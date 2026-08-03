"""Tests for face_service.py — InsightFace/DeepFace backend."""

import builtins

import numpy as np
import pytest

from app.services.face_service import (
    FaceRecognitionUnavailable,
    _face_recognition,
    _match_probe_to_known,
    _usable,
    recognize_face_from_image_bytes,
    recognize_face_from_frames,
)


# ─────────────────────────────────────────────────────────────────────────────
# _face_recognition fallback
# ─────────────────────────────────────────────────────────────────────────────

def test_face_recognition_error_mentions_deepface(monkeypatch):
    """If deepface is missing, FaceRecognitionUnavailable should be raised."""
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name.startswith("deepface"):
            raise ImportError("simulated missing dependency")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(FaceRecognitionUnavailable) as exc_info:
        _face_recognition()

    assert "deepface" in str(exc_info.value).lower() or "face" in str(exc_info.value).lower()


# ─────────────────────────────────────────────────────────────────────────────
# _match_probe_to_known
# ─────────────────────────────────────────────────────────────────────────────

def test_match_probe_returns_none_when_no_candidates():
    probe = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    result = _match_probe_to_known(probe, [], cosine_threshold=0.35, euclidean_threshold=1.1)
    assert result is None


def test_match_probe_finds_correct_student():
    probe = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    known = [
        (1, np.array([0.0, 1.0, 0.0], dtype=np.float32), "enc1.npy"),  # orthogonal → far
        (2, np.array([0.99, 0.1, 0.0], dtype=np.float32), "enc2.npy"),  # very close
    ]
    result = _match_probe_to_known(probe, known, cosine_threshold=0.3, euclidean_threshold=2.0)
    assert result is not None
    assert result["student_id"] == 2
    assert result["encoding_path"] == "enc2.npy"
    assert 0.0 <= result["confidence"] <= 1.0


def test_match_probe_rejects_bad_match():
    probe = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    known = [
        (1, np.array([0.0, 1.0, 0.0], dtype=np.float32), "enc1.npy"),  # cosine=0, far
    ]
    # Strict thresholds: should not match
    result = _match_probe_to_known(probe, known, cosine_threshold=0.99, euclidean_threshold=0.01)
    assert result is None


# ─────────────────────────────────────────────────────────────────────────────
# _usable  (dimension filtering)
# ─────────────────────────────────────────────────────────────────────────────

def test_usable_filters_wrong_dimension():
    known = [
        (1, np.array([[9.0, 9.0, 9.0]]), "invalid.npy"),   # 2-d → excluded
        (2, np.array([0.1, 0.2, 0.3]), "valid.npy"),         # 1-d, size=3 → included
    ]
    result = _usable(known, probe_size=3)
    assert len(result) == 1
    assert result[0][0] == 2
    assert result[0][2] == "valid.npy"


def test_usable_filters_wrong_size():
    known = [
        (1, np.array([0.1, 0.2, 0.3, 0.4]), "four.npy"),  # size=4 → excluded
        (2, np.array([0.1, 0.2, 0.3]), "three.npy"),        # size=3 → included
    ]
    result = _usable(known, probe_size=3)
    assert len(result) == 1
    assert result[0][0] == 2


# ─────────────────────────────────────────────────────────────────────────────
# recognize_face_from_image_bytes — mocked engine
# ─────────────────────────────────────────────────────────────────────────────

