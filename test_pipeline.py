"""Tests for pipeline.py helpers and an OCR -> parse -> score run on a rendered label."""

import os
import tempfile

from pipeline import AUTO_DETECT, detect_sweeteners, is_drink, resolve_category


def test_resolve_category():
    assert resolve_category(AUTO_DETECT, "crunchy corn flakes") == "Breakfast Cereals"
    assert resolve_category("Fruit Juices", "anything") == "Fruit Juices"
    assert resolve_category("Other / Not sure", "corn flakes") is None


def test_is_drink():
    assert is_drink("Soft Drinks & Beverages", "per 100 g")
    assert not is_drink("Snacks", "per 100 ml")
    assert is_drink(None, "per 100 ml") and not is_drink(None, "per 100 g")


def test_detect_sweeteners():
    assert detect_sweeteners("Ingredients: water, Aspartame, flavour")
    assert not detect_sweeteners("Ingredients: water, sugar")


def test_vote_prefers_explicit_unit_then_majority():
    from pipeline import _vote
    assert _vote([(3.59, False), (3.5, True)]) == 3.5
    assert _vote([(5, True), (6, True), (6, True)]) == 6
    assert _vote([(None, False), (None, False)]) is None


def test_full_image_pipeline():
    """Render a label, push it through OCR -> parser -> score."""
    from PIL import Image, ImageDraw, ImageFont
    from health_score import calculate_health_score
    from pipeline import run_ocr_pipeline

    font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    if not os.path.exists(font_path):
        return  # skip on machines without this font
    font = ImageFont.truetype(font_path, 34)
    img = Image.new("RGB", (900, 700), "white")
    draw = ImageDraw.Draw(img)
    y = 40
    for line in ["Nutrition Facts per 100 g", "Energy 536 kcal", "Protein 6 g", "Sugars 0.5 g",
                 "Saturated Fat 3.5 g", "Fibre 4 g", "Sodium 600 mg"]:
        draw.text((40, y), line, font=font, fill="black")
        y += 80
    path = os.path.join(tempfile.mkdtemp(), "label.png")
    img.save(path)
    with open(path, "rb") as handle:
        ocr = run_ocr_pipeline(handle)
    parsed = ocr["parsed"]
    result = calculate_health_score(parsed)
    assert parsed["sodium_mg"] == 600 and parsed["calories_kcal"] == 536
    assert result["score"] <= 40  # potato-chip-like label must NOT look healthy


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f(); print("PASS", n)
