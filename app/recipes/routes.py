import json

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, send_file, url_for
from flask_login import login_required, current_user
from sqlalchemy import desc

from ..extensions import db
from ..models import Category, Favorite, Like, Recipe, Tag
from ..pdf import build_recipe_pdf
from ..storage import (
    StorageServiceError,
    delete_recipe_image,
    upload_recipe_image,
    upload_recipe_step_image,
    upload_recipe_step_video,
)
from ..utils import delete_file_safely, slugify
from .forms import RecipeForm

bp = Blueprint("recipes", __name__)


# Route for checking if current user can modify the receipe
def _require_owner_or_admin(recipe: Recipe):
    if recipe.user_id != current_user.id and not current_user.is_admin:
        abort(403)


# Route for checking if a recipe is viewable by the current user
def _viewable_recipe_or_404(recipe_id: int) -> Recipe:
    recipe = Recipe.query.get_or_404(recipe_id)
    if not recipe.is_published and (not current_user.is_authenticated or (recipe.user_id != current_user.id and not current_user.is_admin)):
        abort(404)
    return recipe


# Helper functions for parsing and validating recipe steps data

def _delete_remote_image_quietly(storage_key: str):
    if not storage_key:
        return
    try:
        delete_recipe_image(storage_key)
    except StorageServiceError as exc:
        current_app.logger.warning("Could not delete remote recipe image %s: %s", storage_key, exc)

class StepValidationError(ValueError):
    pass

def _serialize_steps(steps) -> str:
    return json.dumps(steps, ensure_ascii=True)

def _collect_step_storage_keys(steps) -> set[str]:
    keys = set()
    for step in steps or []:
        if not isinstance(step, dict):
            continue
        if step.get("type") == "image":
            storage_key = str(step.get("image_storage_key") or "").strip()
            if storage_key:
                keys.add(storage_key)
        elif step.get("type") == "video":
            storage_key = str(step.get("video_storage_key") or "").strip()
            if storage_key:
                keys.add(storage_key)
    return keys

def _parse_step_ingredient_quantity(ingredient, *, step_number: int, ingredient_number: int):
    amount = str(ingredient.get("amount") or ingredient.get("grams") or "").strip()
    unit = str(ingredient.get("unit") or ("g" if ingredient.get("grams") not in (None, "") else "")).strip()
    if amount:
        try:
            numeric_amount = float(amount.replace(",", "."))
        except ValueError as exc:
            raise StepValidationError(
                f"Step {step_number} ingredient {ingredient_number} amount must be numeric."
            ) from exc
        if numeric_amount <= 0:
            raise StepValidationError(
                f"Step {step_number} ingredient {ingredient_number} amount must be greater than 0."
            )
    return amount, unit

