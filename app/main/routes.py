from flask import Blueprint, render_template, request, url_for
from sqlalchemy import desc

from ..extensions import db
from ..models import Recipe, Category, Tag, Like

bp = Blueprint("main", __name__)

# Route for homepage with paginated list of published recipes
@bp.route("/")
def index():
    page = request.args.get("page", 1, type=int)
    q = request.args.get("q", "", type=str).strip()
    category = request.args.get("category", "", type=str).strip()
    tag = request.args.get("tag", "", type=str).strip()
    sort = request.args.get("sort", "new", type=str).strip()

    query = Recipe.query.filter_by(is_published=True)

    if q:
        query = query.filter(Recipe.title.ilike(f"%{q}%"))

    if category:
        query = query.join(Category).filter(Category.slug == category)

    if tag:
        query = query.join(Recipe.tags).filter(Tag.slug == tag)

    if sort == "popular":
        query = query.outerjoin(Like).group_by(Recipe.id).order_by(desc(db.func.count(Like.id)), desc(Recipe.created_at))
    else:
        query = query.order_by(desc(Recipe.created_at))

    recipes = query.paginate(page=page, per_page=9, error_out=False)

    categories = Category.query.order_by(Category.name).all()
    tags = Tag.query.order_by(Tag.name).limit(20).all()
    args = {**request.view_args, **request.args.to_dict()}
    def pagination_url(page_num):
        a = {**args, "page": page_num}
        return url_for(request.endpoint, **a)

    return render_template("main/index.html",
                        recipes=recipes,
                        categories=categories,
                        tags=tags,
                        q=q, category=category, tag=tag, sort=sort,
                        pagination_url=pagination_url)

@bp.route("/about")
def about():
    return render_template("main/about.html")
