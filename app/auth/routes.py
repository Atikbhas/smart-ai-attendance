from datetime import datetime, timezone

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app import db
from app.auth.forms import (
    ChangePasswordForm,
    ForgotPasswordForm,
    LoginForm,
    ResetPasswordForm,
)
from app.auth.token import generate_password_reset_token, verify_password_reset_token
from app.models import Professor, Student, User
from app.security import role_home
from app.utils.email_utils import send_email

auth_bp = Blueprint("auth", __name__, template_folder="../templates")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(role_home(current_user))

    form = LoginForm()
    if form.validate_on_submit():
        raw_id = form.email.data.strip()
        identifier = raw_id.lower()

        # 1. Search by email (case-insensitive)
        user = User.query.filter(db.func.lower(User.email) == identifier).first()

        # 2. Search by professor employee code (e.g. FAC-01, FAC-1, FAC1)
        if not user:
            prof = Professor.query.filter(
                (db.func.lower(Professor.employee_code) == identifier) |
                (Professor.employee_code.ilike(f"%{identifier}%"))
            ).first()
            if prof:
                user = prof.user

        # 3. Search by student roll number (e.g. STU-01, STU-1)
        if not user:
            std = Student.query.filter(
                (db.func.lower(Student.roll_number) == identifier) |
                (Student.roll_number.ilike(f"%{identifier}%"))
            ).first()
            if std:
                user = std.user

        pwd = form.password.data.strip() if form.password.data else ""
        if user and (user.check_password(pwd) or user.check_password(pwd.replace(" ", ""))):
            user.last_login_at = datetime.now(timezone.utc)
            db.session.commit()
            login_user(user, remember=form.remember.data)
            next_url = request.args.get("next")
            return redirect(next_url or role_home(user))

        flash("Invalid credentials. Please check your Email/ID and Password.", "danger")

    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been signed out.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/change-password", methods=["GET", "POST"])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash("Current password is incorrect.", "danger")
        else:
            current_user.set_password(form.new_password.data)
            db.session.commit()
            flash("Password updated successfully.", "success")
            return redirect(role_home(current_user))
    return render_template("auth/change_password.html", form=form)


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(role_home(current_user))

    form = ForgotPasswordForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower().strip()).first()
        if user:
            token = generate_password_reset_token(user.id)
            reset_url = url_for("auth.reset_password", token=token, _external=True)
            html_body = (
                f"<p>Hello {user.full_name},</p>"
                f"<p>Click the link below to reset your password:</p>"
                f"<p><a href=\"{reset_url}\">Reset password</a></p>"
                f"<p>If you did not request this, ignore this email.</p>"
            )
            try:
                send_email(
                    "Password reset request",
                    [user.email],
                    html_body,
                    f"Reset your password using the following link: {reset_url}",
                )
                flash("If that email exists in our system, a reset link has been sent.", "info")
            except Exception:
                flash(
                    "Unable to send reset email right now. Contact support or try again later.",
                    "warning",
                )
        else:
            flash("If that email exists in our system, a reset link has been sent.", "info")
    return render_template("auth/forgot_password_request.html", form=form)


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    if current_user.is_authenticated:
        return redirect(role_home(current_user))

    user_id = verify_password_reset_token(token)
    if user_id is None:
        flash("This password reset link is invalid or expired.", "danger")
        return redirect(url_for("auth.forgot_password"))

    user = User.query.get(user_id)
    if not user:
        flash("This password reset link is invalid or expired.", "danger")
        return redirect(url_for("auth.forgot_password"))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.new_password.data)
        db.session.commit()
        flash("Your password has been updated successfully.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/reset_password.html", form=form)
