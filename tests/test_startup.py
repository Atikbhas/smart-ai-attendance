import importlib
import sys
from sqlalchemy import inspect


def test_create_app_creates_user_table_without_preloaded_models():
    sys.modules.pop("app.models", None)
    import app as app_module

    app_module = importlib.reload(app_module)
    app = app_module.create_app("testing")

    with app.app_context():
        table_names = inspect(app_module.db.engine).get_table_names()

    assert "users" in table_names
