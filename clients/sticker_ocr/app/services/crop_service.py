import logging
import time
from pathlib import Path
from typing import Optional, List

import cv2
import numpy as np

logger = logging.getLogger(__name__)

_MIN_ASPECT = 1.0
_MAX_ASPECT = 7.0
_MIN_AREA_RATIO = 0.03


def preprocess_image_for_ocr(img: np.ndarray) -> np.ndarray:
    """Enhance image contrast and sharpness for OCR readability."""
    if img is None:
        return img
    
    # Increase contrast using CLAHE (Contrast Limited Adaptive Histogram Equalization)
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    cl = clahe.apply(l)
    limg = cv2.merge((cl, a, b))
    enhanced = cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)
    return enhanced


def get_image_rotations(img: np.ndarray) -> List[np.ndarray]:
    """Return image in 4 orientations: 0, 90, 180, and 270 degrees."""
    if img is None:
        return []
    rot_90 = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
    rot_180 = cv2.rotate(img, cv2.ROTATE_180)
    rot_270 = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
    return [img, rot_90, rot_180, rot_270]


def read_image_safe(image_path: Path, timeout: float = 3.0) -> Optional[np.ndarray]:
    """Read an image safely using open('rb') + cv2.imdecode, retrying if locked/writing."""
    abs_path = Path(image_path).resolve()
    start_time = time.time()

    while time.time() - start_time < timeout:
        if not abs_path.exists():
            time.sleep(0.2)
            continue
        try:
            with open(abs_path, "rb") as f:
                content = f.read()
                if len(content) > 0:
                    data = np.frombuffer(content, dtype=np.uint8)
                    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
                    if img is not None:
                        return img
        except Exception:
            pass
        time.sleep(0.2)

    logger.warning("Cannot read image after retry timeout: %s", abs_path)
    return None


def crop_sticker(image_path: Path, padding: int = 20) -> Optional[np.ndarray]:
    """
    Detect the sticker region in the photo and return it as a numpy array.
    Falls back to the full image if detection fails.
    """
    img = read_image_safe(image_path)
    if img is None:
        return None

    region = _detect_sticker_region(img, padding)
    target = region if region is not None else img
    return preprocess_image_for_ocr(target)


def _detect_sticker_region(img: np.ndarray, padding: int) -> Optional[np.ndarray]:
    h, w = img.shape[:2]
    image_area = h * w

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    thresh = cv2.adaptiveThreshold(
        blurred, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        11, 2,
    )

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel, iterations=2)

    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    best = _best_contour(contours, image_area)
    if best is None:
        return None

    x, y, cw, ch = cv2.boundingRect(best)
    x1 = max(0, x - padding)
    y1 = max(0, y - padding)
    x2 = min(w, x + cw + padding)
    y2 = min(h, y + ch + padding)

    logger.debug("Cropped sticker: (%d,%d)→(%d,%d)", x1, y1, x2, y2)
    return img[y1:y2, x1:x2]


def _best_contour(contours: list, image_area: int) -> Optional[np.ndarray]:
    candidates = []
    for c in contours:
        area = cv2.contourArea(c)
        if area < image_area * _MIN_AREA_RATIO:
            continue
        x, y, cw, ch = cv2.boundingRect(c)
        if ch == 0:
            continue
        aspect = cw / ch
        # Support both vertical and horizontal stickers
        if _MIN_ASPECT <= aspect <= _MAX_ASPECT or (1.0 / _MAX_ASPECT) <= aspect <= (1.0 / _MIN_ASPECT):
            candidates.append((area, c))

    if not candidates:
        return None
    candidates.sort(key=lambda t: t[0], reverse=True)
    return candidates[0][1]