def _parse_steps_payload(raw_payload: str, uploaded_files) -> tuple[list[dict], list[str]]:
    try:
        payload = json.loads(raw_payload or "[]")
    except ValueError as exc:
        raise StepValidationError("Steps data is invalid.") from exc
    if not isinstance(payload, list) or not payload:
        raise StepValidationError("Please add at least one step.")

    uploaded_storage_keys = []
    steps = []
    try:
        for index, item in enumerate(payload, start=1):
            if not isinstance(item, dict):
                raise StepValidationError(f"Step {index} is invalid.")

            step_type = str(item.get("type") or "").strip()
            if step_type == "content":
                title = str(item.get("title") or "").strip()
                description = str(item.get("description_markdown") or "").strip()
                if not title:
                    raise StepValidationError(f"Step {index} title is required.")
                if not description:
                    raise StepValidationError(f"Step {index} description is required.")

                ingredients = []
                for ingredient_index, ingredient in enumerate(item.get("ingredients") or [], start=1):
                    if not isinstance(ingredient, dict):
                        raise StepValidationError(f"Step {index} has an invalid ingredient.")
                    name = str(ingredient.get("name") or "").strip()
                    if not name:
                        raise StepValidationError(f"Step {index} ingredient {ingredient_index} name is required.")
                    amount, unit = _parse_step_ingredient_quantity(
                        ingredient,
                        step_number=index,
                        ingredient_number=ingredient_index,
                    )
                    ingredients.append({"name": name, "amount": amount, "unit": unit})

                steps.append({
                    "type": "content",
                    "title": title,
                    "description_markdown": description,
                    "ingredients": ingredients,
                })
                continue

            if step_type == "image":
                existing_key = str(item.get("image_storage_key") or "").strip()
                existing_url = str(item.get("image_url") or "").strip()
                upload_field = str(item.get("upload_field") or "").strip()
                file_storage = uploaded_files.get(upload_field) if upload_field else None

                if file_storage and file_storage.filename:
                    uploaded = upload_recipe_step_image(file_storage)
                    if uploaded.storage_key:
                        uploaded_storage_keys.append(uploaded.storage_key)
                    existing_key = uploaded.storage_key
                    existing_url = uploaded.public_url

                if not existing_url:
                    raise StepValidationError(f"Step {index} image is required.")

                steps.append({
                    "type": "image",
                    "image_storage_key": existing_key,
                    "image_url": existing_url,
                })
                continue

            if step_type == "video":
                existing_key = str(item.get("video_storage_key") or "").strip()
                existing_url = str(item.get("video_url") or "").strip()
                upload_field = str(item.get("upload_field") or "").strip()
                file_storage = uploaded_files.get(upload_field) if upload_field else None

                if file_storage and file_storage.filename:
                    uploaded = upload_recipe_step_video(file_storage)
                    if uploaded.storage_key:
                        uploaded_storage_keys.append(uploaded.storage_key)
                    existing_key = uploaded.storage_key
                    existing_url = uploaded.public_url

                if not existing_url:
                    raise StepValidationError(f"Step {index} video is required.")

                steps.append({
                    "type": "video",
                    "video_storage_key": existing_key,
                    "video_url": existing_url,
                })
                continue

            raise StepValidationError(f"Step {index} has an unsupported type.")
    except Exception:
        for storage_key in uploaded_storage_keys:
            _delete_remote_image_quietly(storage_key)
        raise

    return steps, uploaded_storage_keys

def _steps_from_legacy_text(raw_text: str) -> list[dict]:
    lines = [line.strip() for line in (raw_text or "").splitlines() if line.strip()]
    return [
        {
            "type": "content",
            "title": f"Step {index}",
            "description_markdown": line,
            "ingredients": [],
        }
        for index, line in enumerate(lines, start=1)
    ]

def _parse_or_fallback_steps(form, uploaded_files) -> tuple[list[dict], list[str]]:
    try:
        return _parse_steps_payload(form.steps_data.data, uploaded_files)
    except StepValidationError:
        legacy_steps = _steps_from_legacy_text(form.steps_text.data)
        if legacy_steps:
            return legacy_steps, []
        raise


# Route for creating a new recipe, with form validation and image upload handling
@bp.route("/new", methods=["GET", "POST"])
@login_required
def create():
    form = RecipeForm()
    form.category_id.choices = [(0, "— No category —")] + [(c.id, c.name) for c in Category.query.order_by(Category.name).all()]
    if request.method == "GET" and not form.steps_data.data:
        form.steps_data.data = "[]"

    if form.validate_on_submit():
        uploaded_image = None
        uploaded_step_keys = []
        if form.image.data:
            try:
                uploaded_image = upload_recipe_image(form.image.data)
            except (StorageServiceError, ValueError) as e:
                flash(str(e), "danger")
                return render_template("recipes/form.html", form=form, mode="create"), 400
        try:
            structured_steps, uploaded_step_keys = _parse_or_fallback_steps(form, request.files)
        except (StepValidationError, StorageServiceError, ValueError) as e:
            if uploaded_image:
                _delete_remote_image_quietly(uploaded_image.storage_key)
            flash(str(e), "danger")
            return render_template("recipes/form.html", form=form, mode="create"), 400

        recipe = Recipe(
            title=form.title.data.strip(),
            description=(form.description.data or "").strip(),
            ingredients_text=form.ingredients_text.data.strip(),
            steps_text=Recipe.build_steps_text(structured_steps),
            steps_data=_serialize_steps(structured_steps),
            prep_minutes=form.prep_minutes.data or 0,
            cook_minutes=form.cook_minutes.data or 0,
            servings=form.servings.data or 1,
            difficulty=form.difficulty.data,
            category_id=(form.category_id.data or 0) or None,
            image_storage_key=uploaded_image.storage_key if uploaded_image else "",
            image_url=uploaded_image.public_url if uploaded_image else "",
            is_published=bool(form.is_published.data),
            author=current_user,
        )

        db.session.add(recipe)
        tags = parse_tags(form.tags_csv.data or "")
        recipe.tags = tags

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            if uploaded_image:
                _delete_remote_image_quietly(uploaded_image.storage_key)
            for storage_key in uploaded_step_keys:
                _delete_remote_image_quietly(storage_key)
            raise

        flash("Recipe created.", "success")
        return redirect(url_for("recipes.detail", recipe_id=recipe.id))

    return render_template("recipes/form.html", form=form, mode="create")


