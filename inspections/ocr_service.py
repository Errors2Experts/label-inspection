
import json
import tempfile
from pathlib import Path

from paddleocr import PaddleOCR


_ocr_engine = None


def get_ocr_engine():
    """Create the PaddleOCR engine once and reuse it."""

    global _ocr_engine

    if _ocr_engine is None:
        _ocr_engine = PaddleOCR(
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            enable_mkldnn=False,
        )

    return _ocr_engine


def _get_result_data(result):
    """Normalize PaddleOCR 3.x output into a dictionary."""

    if isinstance(result, dict):
        data = result
    else:
        data = getattr(result, "json", {})

        if callable(data):
            data = data()

    # Some versions may expose JSON as a string.
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except (json.JSONDecodeError, TypeError):
            return {}

    if not isinstance(data, dict):
        return {}

    nested = data.get("res")
    return nested if isinstance(nested, dict) else data


def extract_text(image_field):
    """
    Extract text and average recognition confidence from a Django ImageField.

    Returns:
        {"raw_text": str, "confidence": float | None}
    """

    engine = get_ocr_engine()
    suffix = Path(image_field.name).suffix or ".jpg"
    temp_path = None

    try:
        # delete=False is safer when PaddleOCR must reopen the file on Windows.
        with tempfile.NamedTemporaryFile(
            suffix=suffix,
            delete=False,
        ) as temporary_file:
            temp_path = temporary_file.name

            with image_field.open("rb") as source:
                while True:
                    chunk = source.read(1024 * 1024)
                    if not chunk:
                        break
                    temporary_file.write(chunk)

        # The temporary file is closed before PaddleOCR reads it.
        results = engine.predict(input=temp_path)

        extracted_lines = []
        confidence_scores = []

        for result in results or []:
            data = _get_result_data(result)

            for text in data.get("rec_texts", []) or []:
                if text and str(text).strip():
                    extracted_lines.append(str(text).strip())

            for score in data.get("rec_scores", []) or []:
                try:
                    score = float(score)
                    if 0 <= score <= 1:
                        confidence_scores.append(score)
                except (TypeError, ValueError):
                    continue

        confidence = (
            sum(confidence_scores) / len(confidence_scores)
            if confidence_scores
            else None
        )

        return {
            "raw_text": "\n".join(extracted_lines),
            "confidence": confidence,
        }

    finally:
        if temp_path:
            Path(temp_path).unlink(missing_ok=True)
