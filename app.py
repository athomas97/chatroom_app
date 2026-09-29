from extensions import db
from db_models import User
from forms import LoginForm, RegisterForm
from common_utils import generate_unique_code
from socket_events import register_socket_events

import os
from dotenv import load_dotenv
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
    login_required,
    login_user,
    logout_user,
    current_user
)
from flask_socketio import SocketIO

app = Flask(__name__)

load_dotenv()
app.config["SECRET_KEY"] = os.getenv(key="CHATROOM_SECRET_KEY")
if not app.config["SECRET_KEY"]:
    raise RuntimeError("Set the CHATROOM_SECRET_KEY environment variable.")

database_path = Path(__file__).resolve().parent / "database.db"
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{database_path}"

db.init_app(app=app)

socketio = SocketIO(app=app)

bcrypt = Bcrypt(app=app)

login_manager = LoginManager(app=app)
login_manager.login_view = "login"

rooms = {}
register_socket_events(socketio=socketio, rooms=rooms)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(entity=User, ident=int(user_id))

@app.route("/")
def home():
    if current_user.is_authenticated:
        return redirect(location=url_for(endpoint="chatroom"))
    return redirect(location=url_for(endpoint="login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(
            username=form.username.data).first()
        if user and bcrypt.check_password_hash(pw_hash=user.password, password=form.password.data):
            login_user(user=user)
            return redirect(location=url_for(endpoint="chatroom"))
    return render_template(template_name_or_list="login.html", form=form)

@app.route("/logout", methods=["GET", "POST"])
@login_required
def logout():
    logout_user()
    return redirect(location=url_for(endpoint="login"))

@app.route("/register", methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(
            password=form.password.data
        )
        new_user = User(
            username=form.username.data,
            password=hashed_password
        )
        db.session.add(instance=new_user)
        db.session.commit()
        return redirect(location=url_for(endpoint="login"))

    return render_template(template_name_or_list="register.html", form=form)

@app.route("/chatroom", methods=["GET", "POST"])
@login_required
def chatroom():
    if request.method == "POST":
        name = current_user.username
        code = request.form.get(key="code")
        join = request.form.get(key="join", default=False)
        create = request.form.get(key="create", default=False)

        # TODO: Update to send error if we cant access username?
        if not name:
            print("ERROR: Could not retrieve username")
            return redirect(location=url_for(endpoint="login"))
        if join != False and not code:
            return render_template(
                template_name_or_list="chatroom.html",
                error="Please enter a room code",
                code=code,
                name=name,
            )

        room = code
        if create != False:
            room = generate_unique_code(rooms=rooms, code_length=4);
            rooms[room] = {"members": 0, "messages": []}
        elif code not in rooms:
            return render_template(
                template_name_or_list="chatroom.html",
                error="Room does not exist",
                code=code,
                name=name,
            )

        session["room"] = room
        return redirect(location=url_for(endpoint="room", code=room))

    session.pop(key="room", default=None)
    return render_template(template_name_or_list="chatroom.html")

@app.route("/chatroom/<code>")
@login_required
def room(code):
    room = session.get("room")
    if room is None or current_user.username is None or room not in rooms:
        return redirect(location=url_for(endpoint="chatroom"))
    return render_template(
        template_name_or_list="room.html",
        code=room,
        messages=rooms[room]["messages"]
    )

if __name__ == "__main__":
    socketio.run(app=app, debug=True)