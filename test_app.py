"""
End-to-end tests of the real Streamlit app (AppTest): Upload -> Review -> Results.
OCR / parsing / scoring are real; Open Food Facts and the LLM are mocked.

Run:  python -m pytest -q test_app.py
"""

import os
import re
import tempfile

import pytest
from PIL import Image, ImageDraw, ImageFont
from streamlit.testing.v1 import AppTest

from ocr import is_tesseract_available

HARNESS = "_app_harness.py"
CHIPS = os.path.join("sample_images", "01_potato_chips_clean.png")
OATS = os.path.join("sample_images", "07_plain_oats_clean.png")

needs_all = pytest.mark.skipif(
    not (is_tesseract_available() and os.path.exists(CHIPS)), reason="Tesseract or sample images missing")


def _run(image=None, off=None, ai=None):
    import recommendations
    recommendations.clear_cache()
    for name, value in (("HARNESS_IMAGE", os.path.abspath(image) if image else None), ("HARNESS_OFF", off), ("HARNESS_AI", ai)):
        if value:
            os.environ[name] = value
        else:
            os.environ.pop(name, None)
    app = AppTest.from_file(HARNESS, default_timeout=180).run()
    assert not app.exception
    return app


def page(app) -> str:
    """All rendered HTML/markdown of the page as one string."""
    return " ".join(m.value for m in app.markdown)


def score(app) -> int:
    match = re.search(r'data-score="(\d+)"', page(app))
    assert match, "no score card on the page"
    return int(match.group(1))


def button(app, text):
    found = [b for b in app.button if text in b.label]
    assert found, f"button '{text}' not found; have {[b.label for b in app.button]}"
    return found[0]


def analyze(app):
    button(app, "Analyze").click().run()
    assert not app.exception and not app.error
    return app


def calculate(app):
    button(app, "Calculate").click().run()
    assert not app.exception
    return app


def _label_image(lines):
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 34)
    image = Image.new("RGB", (900, 120 + 80 * len(lines)), "white")
    draw = ImageDraw.Draw(image)
    for i, line in enumerate(lines):
        draw.text((40, 40 + 80 * i), line, font=font, fill="black")
    path = os.path.join(tempfile.mkdtemp(), "label.png")
    image.save(path)
    return path


def test_landing_page_and_no_image_warning():
    app = _run()
    assert "Scan Food Labels." in page(app) and "Upload your nutrition label" in page(app)
    for feature in ("OCR-powered", "Health Score", "Better choices"):
        assert feature in page(app)
    button(app, "Analyze").click().run()
    assert any("upload or capture an image first" in w.value for w in app.warning)
    assert not app.exception


@needs_all
def test_unhealthy_label_full_flow():
    app = _run(CHIPS)
    app.selectbox[0].select("Chips & Crisps")      # the label text has no product name to auto-detect
    analyze(app)
    # step 2: review
    assert "Check the values we read" in page(app) and "Analysis complete" in page(app)
    assert "OCR can misread numbers" in page(app)
    assert len(app.number_input) >= 6
    calculate(app)
    # step 3: results dashboard
    assert score(app) <= 40                                  # chips must not look healthy
    for text in ("Your health score", "Why this score?", "What lowered the score?", "What helped the score?", "Healthier alternatives"):
        assert text in page(app)
    assert "Mock AI explanation" in page(app)
    assert "Oats A" in page(app) and "Less" in page(app)     # alternative card + reason
    assert any("Scan Another Product" in b.label for b in app.button)


@needs_all
def test_healthy_label_scores_high():
    app = calculate(analyze(_run(OATS)))
    assert score(app) >= 81


@needs_all
def test_correcting_a_value_recalculates():
    app = analyze(_run(CHIPS))
    calculate(app)
    before = score(app)
    button(app, "Edit values").click().run()
    [n for n in app.number_input if n.label.startswith("Sodium")][0].set_value(20.0)
    calculate(app)
    assert score(app) > before


@needs_all
def test_drink_category_uses_drink_scoring():
    os.environ.pop("HARNESS_OFF", None)
    app = _run(CHIPS)
    app.selectbox[0].select("Soft Drinks & Beverages")
    calculate(analyze(app))
    assert "Drink scoring" in page(app)


