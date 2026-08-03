"""Face recognition service — InsightFace (ArcFace/MobileFaceNet) + ONNX Runtime.

Engine priority:
  1. InsightFace buffalo_sc  (ArcFace + RetinaFace — fastest, ~10ms/frame)
  2. InsightFace buffalo_l   (ArcFace larger — more accurate, ~25ms/frame)
  3. DeepFace Facenet512     (fallback if InsightFace not installed)

All paths keep the same public API so the rest of the codebase is unaffected.
Embeddings are always saved as float32 .npy files for fast reloading.
"""

from __future__ import annotations

import io
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import cv2
import numpy as np
from flask import current_app
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename

from app import db
from app.models import FaceEncoding, Student

log = logging.getLogger(__name__)

ALLOWED_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png"}

# ─────────────────────────────────────────────────────────────────────────────
# Exceptions / data classes
# ─────────────────────────────────────────────────────────────────────────────

class FaceRecognitionUnavailable(RuntimeError):
    pass


@dataclass
class FaceTrainingResult:
    image_path: str
    encoding_path: str


# ─────────────────────────────────────────────────────────────────────────────
# InsightFace engine  (singleton, lazy-loaded)
# ─────────────────────────────────────────────────────────────────────────────

_insight_app = None          # FaceAnalysis instance
_insight_model_name = None   # 'buffalo_sc' | 'buffalo_l'
_insight_available: bool | None = None


def _load_insightface(model_name: str = "buffalo_sc"):
    """Load InsightFace FaceAnalysis (singleton). Returns (app, True) or (None, False)."""
    global _insight_app, _insight_model_name, _insight_available

    if _insight_available is False:
        return None, False
    if _insight_app is not None and _insight_model_name == model_name:
        return _insight_app, True

    try:
        from insightface.app import FaceAnalysis
        fa = FaceAnalysis(
            name=model_name,
            providers=["CPUExecutionProvider"],
            # Download models to a writable cache dir
            root=str(Path.home() / ".insightface"),
        )
        # det_size=320 is faster; 640 more accurate
        fa.prepare(ctx_id=0, det_size=(320, 320))
        _insight_app = fa
        _insight_model_name = model_name
        _insight_available = True
        log.info("InsightFace '%s' loaded successfully.", model_name)
        return fa, True
    except Exception as exc:
        log.warning("InsightFace not available (%s). Falling back to DeepFace.", exc)
        _insight_available = False
        return None, False


def _get_insightface():
    """Return a ready FaceAnalysis app (buffalo_sc preferred, then buffalo_l)."""
    fa, ok = _load_insightface("buffalo_sc")
    if ok:
        return fa
    fa, ok = _load_insightface("buffalo_l")
    if ok:
        return fa
    return None


# ─────────────────────────────────────────────────────────────────────────────
# DeepFace fallback
# ─────────────────────────────────────────────────────────────────────────────

def _face_recognition():
    """Return (DeepFace, numpy) or raise FaceRecognitionUnavailable."""
    try:
        from deepface import DeepFace
        return DeepFace, np
    except ImportError as exc:
        raise FaceRecognitionUnavailable(
            "No face engine available. Install insightface or deepface."
        ) from exc


def _deepface_backend():
    """Best DeepFace detector available."""
    try:
        cascade = Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"
        if cascade.exists():
            return "opencv"
    except Exception:
        pass
    return "retinaface"


# ─────────────────────────────────────────────────────────────────────────────
# Image helpers
# ─────────────────────────────────────────────────────────────────────────────

