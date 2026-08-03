from functools import wraps

from flask import abort, url_for
from flask_login import current_user


def role_home(user) -> str:
    destinations = {
        "admin": "admin.dashboard",
        "professor": "professor.dashboard",
        "student": "student.dashboard",
    }
    return url_for(destinations.get(user.role_name, "main.index"))


def roles_required(*role_names: str):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if current_user.role_name not in role_names:
                abort(403)
            return view(*args, **kwargs)

        return wrapped

    return decorator
