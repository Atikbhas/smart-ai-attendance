import base64
import io
import json

import qrcode
from flask import current_app
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer


QR_TOKEN_SALT = "qr-attendance-session"


def _serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=QR_TOKEN_SALT)


def generate_qr_session_token(session_id: int) -> str:
    return _serializer().dumps({"session_id": session_id})


def verify_qr_session_token(token: str, max_age_seconds: int = 900) -> int | None:
    try:
        payload = _serializer().loads(token, max_age=max_age_seconds)
    except (BadSignature, SignatureExpired):
        return None

    try:
        return int(payload["session_id"])
    except (KeyError, TypeError, ValueError):
        return None


def qr_code_data_uri(value: str) -> str:
    image = qrcode.make(value)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def generate_student_qr_payload(student) -> str:
    """Generate standardized JSON payload for a student's ID Card QR code."""
    payload = {
        "student_id": student.roll_number,
        "name": student.user.full_name if student.user else "",
        "id": student.id
    }
    return json.dumps(payload, separators=(',', ':'))


def generate_student_qr_data_uri(student) -> str:
    """Generate base64 Data URI for a student's ID card QR code."""
    payload = generate_student_qr_payload(student)
    return qr_code_data_uri(payload)


def parse_student_qr_payload(qr_text: str) -> str | None:
    """Parse QR text, extracting student roll number/identifier from JSON or raw text."""
    if not qr_text:
        return None
    cleaned = qr_text.strip()
    # Try parsing as JSON first
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return str(data.get("student_id") or data.get("id") or "").strip() or None
    except Exception:
        pass

    # Fallback to raw string if not JSON
    return cleaned if len(cleaned) <= 60 else None