def _bytes_to_bgr(image_bytes: bytes) -> np.ndarray | None:
    """Decode raw image bytes to a BGR uint8 numpy array (OpenCV format)."""
    try:
        arr = np.frombuffer(image_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        return img
    except Exception:
        return None


def _pil_to_bgr(image_bytes: bytes) -> np.ndarray | None:
    """PIL-based decode fallback (for JPEGs that OpenCV can't handle)."""
    try:
        from PIL import Image
        pil = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        return cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
    except Exception:
        return None


def _check_image_quality(gray: np.ndarray, min_laplacian: float = 50.0, min_brightness: float = 35.0) -> str | None:
    """Return an error string if image is too blurry/dark, else None."""
    try:
        lap_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        if lap_var < min_laplacian:
            return f"Image too blurry (sharpness={lap_var:.1f}, need >{min_laplacian}). Take a sharper photo."
        brightness = float(gray.mean())
        if brightness < min_brightness:
            return f"Image too dark (brightness={brightness:.1f}). Improve lighting."
    except Exception:
        pass
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Core embed functions
# ─────────────────────────────────────────────────────────────────────────────

def _embed_insightface(bgr: np.ndarray, fa) -> tuple[np.ndarray | None, int]:
    """Return (embedding float32 512-d, face_count) using InsightFace."""
    try:
        faces = fa.get(bgr)
        if not faces:
            return None, 0
        # Pick highest-confidence face
        face = max(faces, key=lambda f: float(f.det_score))
        emb = np.array(face.embedding, dtype=np.float32)
        return emb, len(faces)
    except Exception as exc:
        log.debug("InsightFace embed error: %s", exc)
        return None, 0


def _embed_deepface(bgr: np.ndarray) -> tuple[np.ndarray | None, int]:
    """Return (embedding float32, face_count) using DeepFace Facenet512 fallback."""
    try:
        DeepFace, _np = _face_recognition()
        backend = _deepface_backend()
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)

        # Count faces first
        try:
            extracted = DeepFace.extract_faces(rgb, detector_backend=backend, enforce_detection=True)
            face_count = len(extracted)
        except Exception:
            return None, 0

        # Get embedding
        try:
            result = DeepFace.represent(rgb, model_name="Facenet512",
                                        detector_backend=backend, enforce_detection=False)
        except TypeError:
            result = DeepFace.represent(rgb, model_name="Facenet512",
                                        detector_backend=backend, enforce_detection=False)
        if not result or not result[0].get("embedding"):
            return None, face_count
        emb = np.asarray(result[0]["embedding"], dtype=np.float32)
        return emb, face_count
    except FaceRecognitionUnavailable:
        raise
    except Exception as exc:
        log.debug("DeepFace embed error: %s", exc)
        return None, 0


def _embed(bgr: np.ndarray) -> tuple[np.ndarray | None, int]:
    """Return (embedding, face_count). Tries InsightFace then DeepFace."""
    fa = _get_insightface()
    if fa is not None:
        emb, cnt = _embed_insightface(bgr, fa)
        return emb, cnt
    return _embed_deepface(bgr)


# ─────────────────────────────────────────────────────────────────────────────
# Matching / scoring
# ─────────────────────────────────────────────────────────────────────────────

def _match_probe_to_known(
    probe: np.ndarray,
    usable_known: list[tuple[int, np.ndarray, str]],
    cosine_threshold: float = 0.35,
    euclidean_threshold: float = 1.1,
) -> dict | None:
    """Match probe embedding against known encodings.

    Uses cosine similarity + Euclidean distance combined score.
    InsightFace ArcFace embeddings: cosine_sim > 0.28 ≈ same person (tuned for buffalo_sc).
    """
    if not usable_known:
        return None

    known_arr = np.stack([item[1] for item in usable_known])  # (N, D)

    # Normalize both for cosine similarity
    probe_n = probe / (np.linalg.norm(probe) + 1e-9)
    norms = np.linalg.norm(known_arr, axis=1, keepdims=True) + 1e-9
    known_n = known_arr / norms

    cos_sims = known_n @ probe_n                          # (N,)
    dists = np.linalg.norm(known_arr - probe, axis=1)     # (N,)

    # Combined score (higher = better match)
    euc_scores = np.clip(1.0 - dists / 2.0, 0.0, 1.0)
    combined = 0.55 * cos_sims + 0.45 * euc_scores

    idx = int(np.argmax(combined))
    best_cos = float(cos_sims[idx])
    best_dist = float(dists[idx])
    best_combined = float(combined[idx])
    student_id, _, path = usable_known[idx]

    # Reject if neither metric passes
    if best_cos < cosine_threshold and best_dist > euclidean_threshold:
        return None

    confidence = min(1.0, max(0.0, best_combined))
    return {
        "student_id": student_id,
        "confidence": round(confidence, 4),
        "encoding_path": path,
        "cosine": round(best_cos, 4),
        "euclidean": round(best_dist, 4),
    }


