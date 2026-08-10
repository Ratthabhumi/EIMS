import logging
from typing import Optional, List

import numpy as np

from app.models.result import OCRResult
from app.services.crop_service import get_image_rotations
from app.services.validator import extract_serial_number, extract_device_id

logger = logging.getLogger(__name__)

# None = not yet initialised; False = init failed
_ocr_engine = None
_ocr_engine_failed = False
_engine_type = None


def _get_ocr(language: str):
    global _ocr_engine, _ocr_engine_failed, _engine_type
    if _ocr_engine_failed:
        return None
    if _ocr_engine is None:
        # Try RapidOCR (ONNX version of PaddleOCR - 100% reliable across Python 3.8-3.14)
        try:
            from rapidocr_onnxruntime import RapidOCR
            logger.info("Initialising RapidOCR (ONNX engine)")
            _ocr_engine = RapidOCR()
            _engine_type = "rapid"
            return _ocr_engine
        except Exception:
            logger.debug("RapidOCR not installed, trying PaddleOCR fallback")

        # Fallback to PaddleOCR
        try:
            from paddleocr import PaddleOCR
            logger.info("Initialising PaddleOCR (lang=%s)", language)
            try:
                _ocr_engine = PaddleOCR(lang=language)
            except Exception:
                _ocr_engine = PaddleOCR(use_angle_cls=True, lang=language, show_log=False)
            _engine_type = "paddle"
            return _ocr_engine
        except Exception as exc:
            logger.error("Failed to initialize any OCR engine: %s", exc)
            _ocr_engine_failed = True
            return None
    return _ocr_engine


def run_ocr(image: np.ndarray, language: str = "en", use_gpu: bool = False) -> OCRResult:
    """Run OCR with multi-orientation scan until both S/N and ID are extracted."""
    if image is None:
        return OCRResult()

    rotations = get_image_rotations(image)
    best_result = OCRResult()

    for idx, rot_img in enumerate(rotations):
        res = _single_pass_ocr(rot_img, language)
        logger.info("OCR Pass %d (%d deg): SN=%s, ID=%s", idx + 1, idx * 90, res.serial_number, res.device_id)

        if res.is_complete:
            return res

        if res.serial_number and not best_result.serial_number:
            best_result.serial_number = res.serial_number
        if res.device_id and not best_result.device_id:
            best_result.device_id = res.device_id
        if res.raw_text:
            best_result.raw_text += f"\n--- {idx * 90}deg ---\n" + res.raw_text

        if best_result.is_complete:
            return best_result

    return best_result


def _single_pass_ocr(image: np.ndarray, language: str) -> OCRResult:
    engine = _get_ocr(language)
    if engine is None:
        return OCRResult()

    lines: list[str] = []
    if _engine_type == "rapid":
        try:
            res, _ = engine(image)
            if res:
                lines = [str(item[1]) for item in res if len(item) >= 2 and item[1]]
        except Exception:
            logger.exception("RapidOCR inference failed")
            return OCRResult()
    else:
        try:
            raw = engine.ocr(image, cls=True)
        except Exception:
            try:
                raw = engine.predict(image)
            except Exception:
                logger.exception("PaddleOCR inference failed")
                return OCRResult()
        lines = _parse_raw_results(raw)

    if not lines:
        return OCRResult()

    full_text = "\n".join(lines)
    return OCRResult(
        serial_number=_find_serial_number(lines),
        device_id=_find_device_id(lines),
        raw_text=full_text,
    )


def _parse_raw_results(raw) -> list[str]:
    """Parse PaddleOCR output robustly across v2.x and v3.x formats."""
    lines: list[str] = []
    if not raw:
        return lines

    # Flatten one level if results is [[...]] (v2 wraps in outer list)
    items = raw[0] if (isinstance(raw, list) and raw and isinstance(raw[0], list)) else raw

    for item in items:
        if not item:
            continue
        # v2.x: [bbox, (text, conf)]
        if isinstance(item, (list, tuple)) and len(item) >= 2:
            text_part = item[1]
            if isinstance(text_part, (list, tuple)) and len(text_part) >= 1:
                lines.append(str(text_part[0]))
                continue
            if isinstance(text_part, str):
                lines.append(text_part)
                continue
        # v3.x: dict with rec_text / text keys
        if isinstance(item, dict):
            text = item.get("rec_text") or item.get("text") or ""
            if text:
                lines.append(str(text))
    return lines


def _clean_ocr_confusion(text: str) -> str:
    """Clean common OCR typos (e.g., 'O' vs '0', 'I' vs '1') for networking labels."""
    text = text.upper().strip()
    text = text.replace(" ", "").replace("—", "-").replace("–", "-")
    text = text.replace("O", "0")
    return text


def _find_serial_number(lines: list[str]) -> Optional[str]:
    for i, line in enumerate(lines):
        upper = line.upper().strip()
        if "S/N" in upper or "SN" in upper or "SERIAL" in upper:
            inline = upper.replace("S/N:", "").replace("S/N", "").replace("SN:", "").replace("SN", "").strip()
            sn = extract_serial_number(inline) or extract_serial_number(_clean_ocr_confusion(inline))
            if sn:
                return sn
            if i + 1 < len(lines):
                sn = extract_serial_number(lines[i + 1]) or extract_serial_number(_clean_ocr_confusion(lines[i + 1]))
                if sn:
                    return sn

    for line in lines:
        sn = extract_serial_number(line) or extract_serial_number(_clean_ocr_confusion(line))
        if sn:
            return sn
    return None


def _find_device_id(lines: list[str]) -> Optional[str]:
    for i, line in enumerate(lines):
        upper = line.upper().strip()
        if "ID NO" in upper or "ID:" in upper or "ID" in upper:
            inline = (
                upper.replace("ID NO.", "")
                .replace("ID NO", "")
                .replace("ID:", "")
                .replace("ID", "")
                .strip()
            )
            did = extract_device_id(inline) or extract_device_id(_clean_ocr_confusion(inline))
            if did:
                return did
            if i + 1 < len(lines):
                did = extract_device_id(lines[i + 1]) or extract_device_id(_clean_ocr_confusion(lines[i + 1]))
                if did:
                    return did

    for line in lines:
        did = extract_device_id(line) or extract_device_id(_clean_ocr_confusion(line))
        if did:
            return did
    return None

