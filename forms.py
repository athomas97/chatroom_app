from db_models import User

from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField, SubmitField
from wtforms.validators import InputRequired, Length, ValidationError

class RegisterForm(FlaskForm):
    username = StringField(
        validators=[InputRequired(), Length(min=1, max=20)],
        render_kw={"placeholder": "Username"}
    )
    password = PasswordField(
        validators=[InputRequired(), Length(min=1, max=20)],
        render_kw={"placeholder": "Password"}
    )
    submit = SubmitField(
        label="Register",
        render_kw={"class": "primary-btn popup-btn"},
    )

    def validate_username(self, username):
        existing_user_username = User.query.filter_by(
            username=username.data).first()
        if existing_user_username:
            raise ValidationError(
                message="That username already exists. Please choose a different one"
            )

class LoginForm(FlaskForm):
    username = StringField(
        validators=[InputRequired(), Length(min=1, max=20)],
        render_kw={"placeholder": "Username"}
    )
    password = PasswordField(
        validators=[InputRequired(), Length(min=1, max=20)],
        render_kw={"placeholder": "Password"}
    )
    submit = SubmitField(
        label="Login",
        render_kw={"class": "primary-btn popup-btn"},
    )