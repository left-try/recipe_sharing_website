from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash

from ..extensions import db
from ..models import User
from ..utils import save_image, delete_file_safely
from .forms import RegisterForm, LoginForm, ProfileForm, ResetRequestForm, ResetPasswordForm

bp = Blueprint("auth", __name__)

def _serializer():
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"])

def generate_reset_token(email: str) -> str:
    return _serializer().dumps(email, salt="pwd-reset")

def verify_reset_token(token: str, max_age_seconds=3600) -> str | None:
    try:
        email = _serializer().loads(token, salt="pwd-reset", max_age=max_age_seconds)
        return email
    except (BadSignature, SignatureExpired):
        return None

# Routes for user registration, login, logout, profile editing, and password reset


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    form = RegisterForm()
    if form.validate_on_submit():
        u = User(
            username=form.username.data.strip(),
            email=form.email.data.strip().lower(),
            password_hash=generate_password_hash(form.password.data),
        )
        db.session.add(u)
        db.session.commit()
        flash("Account created. You can log in now.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/register.html", form=form)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    form = LoginForm()
    if form.validate_on_submit():
        u = User.query.filter_by(email=form.email.data.strip().lower()).first()
        if not u or not u.check_password(form.password.data):
            flash("Invalid email or password.", "danger")
            return render_template("auth/login.html", form=form), 401
        login_user(u, remember=True)
        flash("Logged in.", "success")
        next_url = request.args.get("next")
        return redirect(next_url or url_for("main.index"))
    return render_template("auth/login.html", form=form)


@bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out.", "info")
    return redirect(url_for("main.index"))


@bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    form = ProfileForm(user_id=current_user.id, obj=current_user)
    if form.validate_on_submit():
        current_user.username = form.username.data.strip()
        current_user.bio = (form.bio.data or "").strip()

        if form.avatar.data:
            try:
                filename = save_image(form.avatar.data, current_app.config["AVATAR_FOLDER"], max_size=(512, 512))
                delete_file_safely(current_app.config["AVATAR_FOLDER"], current_user.avatar_filename)
                current_user.avatar_filename = filename
            except ValueError as e:
                flash(str(e), "danger")
                return render_template("auth/profile.html", form=form), 400

        db.session.commit()
        flash("Profile updated.", "success")
        return redirect(url_for("auth.profile"))
    return render_template("auth/profile.html", form=form)


@bp.route("/reset", methods=["GET", "POST"])
def reset_request():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    form = ResetRequestForm()
    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        u = User.query.filter_by(email=email).first()
        if u:
            token = generate_reset_token(email)
            reset_url = url_for("auth.reset_token", token=token, _external=True)
            current_app.logger.warning("Password reset link for %s: %s", email, reset_url)
        flash("If that email exists, a reset link has been sent (check server console).", "info")
        return redirect(url_for("auth.login"))
    return render_template("auth/reset_request.html", form=form)


# Route for resetting password using a token. Token is valid for 1 hour. If valid, allow user to set a new password.
@bp.route("/reset/<token>", methods=["GET", "POST"])
def reset_token(token):
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))
    email = verify_reset_token(token)
    if not email:
        flash("Reset link is invalid or expired.", "danger")
        return redirect(url_for("auth.reset_request"))
    form = ResetPasswordForm()
    if form.validate_on_submit():
        u = User.query.filter_by(email=email).first()
        if not u:
            flash("Account not found.", "danger")
            return redirect(url_for("auth.register"))
        u.password_hash = generate_password_hash(form.password.data)
        db.session.commit()
        flash("Password updated. You can log in now.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/reset_token.html", form=form)