@needs_all
def test_missing_serving_size_can_be_added():
    path = _label_image(["Nutrition facts per serve", "Energy 150 kcal", "Total Sugars 9 g",
                         "Saturated Fat 3.6 g", "Sodium 90 mg", "Protein 1.5 g"])
    app = analyze(_run(path))
    assert "serving size could not be read" in page(app)       # attention card names the problem
    calculate(app)
    assert "Estimate - limited data" in page(app)              # capped without the serving size
    button(app, "Add or fix values").click().run()
    [n for n in app.number_input if n.label.startswith("Serving size")][0].set_value(30.0)
    calculate(app)
    assert "Estimate - limited data" not in page(app)          # now converted to per 100 g
    assert score(app) <= 40


@needs_all
def test_no_alternatives_shows_friendly_state_with_retry():
    app = _run(CHIPS, off="empty")
    app.selectbox[0].select("Chips & Crisps")
    calculate(analyze(app))
    assert "No better match found" in page(app)
    assert any("Try again" in b.label for b in app.button)
    assert any("Search another category" in s.label for s in app.selectbox)


@needs_all
def test_ai_failure_shows_help_but_keeps_explanation():
    app = calculate(analyze(_run(CHIPS, ai="fail")))
    assert "Why this score?" in page(app)
    assert any("Why isn't the AI explanation showing" in e.label for e in app.expander)


@needs_all
def test_scan_another_product_restarts():
    app = _run(CHIPS)
    app.selectbox[0].select("Chips & Crisps")
    calculate(analyze(app))
    button(app, "Scan Another Product").click().run()
    assert not app.exception and "Upload your nutrition label" in page(app)


@needs_all
def test_unknown_category_asks_the_user_to_choose():
    app = calculate(analyze(_run(CHIPS)))        # category left on Auto-detect: label has no product name
    assert "Choose a category to compare" in page(app)
    assert any("Search another category" in s.label for s in app.selectbox)


RICH = os.path.join("sample_images", "rich_label_with_extras.png")


@needs_all
def test_brand_is_bitewise_with_search_logo():
    app = _run(CHIPS)
    html = page(app)
    assert "Wise</b>" in html and "NutriLens" not in html and 'aria-label="BiteWise logo"' in html


@needs_all
def test_extras_allergens_ingredients_and_serving_table():
    app = _run(RICH)
    app.selectbox[0].select("Biscuits & Cookies")
    app = calculate(analyze(app))
    html = page(app)
    assert any(e.label == "More nutrients" for e in app.expander)
    assert "Allergen alert" in html and "Milk" in html and "Soy" in html and "Wheat / gluten" in html
    assert "Ingredient analysis" in [e.label for e in app.expander]
    assert "Added sugars" in html                                   # ingredient note (sugar, glucose syrup)
    assert "Per serving (30 g)" in html and "% of daily intake" in html
    assert "Added Sugar" in html and "Potassium" in html
    assert "Not available" in html                                  # salt is not printed -> never shown as 0
    assert "Not available" in html and ">0 <small>g</small>" not in html.split("More nutrients")[0]


@needs_all
def test_extras_do_not_change_the_score():
    first = score(calculate(analyze(_run(RICH))))
    app = _run(RICH)
    app = analyze(app)
    for box in app.number_input:                                    # wipe every information-only value
        if box.key and box.key.startswith("nx_"):
            box.set_value(None)
    assert score(calculate(app)) == first


@needs_all
def test_ingredients_can_be_added_in_review():
    app = analyze(_run(CHIPS))                                      # chips label has no ingredient list
    app.text_area[0].set_value("Wheat flour, Sugar, Peanuts, Palm oil, Salt")
    app = calculate(app)
    html = page(app)
    assert "Allergen alert" in html and "Peanuts" in html and "Wheat / gluten" in html


@needs_all
def test_no_ingredients_gives_a_clear_message():
    app = calculate(analyze(_run(CHIPS)))
    assert "No ingredient list was read" in page(app)
