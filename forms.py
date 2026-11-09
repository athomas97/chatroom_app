from db_models import User
from constants import AUTHENTICATION_MESSAGE

from sqlalchemy import func
from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField, SubmitField
from wtforms.validators import InputRequired, Length, ValidationError, Regexp

class RegisterForm(FlaskForm):
    username = StringField(
        validators=[
            InputRequired(),
            Length(
                min=5, max=20,
                message=AUTHENTICATION_MESSAGE["USERNAME_INVALID_LENGTH"],
            ),
            Regexp(
                r"^[A-Za-z0-9_.-]+$",
                message=AUTHENTICATION_MESSAGE["USERNAME_INVALID_CHARACTERS"],
            ),
        ],
        render_kw={"placeholder": "Username", "autocomplete": "off"}
    )
    password = PasswordField(
        validators=[
            InputRequired(),
            Length(
                min=5, max=20,
                message=AUTHENTICATION_MESSAGE["PASSWORD_INVALID_LENGTH"],
            )
        ],
        render_kw={"placeholder": "Password"}
    )
    submit = SubmitField(
        label="Register",
        render_kw={"class": "primary-btn popup-btn"},
    )

    def validate_username(self, username):
        existing_user_username = User.query.filter(
            func.lower(User.username) == username.data.lower()
        ).first()
        if existing_user_username:
            raise ValidationError(
                message=AUTHENTICATION_MESSAGE["USERNAME_EXISTS"],
            )

class LoginForm(FlaskForm):
    username = StringField(
        validators=[
            InputRequired(),
            Length(
                min=5, max=20,
                message=AUTHENTICATION_MESSAGE["USERNAME_INVALID_LENGTH"],
            ),
            Regexp(
                r"^[A-Za-z0-9_.-]+$",
                message=AUTHENTICATION_MESSAGE["USERNAME_INVALID_CHARACTERS"],
            ),
        ],
        render_kw={"placeholder": "Username"}
    )
    password = PasswordField(
        validators=[
            InputRequired(),
            Length(
                min=5, max=20,
                message=AUTHENTICATION_MESSAGE["PASSWORD_INVALID_LENGTH"],
            )
        ],
        render_kw={"placeholder": "Password"}
    )
    submit = SubmitField(
        label="Login",
        render_kw={"class": "primary-btn popup-btn"},
    )

    def validate_username(self, username):
        user = User.query.filter(
            func.lower(User.username) == username.data.lower()
        ).first()

        if user is None:
            raise ValidationError(
                AUTHENTICATION_MESSAGE["USERNAME_OR_PASSWORD_INVALID"]
            )

class DeleteAccountForm(FlaskForm):
    delete = SubmitField(
        label="Delete Account",
        render_kw={"class": "warning-btn popup-btn"},
    )