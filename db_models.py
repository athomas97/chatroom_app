from extensions import db

from flask_login import UserMixin
from sqlalchemy import Index, func

class User(db.Model, UserMixin):
    id = db.Column(
        type_=db.Integer,
        primary_key=True
    )
    username = db.Column(
        type_=db.String(length=20),
        nullable=False,
    )
    password = db.Column(
        type_=db.String(length=128),
        nullable=False
    )
    __table_args__ = (
        Index("uq_user_username_lower", func.lower(username), unique=True),
    )
