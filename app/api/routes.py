from flask import Blueprint, jsonify, request, abort
from flask_login import login_required, current_user

from ..extensions import db
from ..ingredient_compute import compute_recipe_ingredients
from ..models import Recipe, Like, Favorite, Comment

bp = Blueprint("api", __name__)


# Return recipe if it is available for the current user
def _recipe_or_404(recipe_id: int) -> Recipe:
    r = Recipe.query.get(recipe_id)
    if not r or (not r.is_published and (r.user_id != current_user.id and not current_user.is_admin)):
        abort(404)
    return r


def _viewable_recipe_query(recipe_id: int) -> Recipe:
    recipe = Recipe.query.get_or_404(recipe_id)
    if not recipe.is_published and (
        not current_user.is_authenticated
        or (recipe.user_id != current_user.id and not current_user.is_admin)
    ):
        abort(404)
    return recipe


# Return likes count and whether the current user liked the recipe
@bp.post("/recipes/<int:recipe_id>/like")
@login_required
def toggle_like(recipe_id: int):
    recipe = _recipe_or_404(recipe_id)
    existing = Like.query.filter_by(user_id=current_user.id, recipe_id=recipe.id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        return jsonify({"liked": False, "likesCount": recipe.likes.count()})
    db.session.add(Like(user_id=current_user.id, recipe_id=recipe.id))
    db.session.commit()
    return jsonify({"liked": True, "likesCount": recipe.likes.count()})


# Toggle favorite and return whether the recipe is now favorited by the current user
@bp.post("/recipes/<int:recipe_id>/favorite")
@login_required
def toggle_favorite(recipe_id: int):
    recipe = _recipe_or_404(recipe_id)
    existing = Favorite.query.filter_by(user_id=current_user.id, recipe_id=recipe.id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        return jsonify({"favorited": False})
    db.session.add(Favorite(user_id=current_user.id, recipe_id=recipe.id))
    db.session.commit()
    return jsonify({"favorited": True})


# Compute ingredients for a recipe, optionally adjusting quantities for a target servings count and measurement system (metric/us/none)
@bp.get("/recipes/<int:recipe_id>/ingredients-computed")
def ingredients_computed(recipe_id: int):
    recipe = _viewable_recipe_query(recipe_id)
    servings = request.args.get("servings", type=float)
    mode = (request.args.get("mode") or "original").strip().lower()
    if mode not in ("original", "metric", "us"):
        mode = "original"
    payload = compute_recipe_ingredients(recipe, target_servings=servings, mode=mode)
    payload["recipeId"] = recipe.id
    return jsonify(payload)


# Return list of comments for a recipe, with info on whether the current user can delete each comment
@bp.get("/recipes/<int:recipe_id>/comments")
def list_comments(recipe_id: int):
    recipe = Recipe.query.get_or_404(recipe_id)
    if not recipe.is_published and (not current_user.is_authenticated or (recipe.user_id != current_user.id and not current_user.is_admin)):
        abort(404)
    data = []
    for c in recipe.comments.order_by(Comment.created_at.desc()).limit(50).all():
        data.append({
            "id": c.id,
            "body": c.body,
            "createdAt": c.created_at.isoformat(),
            "author": c.author.username,
            "authorId": c.user_id,
            "canDelete": bool(current_user.is_authenticated and (current_user.id == c.user_id or current_user.is_admin)),
        })
    return jsonify({"comments": data})


# Add a comment to a recipe. Body must be 1..600 chars. Return the new comment's ID.
@bp.post("/recipes/<int:recipe_id>/comments")
@login_required
def add_comment(recipe_id: int):
    recipe = _recipe_or_404(recipe_id)
    body = (request.json or {}).get("body", "").strip()
    if not body or len(body) > 600:
        return jsonify({"error": "Comment must be 1..600 chars"}), 400
    c = Comment(body=body, user_id=current_user.id, recipe_id=recipe.id)
    db.session.add(c)
    db.session.commit()
    return jsonify({"ok": True, "commentId": c.id})


# Delete a comment. User must be the comment's author or an admin.
@bp.delete("/comments/<int:comment_id>")
@login_required
def delete_comment(comment_id: int):
    c = Comment.query.get_or_404(comment_id)
    if c.user_id != current_user.id and not current_user.is_admin:
        abort(403)
    db.session.delete(c)
    db.session.commit()
    return jsonify({"ok": True})