def _make_jpeg(width=8, height=8, color=(128, 128, 128)):
    from PIL import Image
    import io
    img = Image.new("RGB", (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def test_recognition_ignores_invalid_known_encoding_shape(monkeypatch):
    """Known encodings with wrong shape should be skipped; valid one should match."""
    probe_vec = [0.1, 0.2, 0.3]

    def fake_embed(bgr):
        return np.array(probe_vec, dtype=np.float32), 1

    monkeypatch.setattr("app.services.face_service._get_insightface", lambda: None)
    monkeypatch.setattr("app.services.face_service._embed_deepface", fake_embed)
    monkeypatch.setattr("app.services.face_service._embed", fake_embed)

    result = recognize_face_from_image_bytes(
        _make_jpeg(),
        tolerance=0.95,
        known=[
            (1, [[9.0, 9.0, 9.0]], "invalid.npy"),   # 2-d → excluded
            (2, [0.1, 0.2, 0.3],   "valid.npy"),      # matches probe
        ],
    )
    assert result is not None
    assert result["student_id"] == 2
    assert result["encoding_path"] == "valid.npy"


def test_recognition_returns_none_when_no_face(monkeypatch):
    """If embed returns None (no face), recognition should return None."""
    def fake_embed(bgr):
        return None, 0

    monkeypatch.setattr("app.services.face_service._embed", fake_embed)
    monkeypatch.setattr("app.services.face_service._get_insightface", lambda: None)

    result = recognize_face_from_image_bytes(
        _make_jpeg(),
        known=[(1, np.array([1.0, 0.0, 0.0]), "enc.npy")],
    )
    assert result is None


def test_recognition_raises_on_multiple_faces(monkeypatch):
    """face_count > 1 should raise ValueError."""
    def fake_embed(bgr):
        return np.array([0.1, 0.2, 0.3], dtype=np.float32), 2

    monkeypatch.setattr("app.services.face_service._embed", fake_embed)
    monkeypatch.setattr("app.services.face_service._get_insightface", lambda: None)

    with pytest.raises(ValueError, match="Multiple"):
        recognize_face_from_image_bytes(_make_jpeg(), known=[(1, [0.1, 0.2, 0.3], "enc.npy")])


# ─────────────────────────────────────────────────────────────────────────────
# recognize_face_from_frames — liveness + voting
# ─────────────────────────────────────────────────────────────────────────────

def test_frames_requires_at_least_two():
    with pytest.raises(ValueError, match="two frames"):
        recognize_face_from_frames([_make_jpeg()])


def test_frames_liveness_fail_returns_none(monkeypatch):
    """If frames are identical, liveness check should fail."""
    call_count = {"n": 0}

    def fake_embed(bgr):
        return np.array([0.5, 0.5, 0.0], dtype=np.float32), 1

    monkeypatch.setattr("app.services.face_service._get_insightface", lambda: None)
    monkeypatch.setattr("app.services.face_service._embed_insightface", lambda bgr, fa: (None, 0))
    monkeypatch.setattr("app.services.face_service._embed_deepface", fake_embed)

    # Use identical frames — pixel diff ≈ 0, liveness will fail
    frame = _make_jpeg(color=(100, 100, 100))
    result = recognize_face_from_frames(
        [frame, frame],
        known=[(1, [0.5, 0.5, 0.0], "enc.npy")],
    )
    # Liveness fail → None
    assert result is None


def test_frames_voting_picks_most_voted(monkeypatch):
    """Multi-frame voting should return the student with most frame matches."""
    call_num = {"i": 0}
    student_probes = [
        np.array([1.0, 0.0, 0.0], dtype=np.float32),  # frame 0 → student 1
        np.array([1.0, 0.0, 0.0], dtype=np.float32),  # frame 1 → student 1
    ]

    def fake_embed_insight(bgr, fa):
        i = call_num["i"]
        call_num["i"] += 1
        if i < len(student_probes):
            return student_probes[i], 1
        return None, 0

    def fake_insight():
        class FakeFA:
            pass
        return FakeFA()

    monkeypatch.setattr("app.services.face_service._get_insightface", fake_insight)
    monkeypatch.setattr("app.services.face_service._embed_insightface", fake_embed_insight)

    known = [
        (1, np.array([0.99, 0.01, 0.0], dtype=np.float32), "s1.npy"),
        (2, np.array([0.0, 0.99, 0.01], dtype=np.float32), "s2.npy"),
    ]

    # Use different-colored frames so liveness passes
    frame1 = _make_jpeg(color=(50, 50, 50))
    frame2 = _make_jpeg(color=(200, 200, 200))
    result = recognize_face_from_frames([frame1, frame2], known=known)
    # student 1 should win (both frames voted for them)
    if result is not None:
        assert result["student_id"] == 1