def _get_thresholds(tolerance: float) -> tuple[float, float]:
    """Read thresholds from Flask config, with fallback for outside app context.

    For InsightFace ArcFace buffalo_sc:
      - cosine_threshold: 0.35 (same-person cosine >= 0.35)
      - euclidean_threshold: 1.2 (ArcFace 512-d embeddings have higher norms ~22)
    """
    try:
        cos_t = float(current_app.config.get("FACE_COSINE_THRESHOLD", 0.35))
        euc_t = float(current_app.config.get("FACE_EUCLIDEAN_THRESHOLD", 1.2))
    except RuntimeError:
        cos_t, euc_t = 0.35, 1.2
    return cos_t, euc_t


def _usable(known: list, probe_size: int) -> list:
    """Filter and convert known encodings to (sid, arr, path) with matching dim."""
    result = []
    for sid, enc, p in known:
        arr = np.asarray(enc, dtype=np.float32)
        if arr.ndim == 1 and arr.size == probe_size:
            result.append((sid, arr, p))
    return result


# ─────────────────────────────────────────────────────────────────────────────
# Public API — Training
# ─────────────────────────────────────────────────────────────────────────────

def _extension(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def validate_face_image(file: FileStorage) -> None:
    if not file or not file.filename:
        raise ValueError("Please choose an image file.")
    if _extension(file.filename) not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError("Only JPG, JPEG, and PNG images are allowed.")


def save_face_image(student: Student, file: FileStorage) -> Path:
    validate_face_image(file)
    base_dir = Path(current_app.root_path).parent / current_app.config["FACE_DATASET_FOLDER"]
    student_dir = base_dir / f"student_{student.id}"
    student_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4().hex}_{secure_filename(file.filename)}"
    image_path = student_dir / filename
    file.save(image_path)
    return image_path


def train_student_face(student: Student, image_path: Path) -> FaceTrainingResult:
    """Generate embedding for a single image and persist to DB + .npy file.

    Uses InsightFace if available (fast, <100ms), else DeepFace Facenet512.
    """
    bgr = cv2.imread(str(image_path))
    if bgr is None:
        image_path.unlink(missing_ok=True)
        raise ValueError("Unable to read image. Try another photo.")

    # Image quality gate
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    try:
        min_lap = float(current_app.config.get("FACE_MIN_LAPLACIAN_VARIANCE", 30))
        min_bright = float(current_app.config.get("FACE_MIN_BRIGHTNESS", 25))
    except RuntimeError:
        min_lap, min_bright = 30.0, 25.0

    quality_err = _check_image_quality(gray, min_laplacian=min_lap, min_brightness=min_bright)
    if quality_err:
        image_path.unlink(missing_ok=True)
        raise ValueError(quality_err)

    t0 = time.perf_counter()
    emb, face_count = _embed(bgr)
    elapsed_ms = (time.perf_counter() - t0) * 1000

    if face_count > 1:
        image_path.unlink(missing_ok=True)
        raise ValueError("Multiple faces detected. Upload an image with only this student.")
    if emb is None:
        image_path.unlink(missing_ok=True)
        raise ValueError("No face detected. Upload a clear front-facing photo.")

    log.debug("train_student_face: embed in %.1fms (dim=%d)", elapsed_ms, emb.size)

    # Save .npy
    encoding_dir = Path(current_app.root_path).parent / current_app.config["FACE_ENCODING_FOLDER"]
    encoding_dir.mkdir(parents=True, exist_ok=True)
    encoding_path = encoding_dir / f"student_{student.id}_{uuid4().hex}.npy"
    np.save(encoding_path, emb)

    record = FaceEncoding(
        student=student,
        image_path=str(image_path),
        encoding_path=str(encoding_path),
    )
    db.session.add(record)
    db.session.commit()
    clear_known_encodings()
    clear_per_session_cache()

    return FaceTrainingResult(image_path=str(image_path), encoding_path=str(encoding_path))


