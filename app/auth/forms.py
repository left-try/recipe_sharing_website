from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, TextAreaField, FileField
from wtforms.validators import DataRequired, Length, Email, EqualTo, ValidationError

from ..models import User
from ..extensions import db

# Forms for user registration, login, profile editing, and password reset


class RegisterForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired(), Length(min=3, max=32)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=6, max=72)])
    confirm = PasswordField("Confirm Password", validators=[DataRequired(), EqualTo("password")])
    submit = SubmitField("Create account")

    def validate_username(self, field):
        if User.query.filter_by(username=field.data).first():
            raise ValidationError("Username already taken.")

    def validate_email(self, field):
        if User.query.filter_by(email=field.data.lower()).first():
            raise ValidationError("Email already registered.")


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Log in")


class ProfileForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired(), Length(min=3, max=32)])
    bio = TextAreaField("Bio", validators=[Length(max=280)])
    avatar = FileField("Avatar (png/jpg/webp)")
    submit = SubmitField("Save")

    def __init__(self, user_id: int, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user_id = user_id

    def validate_username(self, field):
        u = User.query.filter_by(username=field.data).first()
        if u and u.id != self.user_id:
            raise ValidationError("Username already taken.")


class ResetRequestForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    submit = SubmitField("Send reset link")


class ResetPasswordForm(FlaskForm):
    password = PasswordField("New password", validators=[DataRequired(), Length(min=6, max=72)])
    confirm = PasswordField("Confirm", validators=[DataRequired(), EqualTo("password")])
    submit = SubmitField("Reset password")
