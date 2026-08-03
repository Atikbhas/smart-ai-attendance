"""Professional Barcode & QR Code Scanner Service using OpenCV and zxing-cpp.

Supports:
  - 1D Barcodes: Code 128, Code 39, EAN-13, EAN-8, UPC-A, UPC-E, Codabar, ITF
  - 2D Barcodes: QR Code, Data Matrix, PDF417, Aztec
  - Preprocessing: Grayscale, CLAHE contrast enhancement, adaptive thresholding, sharpening, denoising
  - Detection of rotated, tilted, blurry, or low-light images
"""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass

import cv2
import numpy as np

log = logging.getLogger(__name__)


@dataclass
class BarcodeResult:
    text: str
    format: str
    confidence: float = 1.0
    bounding_box: list[tuple[int, int]] | None = None


def preprocess_frame(img: np.ndarray) -> list[np.ndarray]:
    """Generate preprocessed image variants for robust barcode detection under low-light or blur."""
    variants: list[np.ndarray] = [img]

    # Convert to grayscale if color
    if len(img.shape) == 3 and img.shape[2] == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img.copy()

    variants.append(gray)

    # Variant 1: Contrast Limited Adaptive Histogram Equalization (CLAHE) for low-light/uneven lighting
    try:
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        contrast_enhanced = clahe.apply(gray)
        variants.append(contrast_enhanced)
    except Exception:
        pass

    # Variant 2: Sharpening kernel
    try:
        kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]], dtype=np.float32)
        sharpened = cv2.filter2D(gray, -1, kernel)
        variants.append(sharpened)
    except Exception:
        pass

    # Variant 3: Otsu / Adaptive Thresholding
    try:
        thresh = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
        )
        variants.append(thresh)
    except Exception:
        pass

    return variants


def decode_barcode_image_bytes(image_bytes: bytes) -> BarcodeResult | None:
    """Decode 1D/2D Barcode or QR Code from raw image bytes.

    Tries zxing-cpp first for maximum accuracy and speed, then falls back to OpenCV.
    """
    if not image_bytes:
        return None

    try:
        arr = np.frombuffer(image_bytes, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    except Exception:
        return None

    if img is None or img.size == 0:
        return None

    # Preprocess variants
    variants = preprocess_frame(img)

    # 1. Try zxing-cpp if installed
    try:
        import zxingcpp

        for var in variants:
            results = zxingcpp.read_barcodes(var)
            if results:
                res = results[0]
                text = res.text.strip()
                if text:
                    fmt = str(res.format).replace("BarcodeFormat.", "")
                    # Extract polygon points if available
                    pts = None
                    try:
                        p = res.position
                        pts = [(int(p.top_left.x), int(p.top_left.y)),
                               (int(p.top_right.x), int(p.top_right.y)),
                               (int(p.bottom_right.x), int(p.bottom_right.y)),
                               (int(p.bottom_left.x), int(p.bottom_left.y))]
                    except Exception:
                        pts = None

                    return BarcodeResult(
                        text=text,
                        format=fmt,
                        confidence=0.98,
                        bounding_box=pts,
                    )
    except ImportError:
        pass
    except Exception as exc:
        log.debug("zxingcpp decode error: %s", exc)

    # 2. OpenCV Barcode / QR Fallback
    try:
        qr_detector = cv2.QRCodeDetector()
        for var in variants:
            data, bbox, _ = qr_detector.detectAndDecode(var)
            if data and data.strip():
                return BarcodeResult(
                    text=data.strip(),
                    format="QRCode",
                    confidence=0.90,
                )
    except Exception as exc:
        log.debug("OpenCV QRCodeDetector error: %s", exc)

    # 3. OpenCV BarcodeDetector fallback for 1D barcodes
    try:
        if hasattr(cv2, 'barcode') and hasattr(cv2.barcode, 'BarcodeDetector'):
            detector = cv2.barcode.BarcodeDetector()
            for var in variants:
                res = detector.detectAndDecode(var)
                if res and len(res) >= 2:
                    data = res[0]
                    if isinstance(data, (list, tuple)) and data:
                        text = str(data[0]).strip()
                        if text:
                            return BarcodeResult(
                                text=text,
                                format="1D_Barcode",
                                confidence=0.85,
                            )
    except Exception as exc:
        log.debug("OpenCV BarcodeDetector error: %s", exc)

    return None


def decode_barcode_data_url(data_url: str) -> BarcodeResult | None:
    """Decode barcode from a Base64 data URL string."""
    if not data_url or not isinstance(data_url, str):
        return None

    b64 = data_url.split(",", 1)[1] if "," in data_url else data_url
    try:
        image_bytes = base64.b64decode(b64)
        return decode_barcode_image_bytes(image_bytes)
    except Exception:
        return None


def generate_code128_data_uri(text: str) -> str:
    """Generate a Code128 Barcode as a Base64 Data URI."""
    if not text:
        return ""

    try:
        import io
        import barcode
        from barcode.writer import ImageWriter

        code128 = barcode.get("code128", str(text), writer=ImageWriter())
        buffer = io.BytesIO()
        code128.write(buffer, options={"module_height": 8.0, "font_size": 8, "text_distance": 3.0, "quiet_zone": 2.0})
        b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
        return f"data:image/png;base64,{b64}"
    except ImportError:
        return ""
    except Exception as exc:
        log.debug("Failed generating barcode data URI: %s", exc)
        return ""

