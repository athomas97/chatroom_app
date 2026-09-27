import os
from pathlib import Path

from flask import Flask, redirect, render_template, url_for
from flask_bcrypt import Bcrypt
from flask_login import (
    LoginManager,
    UserMixin,
    login_required,
    login_user,
    logout_user,
    current_user
)
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField, SubmitField
from wtforms.validators import InputRequired, Length, ValidationError

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("CHATROOM_SECRET_KEY")
if not app.config["SECRET_KEY"]:
    raise RuntimeError("Set the CHATROOM_SECRET_KEY environment variable.")

database_path = Path(__file__).resolve().parent / "database.db"
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{database_path}"

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), nullable=False, unique=True)
    password = db.Column(db.String(20), nullable=False)

class RegisterForm(FlaskForm):
    username = StringField(
        validators=[InputRequired(), Length(min=1, max=20)],
        render_kw={"placeholder": "Username"}
    )
    password = PasswordField(
        validators=[InputRequired(), Length(min=1, max=20)],
        render_kw={"placeholder": "Password"}
    )
    submit = SubmitField("Register")

    def validate_username(self, username):
        existing_user_username = User.query.filter_by(
            username=username.data).first()
        if existing_user_username:
            raise ValidationError(
                "That username already exists. Please choose a different one"
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
    submit = SubmitField("Login")

@app.route('/')
def home():
    if current_user.is_authenticated:
        return redirect(url_for("chatroom"))
    return redirect(url_for("login"))

@app.route('/chatroom', methods=['GET', 'POST'])
@login_required
def chatroom():
    return render_template('chatroom.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(
            username=form.username.data).first()
        if user and bcrypt.check_password_hash(user.password, form.password.data):
            login_user(user)
            return redirect(url_for("chatroom"))
    return render_template('login.html', form=form)

@app.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(
            form.password.data
        )
        new_user = User(
            username=form.username.data,
            password=hashed_password
        )
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))

    return render_template('register.html', form=form)

if __name__ == "__main__":
    app.run(debug=True)