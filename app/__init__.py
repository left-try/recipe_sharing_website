import os
from flask import Flask, Response, render_template
from dotenv import load_dotenv

from .config import Config
from .extensions import db, login_manager, csrf, migrate
from .models import User, Category
from .utils import render_markdown, slugify

# Factory function to create and configure the Flask application
def create_app():
    load_dotenv()

    app = Flask(__name__)
    app.config.from_object(Config())

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    migrate.init_app(app, db)

    from .main.routes import bp as main_bp
    from .auth.routes import bp as auth_bp
    from .recipes.routes import bp as recipes_bp
    from .api.routes import bp as api_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(recipes_bp, url_prefix="/recipes")
    app.register_blueprint(api_bp, url_prefix="/api")

    register_error_handlers(app)
    register_cli(app)
    app.jinja_env.filters["markdown"] = render_markdown

    with app.app_context():
        os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
        os.makedirs(app.config["AVATAR_FOLDER"], exist_ok=True)

    return app

def register_error_handlers(app: Flask):
    @app.route("/.well-known/appspecific/com.chrome.devtools.json")
    def chrome_devtools_probe():
        return Response(status=204)

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template("errors/500.html"), 500

def register_cli(app: Flask):
    import click
    from werkzeug.security import generate_password_hash
    from .models import User

    @app.cli.command("init-db")
    def init_db():
        db.create_all()
        seed_categories()
        click.echo("Database initialized (tables created, categories seeded).")

    @app.cli.command("create-admin")
    def create_admin():
        email = click.prompt("Admin email")
        username = click.prompt("Admin username")
        password = click.prompt("Admin password", hide_input=True, confirmation_prompt=True)
        if User.query.filter((User.email == email) | (User.username == username)).first():
            click.echo("User with that email/username already exists.")
            return
        u = User(
            email=email,
            username=username,
            password_hash=generate_password_hash(password),
            is_admin=True,
        )
        db.session.add(u)
        db.session.commit()
        click.echo("Admin created.")

def seed_categories():
    defaults = [
        "Breakfast", "Lunch", "Dinner", "Dessert", "Snacks",
        "Drinks", "Vegetarian", "Vegan", "Meat", "Seafood",
        "Baking", "Healthy", "Quick & Easy"
    ]
    existing = {c.name.lower() for c in Category.query.all()}
    for name in defaults:
        if name.lower() not in existing:
            db.session.add(Category(name=name, slug=slugify(name)))
    db.session.commit()
