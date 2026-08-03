import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


class BaseConfig:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-change-me")
    PROJECT_ROOT = Path(__file__).resolve().parents[1]
    DEFAULT_SQLITE_URI = f"sqlite:///{(PROJECT_ROOT / 'instance' / 'app.db').as_posix()}"
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL") or os.getenv("SQLALCHEMY_DATABASE_URI") or DEFAULT_SQLITE_URI
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WTF_CSRF_ENABLED = True
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    REMEMBER_COOKIE_DURATION = timedelta(days=14)
    SESSION_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"
    REMEMBER_COOKIE_SECURE = os.getenv("REMEMBER_COOKIE_SECURE", "false").lower() == "true"
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", "uploads")
    FACE_DATASET_FOLDER = os.getenv("FACE_DATASET_FOLDER", "uploads/faces")
    FACE_ENCODING_FOLDER = os.getenv("FACE_ENCODING_FOLDER", "uploads/encodings")
    # TTL (seconds) for in-memory face encodings cache; set to 0 to disable caching
    FACE_ENCODINGS_CACHE_TTL = int(os.getenv("FACE_ENCODINGS_CACHE_TTL", "300"))
    # Minimum seconds between manual cache clear requests from admin UI
    FACE_CACHE_CLEAR_RATE_LIMIT_SECONDS = int(os.getenv("FACE_CACHE_CLEAR_RATE_LIMIT_SECONDS", "60"))
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024

    MAIL_SERVER = os.getenv("MAIL_SERVER")
    MAIL_PORT = int(os.getenv("MAIL_PORT", 587))
    MAIL_USE_TLS = os.getenv("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_USE_SSL = os.getenv("MAIL_USE_SSL", "false").lower() == "true"
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER", "noreply@localhost")
    PASSWORD_RESET_TOKEN_EXPIRY = int(os.getenv("PASSWORD_RESET_TOKEN_EXPIRY", 3600))


class DevelopmentConfig(BaseConfig):
    DEBUG = True


class ProductionConfig(BaseConfig):
    DEBUG = False
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True


class TestingConfig(BaseConfig):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}
