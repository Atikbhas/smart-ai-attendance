from flask import Blueprint, redirect, render_template
from flask_login import current_user

from app.security import role_home

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(role_home(current_user))
    return render_template("main/index.html")


