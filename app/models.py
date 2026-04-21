import json
from datetime import datetime, timezone

from flask import url_for
from flask_login import UserMixin
from werkzeug.security import check_password_hash

from .extensions import db, login_manager

recipe_tags = db.Table(
    "recipe_tags",
    db.Column("recipe_id", db.Integer, db.ForeignKey("recipes.id"), primary_key=True),
    db.Column("tag_id", db.Integer, db.ForeignKey("tags.id"), primary_key=True),
)

# Database models for users, categories, tags, recipes, comments, likes, and favorites

class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(32), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    bio = db.Column(db.String(280), default="")
    avatar_filename = db.Column(db.String(255), default="")
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    recipes = db.relationship("Recipe", backref="author", lazy="dynamic", cascade="all, delete-orphan")
    comments = db.relationship("Comment", backref="author", lazy="dynamic", cascade="all, delete-orphan")

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.username}>"

class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), unique=True, nullable=False)
    slug = db.Column(db.String(70), unique=True, nullable=False, index=True)

    recipes = db.relationship("Recipe", backref="category", lazy="dynamic")

    def __repr__(self):
        return f"<Category {self.name}>"

class Tag(db.Model):
    __tablename__ = "tags"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(40), unique=True, nullable=False)
    slug = db.Column(db.String(50), unique=True, nullable=False, index=True)

    def __repr__(self):
        return f"<Tag {self.name}>"

class Recipe(db.Model):
    __tablename__ = "recipes"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(140), nullable=False, index=True)
    description = db.Column(db.String(500), default="")
    ingredients_text = db.Column(db.Text, nullable=False)
    steps_text = db.Column(db.Text, nullable=False)
    steps_data = db.Column(db.Text, nullable=True)

    prep_minutes = db.Column(db.Integer, default=0)
    cook_minutes = db.Column(db.Integer, default=0)
    servings = db.Column(db.Integer, default=1)
    difficulty = db.Column(db.String(20), default="Easy")
    image_filename = db.Column(db.String(255), default="")
    image_storage_key = db.Column(db.String(255), default="")
    image_url = db.Column(db.String(500), default="")
    video_filename = db.Column(db.String(255), default="")
    video_storage_key = db.Column(db.String(255), default="")
    video_url = db.Column(db.String(500), default="")

    is_published = db.Column(db.Boolean, default=True)
    view_count = db.Column(db.Integer, default=0)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=True, index=True)

    tags = db.relationship("Tag", secondary=recipe_tags, lazy="subquery",
                           backref=db.backref("recipes", lazy=True))

    comments = db.relationship("Comment", backref="recipe", lazy="dynamic", cascade="all, delete-orphan")
    likes = db.relationship("Like", backref="recipe", lazy="dynamic", cascade="all, delete-orphan")
    favorites = db.relationship("Favorite", backref="recipe", lazy="dynamic", cascade="all, delete-orphan")

    def ingredients_list(self):
        return [x.strip() for x in (self.ingredients_text or "").splitlines() if x.strip()]

    def has_computable_ingredients(self) -> bool:
        if self.ingredients_list():
            return True
        for step in self.structured_steps():
            if step.get("type") == "content" and (step.get("ingredients") or []):
                return True
        return False

    def steps_list(self):
        items = []
        for step in self.structured_steps():
            if step["type"] == "content":
                description = step["description_markdown"].strip()
                items.append(description or step["title"])
            elif step["type"] == "video":
                items.append("Step video")
            else:
                items.append("Step image")
        return items

    def structured_steps(self):
        raw_steps = self._load_steps_data()
        return raw_steps or self._legacy_steps_data()

    def _load_steps_data(self):
        try:
            payload = json.loads(self.steps_data or "[]")
        except (TypeError, ValueError):
            return []
        if not isinstance(payload, list):
            return []

        normalized = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            step_type = str(item.get("type") or "").strip()
            if step_type == "content":
                ingredients = []
                for ingredient in item.get("ingredients") or []:
                    if not isinstance(ingredient, dict):
                        continue
                    name = str(ingredient.get("name") or "").strip()
                    amount = str(ingredient.get("amount") or ingredient.get("grams") or "").strip()
                    unit = str(ingredient.get("unit") or ("g" if ingredient.get("grams") not in (None, "") else "")).strip()
                    if not name:
                        continue
                    ingredients.append({"name": name, "amount": amount, "unit": unit})
                normalized.append({
                    "type": "content",
                    "title": str(item.get("title") or "").strip(),
                    "description_markdown": str(item.get("description_markdown") or "").strip(),
                    "ingredients": ingredients,
                })
            elif step_type == "image":
                storage_key = str(item.get("image_storage_key") or "").strip()
                image_url = str(item.get("image_url") or "").strip()
                if image_url:
                    normalized.append({
                        "type": "image",
                        "image_storage_key": storage_key,
                        "image_url": image_url,
                    })
            elif step_type == "video":
                storage_key = str(item.get("video_storage_key") or "").strip()
                video_url = str(item.get("video_url") or "").strip()
                if video_url:
                    normalized.append({
                        "type": "video",
                        "video_storage_key": storage_key,
                        "video_url": video_url,
                    })
        return normalized

    def _legacy_steps_data(self):
        return [
            {
                "type": "content",
                "title": f"Step {idx}",
                "description_markdown": text,
                "ingredients": [],
            }
            for idx, text in enumerate(self._legacy_step_lines(), start=1)
        ]

    def _legacy_step_lines(self):
        return [x.strip() for x in (self.steps_text or "").splitlines() if x.strip()]

    @staticmethod
    def build_steps_text(structured_steps) -> str:
        lines = []
        for idx, step in enumerate(structured_steps or [], start=1):
            if step.get("type") == "content":
                title = str(step.get("title") or "").strip()
                description = str(step.get("description_markdown") or "").strip()
                if title and description:
                    lines.append(f"{idx}. {title}: {description}")
                elif description:
                    lines.append(f"{idx}. {description}")
                elif title:
                    lines.append(f"{idx}. {title}")
            elif step.get("type") == "image":
                lines.append(f"{idx}. [Image]")
            elif step.get("type") == "video":
                lines.append(f"{idx}. [Video]")
        return "\n".join(lines)

    @property
    def image_display_url(self) -> str:
        if self.image_url:
            return self.image_url
        if self.image_filename:
            return url_for("static", filename=f"uploads/{self.image_filename}")
        return ""

    def __repr__(self):
        return f"<Recipe {self.title}>"

class Comment(db.Model):
    __tablename__ = "comments"

    id = db.Column(db.Integer, primary_key=True)
    body = db.Column(db.String(600), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    recipe_id = db.Column(db.Integer, db.ForeignKey("recipes.id"), nullable=False, index=True)

class Like(db.Model):
    __tablename__ = "likes"

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    recipe_id = db.Column(db.Integer, db.ForeignKey("recipes.id"), nullable=False, index=True)

    __table_args__ = (db.UniqueConstraint("user_id", "recipe_id", name="uq_like_user_recipe"),)

class Favorite(db.Model):
    __tablename__ = "favorites"

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    recipe_id = db.Column(db.Integer, db.ForeignKey("recipes.id"), nullable=False, index=True)

    __table_args__ = (db.UniqueConstraint("user_id", "recipe_id", name="uq_fav_user_recipe"),)

@login_manager.user_loader
def load_user(user_id: str):
    return User.query.get(int(user_id))