# Route for viewing a recipe's details
@bp.route("/<int:recipe_id>")
def detail(recipe_id: int):
    recipe = _viewable_recipe_or_404(recipe_id)

    recipe.view_count += 1
    db.session.commit()

    liked = False
    favorited = False
    if current_user.is_authenticated:
        liked = Like.query.filter_by(user_id=current_user.id, recipe_id=recipe.id).first() is not None
        favorited = Favorite.query.filter_by(user_id=current_user.id, recipe_id=recipe.id).first() is not None

    return render_template("recipes/detail.html", recipe=recipe, liked=liked, favorited=favorited)


# Route for editing a recipe with form validation
@bp.route("/<int:recipe_id>/edit", methods=["GET", "POST"])
@login_required
def edit(recipe_id: int):
    recipe = Recipe.query.get_or_404(recipe_id)
    _require_owner_or_admin(recipe)

    form = RecipeForm(obj=recipe)
    form.category_id.choices = [(0, "— No category —")] + [(c.id, c.name) for c in Category.query.order_by(Category.name).all()]
    form.category_id.data = recipe.category_id or 0
    form.tags_csv.data = ", ".join([t.name for t in recipe.tags])
    if request.method == "GET":
        form.steps_data.data = _serialize_steps(recipe.structured_steps())

    if form.validate_on_submit():
        uploaded_image = None
        uploaded_step_keys = []
        if form.image.data:
            try:
                uploaded_image = upload_recipe_image(form.image.data)
            except (StorageServiceError, ValueError) as e:
                flash(str(e), "danger")
                return render_template("recipes/form.html", form=form, mode="edit", recipe=recipe), 400
        try:
            structured_steps, uploaded_step_keys = _parse_or_fallback_steps(form, request.files)
        except (StepValidationError, StorageServiceError, ValueError) as e:
            if uploaded_image:
                _delete_remote_image_quietly(uploaded_image.storage_key)
            flash(str(e), "danger")
            return render_template("recipes/form.html", form=form, mode="edit", recipe=recipe), 400

        previous_storage_key = recipe.image_storage_key
        previous_image_filename = recipe.image_filename
        previous_video_storage_key = recipe.video_storage_key
        previous_video_filename = recipe.video_filename
        previous_step_storage_keys = _collect_step_storage_keys(recipe.structured_steps())
        recipe.title = form.title.data.strip()
        recipe.description = (form.description.data or "").strip()
        recipe.ingredients_text = form.ingredients_text.data.strip()
        recipe.steps_text = Recipe.build_steps_text(structured_steps)
        recipe.steps_data = _serialize_steps(structured_steps)
        recipe.prep_minutes = form.prep_minutes.data or 0
        recipe.cook_minutes = form.cook_minutes.data or 0
        recipe.servings = form.servings.data or 1
        recipe.difficulty = form.difficulty.data
        recipe.category_id = (form.category_id.data or 0) or None
        recipe.is_published = bool(form.is_published.data)

        if uploaded_image:
            recipe.image_storage_key = uploaded_image.storage_key
            recipe.image_url = uploaded_image.public_url
            recipe.image_filename = ""

        recipe.video_storage_key = ""
        recipe.video_url = ""
        recipe.video_filename = ""

        recipe.tags = parse_tags(form.tags_csv.data or "")

        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            if uploaded_image:
                _delete_remote_image_quietly(uploaded_image.storage_key)
            for storage_key in uploaded_step_keys:
                _delete_remote_image_quietly(storage_key)
            raise

        if uploaded_image:
            if previous_storage_key and previous_storage_key != uploaded_image.storage_key:
                _delete_remote_image_quietly(previous_storage_key)
            elif not previous_storage_key and previous_image_filename:
                delete_file_safely(current_app.config["UPLOAD_FOLDER"], previous_image_filename)
        if previous_video_storage_key:
            _delete_remote_image_quietly(previous_video_storage_key)
        elif previous_video_filename:
            delete_file_safely(current_app.config["UPLOAD_FOLDER"], previous_video_filename)
        current_step_storage_keys = _collect_step_storage_keys(structured_steps)
        for storage_key in previous_step_storage_keys - current_step_storage_keys:
            _delete_remote_image_quietly(storage_key)

        flash("Recipe updated.", "success")
        return redirect(url_for("recipes.detail", recipe_id=recipe.id))

    return render_template("recipes/form.html", form=form, mode="edit", recipe=recipe)


