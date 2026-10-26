"""
Sample-data tests.

  * Scoring benchmark: every product in data/sample_data.csv must land on the
    right side (no OCR involved).
  * Image tests: the labelled images in sample_images/ are pushed through the
    real OCR + parser + scoring pipeline. Skipped if Tesseract is missing or
    the images have not been generated (python generate_sample_images.py).

Run:  python -m pytest -q test_samples.py
"""

import csv
import os

import pytest

from evaluate import value_matches, verdict_ok
from health_score import calculate_health_score
from nutrient_parser import NUTRIENT_KEYS
from ocr import is_tesseract_available

GROUND_TRUTH = os.path.join("sample_images", "ground_truth.csv")
BENCHMARK = os.path.join("data", "sample_data.csv")


def _read(path):
    with open(path) as handle:
        return list(csv.DictReader(handle))


def test_scoring_benchmark_all_products():
    wrong = []
    for row in _read(BENCHMARK):
        values = {k: (float(row[k]) if row[k] != "" else None) for k in NUTRIENT_KEYS}
        values["normalized"] = True
        score = calculate_health_score(values, is_drink=bool(int(row["is_drink"])))["score"]
        if row["expected"] == "moderate":
            ok = score is not None and 21 <= score <= 80
        else:
            ok = verdict_ok(score, row["expected"])
        if not ok:
            wrong.append((row["product"], score, row["expected"]))
    assert not wrong, f"Benchmark products on the wrong side: {wrong}"


needs_images = pytest.mark.skipif(
    not (is_tesseract_available() and os.path.exists(GROUND_TRUTH)),
    reason="Tesseract or sample images not available",
)


@pytest.fixture(scope="module")
def results():
    """Run the OCR pipeline once per image and cache the outcome."""
    from pipeline import run_ocr_pipeline
    out = []
    for row in _read(GROUND_TRUTH):
        with open(os.path.join("sample_images", row["file"]), "rb") as handle:
            parsed = run_ocr_pipeline(handle)["parsed"]
        truth = {k: float(row[k]) for k in NUTRIENT_KEYS if row[k] != ""}
        correct = sum(1 for k, v in truth.items() if value_matches(parsed[k], v))
        score = calculate_health_score(parsed, is_drink=bool(int(row["is_drink"])))["score"]
        out.append((row, correct, len(truth), score))
    return out


@needs_images
def test_clean_labels_extract_everything(results):
    clean = [r for r in results if r[0]["kind"] == "clean"]
    assert sum(r[1] for r in clean) == sum(r[2] for r in clean)


@needs_images
def test_photo_labels_extraction_at_least_90_percent(results):
    photos = [r for r in results if r[0]["kind"] == "photo"]
    assert sum(r[1] for r in photos) / sum(r[2] for r in photos) >= 0.90


@needs_images
def test_no_unhealthy_label_is_called_healthy(results):
    """The most important safety property of the project."""
    for row, _correct, _total, score in results:
        if row["verdict"] == "unhealthy":
            assert score is not None and score <= 60, f"{row['file']} scored {score}"


@needs_images
def test_every_clean_label_gets_correct_verdict(results):
    for row, _c, _t, score in results:
        if row["kind"] == "clean":
            assert verdict_ok(score, row["verdict"]), f"{row['file']}: score {score}"


@needs_images
def test_per_serving_photo_is_not_mixed_with_per_100_values(results):
    """Regression: OCR passes with different label bases must not vote together."""
    for row, correct, total, _score in results:
        if row["file"].startswith("11_cookies_per_serving_photo"):
            assert correct == total
