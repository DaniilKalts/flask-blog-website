from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import current_user, login_required
from dotenv import load_dotenv

from ..forms.forms import UpdateProfileForm
from ..models import User, UserRole
from website import db

load_dotenv()

general_bp = Blueprint("general", __name__, template_folder="../templates")


@general_bp.route("/")
def home():
    user = User.query.get(current_user.id) if current_user.is_authenticated else None

    avatar_url = user.avatar_url if user else ""
    is_admin = user and user.role == UserRole.ADMIN

    return render_template(
        "general/pages/home.html",
        is_admin=is_admin,
        avatar_url=avatar_url,
        active_page="Home",
    )


@general_bp.route("/settings")
@login_required
def settings():
    form = UpdateProfileForm()

    user = User.query.get(current_user.id) if current_user.is_authenticated else None
    if user:
        form.username.data = user.username

    avatar_url = user.avatar_url if user else ""
    is_admin = user and user.role == UserRole.ADMIN

    return render_template(
        "general/pages/settings.html",
        is_admin=is_admin,
        avatar_url=avatar_url,
        active_page="",
        form=form,
    )


@general_bp.route("/settings/delete-avatar", methods=["POST"])
@login_required
def delete_avatar():
    form = UpdateProfileForm()

    user = User.query.get(current_user.id) if current_user.is_authenticated else None
    if user:
        form.username.data = user.username

    if user:
        user.avatar_url = None
        db.session.commit()
        flash("Avatar deleted successfully", "success")
    else:
        flash("User not found", "error")

    return redirect(url_for("general.settings"))
