from datetime import datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe

from flask import current_app


def generate_password_reset_token(user_id: int) -> str:
    token = token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(seconds=current_app.config["PASSWORD_RESET_TOKEN_EXPIRY"])
    payload = f"{user_id}:{token}:{int(expires_at.timestamp())}"
    signature = sha256(payload.encode("utf-8") + current_app.config["SECRET_KEY"].encode("utf-8")).hexdigest()
    return f"{payload}:{signature}"


def verify_password_reset_token(token: str) -> int | None:
    try:
        user_id_str, token_value, expiry_str, signature = token.split(":")
    except ValueError:
        return None

    payload = f"{user_id_str}:{token_value}:{expiry_str}"
    expected_signature = sha256(payload.encode("utf-8") + current_app.config["SECRET_KEY"].encode("utf-8")).hexdigest()
    if signature != expected_signature:
        return None

    expires_at = datetime.utcfromtimestamp(int(expiry_str))
    if datetime.utcnow() > expires_at:
        return None

    return int(user_id_str)