def upload_and_train_student_face(student: Student, file: FileStorage) -> FaceTrainingResult:
    image_path = save_face_image(student, file)
    try:
        return train_student_face(student, image_path)
    except FaceRecognitionUnavailable:
        image_path.unlink(missing_ok=True)
        raise
    except ValueError:
        image_path.unlink(missing_ok=True)
        raise
    except Exception as exc:
        image_path.unlink(missing_ok=True)
        current_app.logger.exception("Unhandled error during student face upload")
        raise ValueError(
            "Unable to train face image. Try another clear photo or contact support."
        ) from exc


def face_training_status() -> dict[str, int]:
    total_students = Student.query.count()
    trained_students = (
        db.session.query(FaceEncoding.student_id).distinct().count()
    )
    return {
        "total_students": total_students,
        "trained_students": trained_students,
        "pending_students": max(total_students - trained_students, 0),
        "total_encodings": FaceEncoding.query.count(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Encoding cache
# ─────────────────────────────────────────────────────────────────────────────

_known_encodings_cache: dict = {"data": None, "loaded_at": None}
_per_session_cache: dict = {}


def _load_all_known_encodings() -> list[tuple[int, np.ndarray, str]]:
    encodings = []
    records = FaceEncoding.query.join(Student).all()
    for record in records:
        enc_file = Path(record.encoding_path)
        if not enc_file.exists():
            current_app.logger.warning("Missing face encoding file: %s", enc_file)
            continue
        try:
            arr = np.load(enc_file).astype(np.float32)
            encodings.append((record.student_id, arr, str(enc_file)))
        except Exception as exc:
            current_app.logger.warning("Could not load encoding %s: %s", enc_file, exc)
    return encodings


def preload_known_encodings(force: bool = False, ttl_seconds: int | None = None) -> list:
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    loaded_at = _known_encodings_cache.get("loaded_at")
    if ttl_seconds is None:
        try:
            ttl_seconds = int(current_app.config.get("FACE_ENCODINGS_CACHE_TTL", 300))
        except Exception:
            ttl_seconds = 300

    should_refresh = force or _known_encodings_cache.get("data") is None or ttl_seconds <= 0
    if should_refresh:
        _known_encodings_cache["data"] = _load_all_known_encodings()
        _known_encodings_cache["loaded_at"] = now
        return _known_encodings_cache["data"]

    if loaded_at and isinstance(loaded_at, datetime):
        if now - loaded_at > timedelta(seconds=ttl_seconds):
            _known_encodings_cache["data"] = _load_all_known_encodings()
            _known_encodings_cache["loaded_at"] = now
    return _known_encodings_cache["data"]


def preload_known_encodings_for_session(session_id: int, force: bool = False, ttl_seconds: int | None = None) -> list:
    from datetime import datetime, timedelta
    if session_id is None:
        return preload_known_encodings(force=force, ttl_seconds=ttl_seconds)

    entry = _per_session_cache.get(session_id)
    now = datetime.now()
    if force or not entry:
        data = _load_all_known_encodings()
        _per_session_cache[session_id] = {"data": data, "loaded_at": now}
        return data

    loaded_at = entry.get("loaded_at")
    if ttl_seconds is None:
        try:
            ttl_seconds = int(current_app.config.get("FACE_ENCODINGS_CACHE_TTL", 300))
        except Exception:
            ttl_seconds = 300

    should_refresh = ttl_seconds <= 0
    if should_refresh:
        data = _load_all_known_encodings()
        _per_session_cache[session_id] = {"data": data, "loaded_at": now}
        return data

    if loaded_at and now - loaded_at > timedelta(seconds=ttl_seconds):
        data = _load_all_known_encodings()
        _per_session_cache[session_id] = {"data": data, "loaded_at": now}
        return data

    return entry.get("data")


def clear_per_session_cache(session_id: int | None = None) -> None:
    if session_id is None:
        _per_session_cache.clear()
    else:
        _per_session_cache.pop(session_id, None)


def clear_known_encodings() -> None:
    _known_encodings_cache["data"] = None
    _known_encodings_cache["loaded_at"] = None


def get_known_encodings_cache_info() -> dict:
    data = _known_encodings_cache.get("data")
    loaded_at = _known_encodings_cache.get("loaded_at")
    count = len(data) if data else 0
    return {"loaded_at": loaded_at, "count": count}


# ─────────────────────────────────────────────────────────────────────────────
# Public API — Recognition
# ─────────────────────────────────────────────────────────────────────────────

def recognize_face_from_image_bytes(image_bytes: bytes, tolerance: float = 0.55, known: list | None = None) -> dict | None:
    """Recognize a student from raw image bytes.

    Returns dict(student_id, confidence, encoding_path) or None.
    """
    bgr = _bytes_to_bgr(image_bytes)
    if bgr is None:
        bgr = _pil_to_bgr(image_bytes)
    if bgr is None:
        raise ValueError("Invalid image data")

    t0 = time.perf_counter()
    emb, face_count = _embed(bgr)
    log.debug("recognize single: embed %.1fms", (time.perf_counter() - t0) * 1000)

    if face_count > 1:
        raise ValueError("Multiple faces detected. Capture only one student at a time.")
    if emb is None:
        return None

    if known is None:
        known = preload_known_encodings()
    if not known:
        return None

    uk = _usable(known, emb.size)
    if not uk:
        return None

    cos_t, euc_t = _get_thresholds(tolerance)
    return _match_probe_to_known(emb, uk, cos_t, euc_t)


def recognize_face_from_frames(frames: list[bytes], tolerance: float = 0.55, known: list | None = None) -> dict | None:
    """Recognize a student from multiple frames with liveness check + multi-frame voting.

    - Liveness: pixel-diff between frame 1 and frame 2 must exceed threshold
    - Voting: each frame casts a vote; most-voted student wins
    - Confidence boosted when multiple frames agree
    """
    if not frames or len(frames) < 2:
        raise ValueError("At least two frames required for liveness check")

    t_start = time.perf_counter()

    # Decode all frames
    bgrs: list[np.ndarray] = []
    for b in frames[:3]:
        img = _bytes_to_bgr(b)
        if img is None:
            img = _pil_to_bgr(b)
        if img is not None:
            bgrs.append(img)
    if len(bgrs) < 2:
        return None

    # ── Liveness check ──────────────────────────────────────────────────────
    try:
        g0 = cv2.cvtColor(bgrs[0], cv2.COLOR_BGR2GRAY)
        g1 = cv2.cvtColor(bgrs[1], cv2.COLOR_BGR2GRAY)
        if g0.shape != g1.shape:
            g1 = cv2.resize(g1, (g0.shape[1], g0.shape[0]))
        diff_mean = float(cv2.absdiff(g0, g1).mean())
        try:
            liveness_thr = float(current_app.config.get("FACE_LIVENESS_DIFF_THRESHOLD", 2.0))
        except RuntimeError:
            liveness_thr = 2.0
        if diff_mean < liveness_thr:
            log.debug("Liveness fail: diff=%.3f < %.3f", diff_mean, liveness_thr)
            return None
    except Exception:
        pass  # non-fatal

    # ── Load known encodings ─────────────────────────────────────────────────
    if known is None:
        known = preload_known_encodings()
    if not known:
        return None

    cos_t, euc_t = _get_thresholds(tolerance)
    fa = _get_insightface()

    # ── Multi-frame voting ───────────────────────────────────────────────────
    votes: dict[int, list[float]] = {}
    best_results: dict[int, dict] = {}

    for bgr in bgrs:
        t0 = time.perf_counter()
        if fa is not None:
            emb, cnt = _embed_insightface(bgr, fa)
        else:
            emb, cnt = _embed_deepface(bgr)
        log.debug("frame embed %.1fms", (time.perf_counter() - t0) * 1000)

        if emb is None:
            continue

        uk = _usable(known, emb.size)
        if not uk:
            continue

        match = _match_probe_to_known(emb, uk, cos_t, euc_t)
        if match:
            sid = match["student_id"]
            votes.setdefault(sid, []).append(match["confidence"])
            if sid not in best_results or match["confidence"] > best_results[sid]["confidence"]:
                best_results[sid] = match

    log.debug("recognize_frames total %.1fms (%d frames)", (time.perf_counter() - t_start) * 1000, len(bgrs))

    if not votes:
        return None

    # Winner: most votes, tie-break by avg confidence
    winner_id = max(votes, key=lambda s: (len(votes[s]), sum(votes[s]) / len(votes[s])))
    winner = best_results[winner_id].copy()

    vote_count = len(votes[winner_id])
    avg_conf = sum(votes[winner_id]) / vote_count
    # +5% per extra agreeing frame
    winner["confidence"] = round(min(1.0, avg_conf * (1.0 + 0.05 * (vote_count - 1))), 4)
    winner["vote_count"] = vote_count
    return winner


# ─────────────────────────────────────────────────────────────────────────────
# Dataset capture helpers (student face self-registration)
# ─────────────────────────────────────────────────────────────────────────────

def save_dataset_image_bytes(student: Student, image_bytes: bytes) -> Path:
    """Validate and save a single webcam frame for the student dataset."""
    bgr = _bytes_to_bgr(image_bytes)
    if bgr is None:
        bgr = _pil_to_bgr(image_bytes)
    if bgr is None:
        raise ValueError("Invalid image data")

    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    try:
        min_lap = float(current_app.config.get("FACE_MIN_LAPLACIAN_VARIANCE", 30))
        min_bright = float(current_app.config.get("FACE_MIN_BRIGHTNESS", 25))
    except RuntimeError:
        min_lap, min_bright = 30.0, 25.0

    quality_err = _check_image_quality(gray, min_laplacian=min_lap, min_brightness=min_bright)
    if quality_err:
        raise ValueError(quality_err)

    # Face presence check (fast)
    fa = _get_insightface()
    if fa is not None:
        faces = fa.get(bgr)
        if not faces:
            raise ValueError("No face detected. Ensure your face is fully visible.")
        if len(faces) > 1:
            raise ValueError("Multiple faces detected. Ensure only your face is in the frame.")
    else:
        # DeepFace fallback
        try:
            DeepFace, _ = _face_recognition()
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            extracted = DeepFace.extract_faces(rgb, detector_backend=_deepface_backend(), enforce_detection=True)
            if len(extracted) > 1:
                raise ValueError("Multiple faces detected. Ensure only your face is in the frame.")
        except ValueError:
            raise
        except Exception:
            raise ValueError("No face detected. Ensure your face is fully visible and facing the camera.")

    base_dir = Path(current_app.root_path).parent / current_app.config["FACE_DATASET_FOLDER"]
    student_dir = base_dir / f"student_{student.id}"
    student_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid4().hex}.jpg"
    image_path = student_dir / filename
    cv2.imwrite(str(image_path), bgr, [cv2.IMWRITE_JPEG_QUALITY, 90])
    return image_path


def finalize_student_dataset(student: Student, min_images: int = 3, max_images: int = 30) -> dict:
    """Train encodings from the student's captured dataset images.

    min_images=3 for fast registration: just 3 good captures needed.
    """
    import hashlib

    base_dir = Path(current_app.root_path).parent / current_app.config["FACE_DATASET_FOLDER"]
    student_dir = base_dir / f"student_{student.id}"
    if not student_dir.exists():
        raise ValueError("No dataset images found for this student.")

    images = [p for p in sorted(student_dir.iterdir()) if p.suffix.lower() in {".jpg", ".jpeg", ".png"}]

    # Deduplicate
    unique = []
    seen: set[str] = set()
    for p in images:
        try:
            h = hashlib.sha256(p.read_bytes()).hexdigest()
        except Exception:
            continue
        if h not in seen:
            seen.add(h)
            unique.append(p)
        else:
            p.unlink(missing_ok=True)

    count = len(unique)
    if count < min_images:
        return {"trained": False, "reason": "not_enough_images", "count": count}

    trained, errors = [], []
    for img in unique[:max_images]:
        try:
            result = train_student_face(student, img)
            trained.append({"image": result.image_path, "encoding": result.encoding_path})
        except Exception as exc:
            errors.append({"image": str(img), "error": str(exc)})

    return {"trained": True, "trained_count": len(trained), "errors": errors, "count": count}
