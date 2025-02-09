from flask import Blueprint, render_template
from flask_login import current_user

from ..models import User, UserRole
from ..utils import convert_binary_to_image

general_bp = Blueprint("general", __name__, template_folder="../templates")


@general_bp.route("/")
def home():
    avatar_data = None
    is_admin = False

    if current_user.is_authenticated:
        user = User.query.filter(User.id == current_user.id).first()
        is_admin = user.role == UserRole.ADMIN
        if user and user.avatar:
            avatar_data = convert_binary_to_image(user.avatar)

    return render_template(
        "general/pages/home.html", avatar_data=avatar_data, is_admin=is_admin
    )
