from extensions import db

from flask_login import UserMixin

class User(db.Model, UserMixin):
    id = db.Column(
        type_=db.Integer,
        primary_key=True
    )
    username = db.Column(
        type_=db.String(length=20),
        nullable=False,
        unique=True
    )
    password = db.Column(
        type_=db.String(length=128),
        nullable=False
    )
