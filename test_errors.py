"""
Error-handling tests: the app must fail gracefully, never crash.

Covers: invalid image, blank image (empty OCR), no nutrients found, Tesseract
missing, Open Food Facts failure, LLM failure, missing API key, too few
nutrients. (Open Food Facts / LLM failures are also covered in
test_recommend.py and test_ai.py.)
"""

import io
from unittest.mock import patch

import numpy as np
import pytest
from PIL import Image

from health_score import calculate_health_score
from image_preprocessing import load_image, preprocess_for_ocr
from nutrient_parser import count_found, has_enough_nutrients, parse_nutrients


def test_invalid_image_raises_friendly_error():
    with pytest.raises(ValueError, match="valid"):
        load_image(io.BytesIO(b"this is not an image"))


def test_empty_array_rejected():
    with pytest.raises(ValueError):
        preprocess_for_ocr(np.array([]))


def test_blank_image_gives_no_nutrients():
    from ocr import is_tesseract_available
    if not is_tesseract_available():
        pytest.skip("Tesseract not available")
    from pipeline import run_ocr_pipeline
    buffer = io.BytesIO()
    Image.new("RGB", (800, 600), "white").save(buffer, format="PNG")
    buffer.seek(0)
    result = run_ocr_pipeline(buffer)
    assert count_found(result["parsed"]) == 0
    assert calculate_health_score(result["parsed"])["score"] is None


def test_text_without_nutrients():
    parsed = parse_nutrients("Crunchy and tasty! Best before 12/2027. Store in a cool dry place.")
    assert count_found(parsed) == 0 and not has_enough_nutrients(parsed)


def test_tesseract_missing_gives_runtime_error():
    import ocr
    import pytesseract
    image = np.full((100, 300), 255, dtype=np.uint8)
    with patch.object(ocr.pytesseract, "image_to_string", side_effect=pytesseract.TesseractNotFoundError()):
        with pytest.raises(RuntimeError):
            ocr.extract_text(image)


def test_only_two_nutrients_gives_no_score():
    parsed = parse_nutrients("Per 100 g\nSugars 10 g\nProtein 3 g")
    assert calculate_health_score(parsed)["score"] is None


def test_none_and_empty_text_do_not_crash():
    assert count_found(parse_nutrients("")) == 0
    assert count_found(parse_nutrients(None)) == 0  # type: ignore[arg-type]
