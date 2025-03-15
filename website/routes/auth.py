import os
import random

from flask import (
    Blueprint,
    request,
    render_template,
    redirect,
    url_for,
    flash,
)
from flask_login import current_user, login_user, login_required, logout_user
from flask_mail import Message
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv

from ..forms import RegisterForm, LoginForm, ForgotPasswordForm, ResetPasswordForm
from ..models import User, VerificationCode
from ..init import google
from website import db, mail, limiter

load_dotenv()

admin_email = os.getenv("ADMIN_EMAIL")
secret_key = os.getenv("SECRET_KEY")
preferred_url_scheme = os.getenv("PREFERRED_URL_SCHEME", "https")

auth_bp = Blueprint("auth", __name__, template_folder="../templates")


def _redirect_to_referrer_or_home():
    """Redirect to the previous page URL if available, else home."""

    return redirect(request.referrer or url_for("general.home"))


def _get_verification_code(token):
    """
    Retrieve a valid verification code using token.
    If invalid or expired, flash an error and return None.

    :param token: The query parameter token.
    """

    verification_code = VerificationCode.query.filter_by(token=token).first()

    if not verification_code or verification_code.is_expired():
        return None

    return verification_code


def _generate_unique_username():
    """Generates a unique username, ensuring it doesn't duplicate in the database."""
    while True:
        candidate = f"user_{random.randint(1000000, 9999999)}"
        if not User.query.filter_by(username=candidate).first():
            return candidate


# --- Google Auth Routes ---


@auth_bp.route("/google/")
def login_google():
    if current_user.is_authenticated:
        return _redirect_to_referrer_or_home()

    try:
        redirect_uri = url_for(
            "auth.authorize_google",
            _external=True,
            _scheme=preferred_url_scheme,
        )
        return google.authorize_redirect(redirect_uri)
    except Exception as e:
        print(f"Error during Google OAuth login: {e}")
        return render_template("errors/pages/500.html"), 500


@auth_bp.route("/google/authorize/")
def authorize_google():
    if current_user.is_authenticated:
        return _redirect_to_referrer_or_home()

    try:
        token = google.authorize_access_token()

        user_info_endpoint = "https://openidconnect.googleapis.com/v1/userinfo"
        response = google.get(user_info_endpoint, token=token)

        user_info = response.json()

        email = user_info.get("email")
        name = user_info.get("name")
        picture = user_info.get("picture")
        google_id = user_info.get("sub")

        user = User.query.filter_by(email=email).first()
        if user:
            user.google_id = google_id
            if not user.avatar_url:
                user.avatar_url = picture
            db.session.commit()
            message = f"Welcome back, {user.username}!"
        else:
            user = User(
                username=name,
                email=email,
                avatar_url=picture,
                google_id=google_id,
            )
            db.session.add(user)
            db.session.commit()
            message = "Your account was created successfully!"

        login_user(user)
        flash(message, "success")

        return redirect(url_for("general.home"))
    except Exception as e:
        flash(
            "An error occurred while signing you in. Please check your credentials and try again later.",
            "danger",
        )
        print(f"Error during Google OAuth callback: {e}")
        return render_template("errors/pages/500.html"), 500


# --- Gmail Auth Routes ---


@auth_bp.route("/register/", methods=["GET", "POST"])
@limiter.limit("5/day", methods=["POST"])
def register():
    if current_user.is_authenticated:
        return _redirect_to_referrer_or_home()

    form = RegisterForm()

    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()

        if user:
            flash("A user with this email already exists.", "danger")
            return redirect(request.url)
        try:
            new_user = User(
                username=_generate_unique_username(),
                email=form.email.data,
                password_hash=generate_password_hash(form.password.data),
            )
            db.session.add(new_user)
            db.session.commit()

            login_user(new_user)
            flash("Your account was created successfully!", "success")

            return redirect(url_for("general.home"))
        except Exception as e:
            flash(
                "An error occurred while creating your account. Please try again later.",
                "danger",
            )
            print(f"Error creating a user:\n\n" f"{e}")

    return render_template("auth/user/pages/register.html", form=form)


@auth_bp.route("/login/", methods=["GET", "POST"])
@limiter.limit("5/minute", methods=["POST"])
def login():
    if current_user.is_authenticated:
        return _redirect_to_referrer_or_home()

    form = LoginForm()

    form.email.label.text = "Your email"
    form.email.render_kw["placeholder"] = "user@gmail.com"

    form.password.render_kw["placeholder"] = "password"

    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()

        if user and user.email != admin_email and not user.password_hash:
            flash(f"You need to sign in with Google.", "info")
            return redirect(request.url)
        elif (
            user
            and user.email != admin_email
            and check_password_hash(user.password_hash, form.password.data)
        ):
            login_user(user)
            flash(f"Welcome back, {user.username}!", "success")
            return redirect(url_for("general.home"))
        else:
            flash("Invalid credentials. Please try again.", "danger")
            return redirect(request.url)

    return render_template("auth/user/pages/login.html", form=form)


