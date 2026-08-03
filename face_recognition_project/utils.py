"""Utility functions for face recognition attendance system."""

import cv2
import numpy as np
import os
import pickle
from pathlib import Path
from typing import List, Tuple, Optional
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DATASET_DIR = Path("dataset")
MODELS_DIR = Path("models")
ENCODINGS_FILE = MODELS_DIR / "encodings.pkl"

DEFAULT_CAMERA_INDEX = 0
FRAME_WIDTH = 640
FRAME_HEIGHT = 480
PROCESSING_SCALE = 0.25
BLUR_THRESHOLD = 100.0
MIN_FACE_SIZE = 80
CAPTURE_COUNT = 50
CONFIDENCE_THRESHOLD = 0.6


def ensure_directories() -> None:
    """Create required directories if they don't exist."""
    DATASET_DIR.mkdir(parents=True, exist_ok=True)
    MODELS_DIR.mkdir(parents=True, exist_ok=True)


def get_person_dir(person_name: str) -> Path:
    """Get the directory path for a person's images."""
    safe_name = "".join(c for c in person_name if c.isalnum() or c in (' ', '-', '_')).strip()
    return DATASET_DIR / safe_name


def list_people() -> List[str]:
    """List all people in the dataset directory."""
    if not DATASET_DIR.exists():
        return []
    return [d.name for d in DATASET_DIR.iterdir() if d.is_dir()]


def count_images(person_name: str) -> int:
    """Count valid images for a person."""
    person_dir = get_person_dir(person_name)
    if not person_dir.exists():
        return 0
    valid_ext = {'.jpg', '.jpeg', '.png', '.bmp'}
    return sum(1 for f in person_dir.iterdir() if f.suffix.lower() in valid_ext)


def calculate_blur_score(image: np.ndarray) -> float:
    """Calculate the blur score of an image using Laplacian variance."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    return cv2.Laplacian(gray, cv2.CV_64F).var()


def is_blurry(image: np.ndarray, threshold: float = BLUR_THRESHOLD) -> bool:
    """Check if an image is blurry based on Laplacian variance."""
    return calculate_blur_score(image) < threshold


def resize_frame(frame: np.ndarray, scale: float = PROCESSING_SCALE) -> np.ndarray:
    """Resize frame for faster processing."""
    return cv2.resize(frame, (0, 0), fx=scale, fy=scale)


def draw_face_box(frame: np.ndarray, face_location: Tuple[int, int, int, int], 
                  name: str, confidence: float, scale: float = PROCESSING_SCALE) -> None:
    """Draw bounding box and label on frame."""
    top, right, bottom, left = face_location
    top = int(top / scale)
    right = int(right / scale)
    bottom = int(bottom / scale)
    left = int(left / scale)

    color = (0, 255, 0) if name != "Unknown" else (0, 0, 255)
    cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
    
    label = f"{name} ({confidence:.1%})" if name != "Unknown" else "Unknown"
    label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
    cv2.rectangle(frame, (left, top - label_size[1] - 10), 
                  (left + label_size[0] + 10, top), color, -1)
    cv2.putText(frame, label, (left + 5, top - 5), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)


def save_encodings(encodings: dict, filepath: Path = ENCODINGS_FILE) -> None:
    """Save face encodings to disk."""
    ensure_directories()
    with open(filepath, 'wb') as f:
        pickle.dump(encodings, f)
    logger.info(f"Encodings saved to {filepath}")


def load_encodings(filepath: Path = ENCODINGS_FILE) -> Optional[dict]:
    """Load face encodings from disk."""
    if not filepath.exists():
        logger.error(f"Encodings file not found: {filepath}")
        return None
    try:
        with open(filepath, 'rb') as f:
            encodings = pickle.load(f)
        logger.info(f"Loaded {len(encodings.get('encodings', []))} encodings for {len(encodings.get('names', []))} people")
        return encodings
    except Exception as e:
        logger.error(f"Failed to load encodings: {e}")
        return None


def get_image_paths(person_name: str) -> List[Path]:
    """Get all valid image paths for a person."""
    person_dir = get_person_dir(person_name)
    if not person_dir.exists():
        return []
    valid_ext = {'.jpg', '.jpeg', '.png', '.bmp'}
    return [f for f in person_dir.iterdir() if f.suffix.lower() in valid_ext]


def init_camera(camera_index: int = DEFAULT_CAMERA_INDEX) -> Optional[cv2.VideoCapture]:
    """Initialize camera capture."""
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        logger.error(f"Cannot open camera {camera_index}")
        return None
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
    return cap


def release_camera(cap: Optional[cv2.VideoCapture]) -> None:
    """Release camera resources."""
    if cap is not None:
        cap.release()
    cv2.destroyAllWindows()


def draw_progress_bar(frame: np.ndarray, progress: float, 
                      position: Tuple[int, int] = (20, 40),
                      size: Tuple[int, int] = (300, 25)) -> None:
    """Draw a progress bar on the frame."""
    x, y = position
    w, h = size
    cv2.rectangle(frame, (x, y), (x + w, y + h), (100, 100, 100), -1)
    fill_width = int(w * progress)
    cv2.rectangle(frame, (x, y), (x + fill_width, y + h), (0, 255, 0), -1)
    cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 255, 255), 2)
    cv2.putText(frame, f"{progress:.0%}", (x + w + 10, y + h - 2),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)


def draw_info_panel(frame: np.ndarray, lines: List[str], 
                    position: Tuple[int, int] = (20, 80)) -> None:
    """Draw information panel on frame."""
    x, y = position
    for i, line in enumerate(lines):
        cv2.putText(frame, line, (x, y + i * 25),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)