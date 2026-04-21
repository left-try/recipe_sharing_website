from flask_wtf import FlaskForm
from wtforms import BooleanField, FileField, IntegerField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length, NumberRange, Optional

DIFFICULTY_CHOICES = [("Easy", "Easy"), ("Medium", "Medium"), ("Hard", "Hard")]

# Form for creating and editing recipes, with fields for title, description, ingredients, steps, prep/cook time, servings, difficulty, category, tags, image, and publish status
class RecipeForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired(), Length(min=3, max=140)])
    description = TextAreaField("Short description", validators=[Optional(), Length(max=500)])
    ingredients_text = TextAreaField(
        "Ingredients (one per line)",
        validators=[DataRequired()],
        render_kw={"required": False},
    )
    steps_text = TextAreaField("Steps (legacy fallback)", validators=[Optional()])
    steps_data = TextAreaField("Structured steps", validators=[Optional()])

    prep_minutes = IntegerField("Prep time (min)", validators=[Optional(), NumberRange(min=0, max=10000)])
    cook_minutes = IntegerField("Cook time (min)", validators=[Optional(), NumberRange(min=0, max=10000)])
    servings = IntegerField("Servings", validators=[Optional(), NumberRange(min=1, max=200)])
    difficulty = SelectField("Difficulty", choices=DIFFICULTY_CHOICES)

    category_id = SelectField("Category", coerce=int, validators=[Optional()])
    tags_csv = StringField("Tags (comma separated)", validators=[Optional(), Length(max=200)])

    image = FileField("Recipe cover image (png/jpg/webp)")
    is_published = BooleanField("Publish now", default=True)

    submit = SubmitField("Save recipe")
