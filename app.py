from extensions import db
from db_models import User
from sqlalchemy import func, inspect, select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from forms import LoginForm, RegisterForm, DeleteAccountForm
from common_utils import generate_unique_code
from socket_events import register_socket_events
from constants import AUTHENTICATION_MESSAGE, JOIN_ROOM_MESSAGE

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
database_url = os.environ.get("DATABASE_URL")
if database_url:
    database_uri = make_url(database_url)
    if database_uri.drivername in {"postgres", "postgresql"}:
        database_uri = database_uri.set(drivername="postgresql+psycopg")
    app.config["SQLALCHEMY_DATABASE_URI"] = database_uri
else:
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{database_path}"

db.init_app(app=app)

@app.cli.command("init-db")
def init_db():
    """Create missing database tables and indexes."""
    user_table_exists = inspect(db.engine).has_table(User.__tablename__)
    if user_table_exists:
        duplicate_username = db.session.execute(
            select(func.lower(User.username), func.count())
            .group_by(func.lower(User.username))
            .having(func.count() > 1)
            .limit(1)
        ).first()
        if duplicate_username:
            raise RuntimeError(
                "Cannot enforce case-insensitive username uniqueness: "
                f"duplicate usernames normalize to {duplicate_username[0]!r}. "
                "Resolve the duplicate accounts before initializing the database."
            )

    db.create_all()
    if user_table_exists:
        if db.engine.dialect.name == "sqlite":
            with db.engine.begin() as connection:
                connection.exec_driver_sql(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_user_username_lower "
                    "ON user (lower(username))"
                )
        else:
            for index in User.__table__.indexes:
                index.create(bind=db.engine, checkfirst=True)
    print("Database tables and indexes are initialized.")

socketio = SocketIO(app=app)

bcrypt = Bcrypt(app=app)

login_manager = LoginManager(app=app)
login_manager.login_view = "login"

rooms = {}
register_socket_events(socketio=socketio, rooms=rooms)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(entity=User, ident=int(user_id))

def decode_stored_password_hash(stored_hash):
    if len(stored_hash) != 122 or not stored_hash.startswith(r"\x"):
        return stored_hash

    try:
        decoded_hash = bytes.fromhex(stored_hash[2:]).decode("ascii")
    except (ValueError, UnicodeDecodeError):
        return stored_hash

    is_bcrypt_hash = len(decoded_hash) == 60 and decoded_hash.startswith(
        ("$2a$", "$2b$", "$2y$")
    )
    if is_bcrypt_hash:
        return decoded_hash
    return stored_hash

@app.route("/")
def home():
    if current_user.is_authenticated:
        return redirect(location=url_for(endpoint="chatroom"))
    return redirect(location=url_for(endpoint="login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter(
            func.lower(User.username) == form.username.data.lower()
        ).first()
        stored_hash = user.password if user else None
        if user:
            user.password = decode_stored_password_hash(stored_hash)
        if user and bcrypt.check_password_hash(pw_hash=user.password, password=form.password.data):
            if stored_hash != user.password:
                db.session.commit()
            login_user(user=user)
            return redirect(location=url_for(endpoint="chatroom"))
        form.password.errors.append(
            AUTHENTICATION_MESSAGE["USERNAME_OR_PASSWORD_INVALID"]
        )
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
        if isinstance(hashed_password, bytes):
            hashed_password = hashed_password.decode("utf-8")
        new_user = User(
            username=form.username.data,
            password=hashed_password
        )
        try:
            db.session.add(instance=new_user)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            duplicate_user = User.query.filter(
                func.lower(User.username) == form.username.data.lower()
            ).first()
            if duplicate_user is None:
                raise
            form.username.errors.append(
                AUTHENTICATION_MESSAGE["USERNAME_EXISTS"]
            )
            return render_template(
                template_name_or_list="register.html",
                form=form,
            )
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
            print(JOIN_ROOM_MESSAGE["NO_USERNAME"])
            return redirect(location=url_for(endpoint="login"))
        if join != False and not code:
            return render_template(
                template_name_or_list="chatroom.html",
                error=JOIN_ROOM_MESSAGE["ROOMCODE_EMPTY"],
                code=code,
                name=name,
            )

        room = code
        if create != False:
            room = generate_unique_code(rooms=rooms, code_length=4);
            rooms[room] = {"members": 0, "messages": []}
        elif len(code) != 4 or not code.isalpha():
            return render_template(
                template_name_or_list="chatroom.html",
                error=JOIN_ROOM_MESSAGE["ROOMCODE_INVALID"],
                code=code,
                name=name,
            )
        elif code not in rooms:
            return render_template(
                template_name_or_list="chatroom.html",
                error=JOIN_ROOM_MESSAGE["ROOMCODE_DOESNT_EXIST"],
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

@app.route("/settings")
@login_required
def settings():
    form = DeleteAccountForm()
    return render_template(
        template_name_or_list="settings.html",
        form=form
    )

@app.route("/settings/delete-account", methods=["POST"])
@login_required
def delete_account():
    form = DeleteAccountForm()
    if not form.validate_on_submit():
        return redirect(location=url_for(endpoint="settings"))

    db.session.delete(instance=current_user)
    db.session.commit()

    logout_user()
    session.clear()
    return redirect(location=url_for(endpoint="login"))

if __name__ == "__main__":
    socketio.run(
        app,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "5000")),
        debug=False,
    )