# Route for deleting a recipe, with cleanup of associated images and videos
@bp.route("/<int:recipe_id>/delete", methods=["POST"])
@login_required
def delete(recipe_id: int):
    recipe = Recipe.query.get_or_404(recipe_id)
    _require_owner_or_admin(recipe)

    storage_key = recipe.image_storage_key
    legacy_image_filename = recipe.image_filename
    video_storage_key = recipe.video_storage_key
    legacy_video_filename = recipe.video_filename
    step_storage_keys = _collect_step_storage_keys(recipe.structured_steps())
    db.session.delete(recipe)
    db.session.commit()
    if storage_key:
        _delete_remote_image_quietly(storage_key)
    elif legacy_image_filename:
        delete_file_safely(current_app.config["UPLOAD_FOLDER"], legacy_image_filename)
    if video_storage_key:
        _delete_remote_image_quietly(video_storage_key)
    elif legacy_video_filename:
        delete_file_safely(current_app.config["UPLOAD_FOLDER"], legacy_video_filename)
    for step_storage_key in step_storage_keys:
        _delete_remote_image_quietly(step_storage_key)
    flash("Recipe deleted.", "info")
    return redirect(url_for("main.index"))


# Route for exporting a recipe as a PDF, with optional servings and unit mode adjustments
@bp.route("/<int:recipe_id>/export.pdf")
def export_pdf(recipe_id: int):
    recipe = _viewable_recipe_or_404(recipe_id)
    servings = request.args.get("servings", type=float)
    mode = (request.args.get("mode") or "original").strip().lower()
    if mode not in ("original", "metric", "us"):
        mode = "original"
    pdf_buffer, filename = build_recipe_pdf(recipe, target_servings=servings, unit_mode=mode)
    return send_file(pdf_buffer, mimetype="application/pdf", as_attachment=True, download_name=filename)


# Route for listing the current user's own recipes with pagination
@bp.route("/mine")
@login_required
def mine():
    page = request.args.get("page", 1, type=int)
    query = Recipe.query.filter_by(user_id=current_user.id).order_by(desc(Recipe.created_at))
    recipes = query.paginate(page=page, per_page=9, error_out=False)
    return render_template("recipes/mine.html", recipes=recipes)


# Route for listing the current user's favorite recipes with pagination
@bp.route("/favorites")
@login_required
def favorites():
    page = request.args.get("page", 1, type=int)
    query = Recipe.query.join(Favorite).filter(Favorite.user_id == current_user.id).order_by(desc(Favorite.created_at))
    recipes = query.paginate(page=page, per_page=9, error_out=False)
    return render_template("recipes/favorites.html", recipes=recipes)

def parse_tags(csv_text: str):
    names = [x.strip() for x in csv_text.split(",") if x.strip()]
    names = names[:12]
    out = []
    for name in names:
        slug = slugify(name)
        t = Tag.query.filter_by(slug=slug).first()
        if not t:
            t = Tag(name=name, slug=slug)
            db.session.add(t)
        out.append(t)
    return out
