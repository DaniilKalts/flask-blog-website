import uuid
from datetime import datetime, timedelta

from sqlalchemy import Integer, Enum as SQLEnum, String, DateTime, BLOB, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from flask_login import UserMixin

from website import db
from .enums import UserRole, UserTheme


class User(db.Model, UserMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, unique=False, nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SQLEnum(UserRole), nullable=False, default=UserRole.USER
    )
    avatar: Mapped[bytes] = mapped_column(BLOB, nullable=True)
    theme: Mapped[str] = mapped_column(
        SQLEnum(UserTheme), nullable=False, default=UserTheme.SYSTEM
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    posts: Mapped[list["Post"]] = relationship(
        "Post", back_populates="author", cascade="all, delete-orphan"
    )
    images: Mapped[list["Image"]] = relationship(
        "Image", back_populates="author", cascade="all, delete-orphan"
    )
    tags: Mapped[list["Tag"]] = relationship(
        "Tag", back_populates="author", cascade="all, delete-orphan"
    )
    comments: Mapped[list["Comment"]] = relationship(
        "Comment", back_populates="author", cascade="all, delete-orphan"
    )
    saved_posts: Mapped[list["SavedPost"]] = relationship(
        "SavedPost", back_populates="user", cascade="all, delete-orphan"
    )
    notifications: Mapped[list["UserNotification"]] = relationship(
        "UserNotification", back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return (
            f"User Info:\n"
            f"ID: {self.id}\n"
            f"Role: {self.role}\n"
            f"Theme: {self.theme}\n"
            f"Created At: {self.created_at}\n"
            f"Updated At: {self.updated_at}"
        )


class VerificationCode(db.Model):
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(4), nullable=False)
    token: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    def __init__(self, user_id: int, code: str):
        self.user_id = user_id
        self.code = code
        self.token = uuid.uuid4().hex[:16]
        self.expires_at = datetime.utcnow() + timedelta(minutes=2)

    def is_expired(self):
        return datetime.utcnow() > self.expires_at

    @staticmethod
    def delete_expired():
        db.session.query(VerificationCode).filter(
            VerificationCode.expires_at < datetime.utcnow()
        ).delete()
        db.session.commit()
