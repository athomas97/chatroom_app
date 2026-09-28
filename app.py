import os
import random
from string import ascii_uppercase
from pathlib import Path

from flask import (
    Flask,
    redirect,
    render_template,
    url_for,
    session,
    request
)
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
from flask_socketio import (
    join_room,
    leave_room,
    send,
    SocketIO
)
from flask_wtf import FlaskForm
from wtforms import PasswordField, StringField, SubmitField
from wtforms.validators import InputRequired, Length, ValidationError

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("CHATROOM_SECRET_KEY")
if not app.config["SECRET_KEY"]:
    raise RuntimeError("Set the CHATROOM_SECRET_KEY environment variable.")

database_path = Path(__file__).resolve().parent / "database.db"
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{database_path}"

socketio = SocketIO(app)

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"

rooms = {}

def generate_unique_code(length):
    while True:
        code = ""
        for _ in range(length):
            code += random.choice(ascii_uppercase)
        if code not in rooms:
            return code

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

@app.route('/chatroom', methods=['GET', 'POST'])
@login_required
def chatroom():
    if request.method == "POST":
        name = current_user.username
        code = request.form.get("code")
        join = request.form.get("join", False)
        create = request.form.get("create", False)

        # TODO: Update to send error if we cant access username?
        if not name:
            print("ERROR: Could not retrieve username")
            return redirect(url_for('login'))
        if join != False and not code:
            return render_template(
                'chatroom.html', error="Please enter a room code", code=code, name=name
            )

        room = code
        if create != False:
            room = generate_unique_code(4);
            rooms[room] = {"members": 0, "messages": []}
        elif code not in rooms:
            return render_template(
                'chatroom.html', error="Room does not exist", code=code, name=name
            )

        session["room"] = room
        return redirect(url_for("room", code=room))

    session.pop("room", None)
    return render_template('chatroom.html')

@app.route('/chatroom/<code>')
@login_required
def room(code):
    room = session.get("room")
    if room is None or current_user.username is None or room not in rooms:
        return redirect(url_for("chatroom"))
    return render_template(
        'room.html',
        code=room,
        messages=rooms[room]["messages"]
    )

@socketio.on("message")
def message(data):
    room = session.get("room")
    if room not in rooms:
        return

    content = {
        "name": current_user.username,
        "message": data["data"]
    }
    send(content, to=room)
    rooms[room]["messages"].append(content)
    print(f"{current_user.username} said: {data['data']}")

@socketio.on("connect")
def connect(auth):
    room = session.get("room")

    if not room or not current_user.is_authenticated:
        return
    if room not in rooms:
        leave_room(room)
        return

    join_room(room)
    send({"name": current_user.username, "message": "has entered the room"}, to=room)
    rooms[room]["members"] += 1
    print(f"{current_user.username} joined room {room}")

@socketio.on("disconnect")
def disconnect():
    room = session.get("room")
    name = current_user.username
    leave_room(room)

    if room in rooms:
        rooms[room]["members"] -= 1
        if rooms[room]["members"] <= 0:
            del rooms[room]

    send({"name": name, "message": "has left the room"}, to=room)
    print(f"{name} left room {room}")

if __name__ == "__main__":
    socketio.run(app, debug=True)