from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField
from wtforms.validators import DataRequired

class PostForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired()])
    content = TextAreaField('Content', validators=[DataRequired()])
    ingredients = TextAreaField('Ingredients', validators=[DataRequired()], render_kw={"rows": 5})  # Set rows for the textarea
    submit = SubmitField('Post')

class SearchForm(FlaskForm):
    ingredients = TextAreaField('Ingredients', validators=[DataRequired()])
    submit = SubmitField('Search')