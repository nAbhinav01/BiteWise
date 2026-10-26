"""Offline tests for category_detector.py and recommendations.py (no internet needed)."""

from unittest.mock import patch

from category_detector import detect_category, get_off_tag
import recommendations as rec


def test_detect_category():
    assert detect_category("Crunchy corn flakes with oats") == "Breakfast Cereals"
    assert detect_category("Orange juice from concentrate") == "Fruit Juices"
    assert detect_category("zzz nothing here") is None
    assert get_off_tag("Biscuits & Cookies") == "en:biscuits"


def test_nutriments_conversion():
    p = rec.nutriments_to_parsed({"energy-kcal_100g": 400, "sugars_100g": 10, "sodium_100g": 0.4})
    assert p["sodium_mg"] == 400 and p["calories_kcal"] == 400


def test_find_alternatives_filters_and_sorts():
    good = {"product_name": "Good", "brands": "A", "nutriscore_grade": "a", "code": "1", "nutriments": {
        "energy-kcal_100g": 100, "sugars_100g": 2, "saturated-fat_100g": 0.5,
        "sodium_100g": 0.05, "fiber_100g": 6, "proteins_100g": 8}}
    bad = {"product_name": "Bad", "brands": "B", "code": "2", "nutriments": {
        "energy-kcal_100g": 540, "sugars_100g": 50, "saturated-fat_100g": 15,
        "sodium_100g": 0.9, "fiber_100g": 0, "proteins_100g": 2}}
    with patch.object(rec, "_fetch_products", return_value=(good, bad)):
        items, msg = rec.find_alternatives("en:x", current_score=50)
    assert [i["Product"] for i in items] == ["Good"] and msg


def test_network_failure_is_graceful():
    import requests
    with patch.object(rec, "_fetch_products", side_effect=requests.exceptions.ConnectionError):
        items, msg = rec.find_alternatives("en:x", 50)
    assert items == [] and "Open Food Facts" in msg


if __name__ == "__main__":
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            f(); print("PASS", n)