@auth_bp.route("/logout/")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "success")
    return redirect(url_for("general.home"))


@auth_bp.route("/forgot-password/", methods=["GET", "POST"])
@limiter.limit("5/minute", methods=["POST"])
def forgot_password():
    form = ForgotPasswordForm()

    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        admin = User.query.filter_by(email=admin_email).first()

        if user and user.email != admin.email:
            if not user.password_hash:
                flash(
                    "Password reset is available for email-registered users.",
                    "info",
                )
                return redirect(url_for("auth.login"))
            code = f"{random.randint(1000, 9999)}"
            verification_code = VerificationCode(user.id, code)
            db.session.add(verification_code)
            db.session.commit()

            token = verification_code.token
            verification_link = f"{request.host_url}auth/verify-code?token={token}"

            message = Message(
                "Verify Your Email with This Code",
                html=render_template(
                    "auth/user/pages/email_message.html",
                    code=code,
                    verification_link=verification_link,
                ),
                sender=os.getenv("ADMIN_EMAIL"),
                recipients=[form.email.data],
            )

            try:
                mail.send(message)
                return redirect(f"/auth/verify-code?token={token}")
            except Exception as error:
                flash(str(error), "danger")
                return redirect(request.url)
        else:
            flash("Invalid credentials. Please try again.", "danger")
            return redirect(request.url)

    return render_template("auth/user/pages/forgot_password.html", form=form)


@auth_bp.route("/verify-code/", methods=["GET", "POST"])
@limiter.limit("5/minute", methods=["POST"])
def verify_code():
    token = request.args.get("token")

    if not token:
        flash("Invalid token. Please fill in your email.", "danger")
        return redirect(url_for("auth.forgot_password"))

    verification_code = _get_verification_code(token)

    if not verification_code:
        flash(
            f"The verification link is invalid or expired.",
            "danger",
        )
        return redirect(url_for("auth.forgot_password"))

    if request.method == "POST":
        user_code = "".join([request.form.get(f"codefield_{idx}") for idx in range(4)])

        if check_password_hash(verification_code.code_hash, user_code):
            verification_code.is_valid = True
            db.session.commit()
            return redirect(url_for("auth.reset_password", token=token))

        return render_template(
            "auth/user/pages/verify_code.html",
            is_valid=False,
        )

    return render_template("auth/user/pages/verify_code.html")


@auth_bp.route("/reset-password/", methods=["GET", "POST"])
def reset_password():
    token = request.args.get("token")

    if not token:
        flash("Invalid token. Please fill in your email.", "danger")
        return redirect(url_for("auth.forgot_password"))

    verification_code = _get_verification_code(token)

    if not verification_code:
        flash(
            f"The verification link is invalid or expired.",
            "danger",
        )
        return redirect(url_for("auth.forgot_password"))

    if not verification_code.is_valid:
        flash("You didn't confirm this code!", "danger")
        return redirect(url_for("auth.verify_code", token=token))

    form = ResetPasswordForm()

    if form.validate_on_submit():
        verification_code = _get_verification_code(token)

        user = User.query.filter_by(id=verification_code.user_id).first()
        user.password_hash = generate_password_hash(form.password.data)
        db.session.delete(verification_code)
        db.session.commit()

        flash("Password reset successfully.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/user/pages/reset_password.html", form=form)


# --- Admin Routes ---


@auth_bp.route("/admin/login/", methods=["GET", "POST"])
@limiter.limit("3/hour", methods=["POST"])
def admin_login():
    if current_user.is_authenticated:
        return _redirect_to_referrer_or_home()

    if request.args.get("token") != secret_key:
        return render_template("errors/pages/403.html")

    form = LoginForm()
    form.email.label.text = "Admin email"
    form.email.render_kw["placeholder"] = "admin@gmail.com"

    form.password.render_kw["placeholder"] = "No one knows it.."

    if form.validate_on_submit():
        admin = User.query.filter_by(email=admin_email).first()

        if admin and (check_password_hash(admin.password_hash, form.password.data)):
            login_user(admin)
            flash("Access granted!", "success")
            return redirect(url_for("general.home"))
        else:
            flash("Invalid credentials. Please try again.", "danger")
            return redirect(request.url)

    return render_template("auth/admin/pages/login.html", form=form)
