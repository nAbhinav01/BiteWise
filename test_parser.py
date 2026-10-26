"""
Tests for nutrient_parser.py  (run with:  python -m pytest -q   or   python test_parser.py)
Uses sample OCR text so no real photo is needed.
"""

from nutrient_parser import count_found, has_enough_nutrients, parse_nutrients

SPEC_SAMPLE = """Nutrition Facts (per 100 g)
Energy 450 kcal
Protein 8 g
Carbohydrate 60 g
Sugars 18 g
Fat 15 g
Saturated Fat 6 g
Fibre 4 g
Sodium 400 mg"""


def test_spec_sample():
    p = parse_nutrients(SPEC_SAMPLE)
    assert p["calories_kcal"] == 450
    assert p["protein_g"] == 8
    assert p["sugar_g"] == 18
    assert p["saturated_fat_g"] == 6
    assert p["fibre_g"] == 4
    assert p["sodium_mg"] == 400
    assert p["serving_basis"] == "per 100 g"
    assert p["normalized"] is True


def test_salt_converted_to_sodium():
    p = parse_nutrients("Per 100g\nSalt 1.0 g\nSugars 5 g\nProtein 3 g")
    assert p["sodium_mg"] == 400


def test_kj_converted_to_kcal():
    p = parse_nutrients("Per 100 g\nEnergy 1883 kJ\nSugars 5 g\nProtein 3 g")
    assert abs(p["calories_kcal"] - 450.0) < 1


def test_kj_and_kcal_prefers_kcal():
    p = parse_nutrients("Per 100 g\nEnergy 1883 kJ / 450 kcal\nSugars 5 g\nProtein 3 g")
    assert p["calories_kcal"] == 450


def test_serving_normalised_when_size_known():
    text = "Serving size 30 g\nPer serving\nEnergy 135 kcal\nSugars 6 g\nSodium 120 mg"
    p = parse_nutrients(text)
    assert p["normalized"] is True
    assert p["calories_kcal"] == 450
    assert p["sugar_g"] == 20
    assert p["sodium_mg"] == 400


def test_serving_without_size_is_flagged():
    p = parse_nutrients("Per serving\nEnergy 135 kcal\nSugars 6 g\nProtein 2 g")
    assert p["normalized"] is False
    assert p["sugar_g"] == 6
    assert any("could not be normalized" in n for n in p["notes"])


def test_two_columns_picks_per_100():
    text = "Per 100 g Per serving\nEnergy 450 kcal 135 kcal\nSugars 20 g 6 g\nProtein 8 g 2.4 g"
    p = parse_nutrients(text)
    assert p["sugar_g"] == 20 and p["calories_kcal"] == 450


def test_missing_nutrients_are_none():
    p = parse_nutrients("Per 100 g\nSugars 12 g")
    assert p["sugar_g"] == 12
    assert p["sodium_mg"] is None
    assert count_found(p) == 1
    assert not has_enough_nutrients(p)


def test_decimal_comma_and_percent_ignored():
    p = parse_nutrients("Per 100 g\nSugars 4,5 g 5%\nProtein 3 g 6%\nFibre 2 g")
    assert p["sugar_g"] == 4.5


def test_sat_fat_not_confused_with_total_fat():
    p = parse_nutrients("Per 100 g\nTotal Fat 15 g\nof which saturates 6 g\nSugars 1 g\nProtein 2 g")
    assert p["saturated_fat_g"] == 6


def test_empty_text():
    p = parse_nutrients("")
    assert count_found(p) == 0


# ---------------- Real-label style samples ----------------

INDIAN_LABEL = """NUTRITION INFORMATION (Approx.)
Per 100 g Per serve (30 g) %RDA* per serve
Energy (kcal) 520 156 8
Protein (g) 6.5 1.95 4
Carbohydrate (g) 62 18.6 7
Total Sugars (g) 28 8.4 -
Added Sugars (g) 25 7.5 -
Total Fat (g) 26 7.8 12
Saturated Fat (g) 12 3.6 16
Trans Fat (g) 0 0 -
Sodium (mg) 280 84 4"""


def test_indian_style_two_column_label():
    p = parse_nutrients(INDIAN_LABEL)
    assert p["calories_kcal"] == 520 and p["sugar_g"] == 28
    assert p["saturated_fat_g"] == 12 and p["sodium_mg"] == 280 and p["protein_g"] == 6.5
    assert p["fibre_g"] is None and p["normalized"] is True


def test_per_serve_only_is_scaled_to_per_100():
    text = """Serving size: 25 g
Nutrition facts per serve
Energy 130 kcal
Total Sugars 4 g
Saturated Fat 3 g
Sodium 150 mg"""
    p = parse_nutrients(text)
    assert p["normalized"] is True
    assert p["calories_kcal"] == 520 and p["sugar_g"] == 16
    assert p["saturated_fat_g"] == 12 and p["sodium_mg"] == 600


def test_ingredient_list_is_ignored():
    text = """Ingredients: Sugar, Salt, Emulsifier (322), Palm oil
Nutrition per 100 g
Energy 480 kcal
Sugars 12 g
Saturated fat 7 g
Sodium 300 mg"""
    p = parse_nutrients(text)
    assert p["sugar_g"] == 12 and p["sodium_mg"] == 300


def test_ocr_misread_100g_header():
    p = parse_nutrients("Per 1009\nEnergy 450 kcal\nSugars 18 g\nSodium 400 mg")
    assert p["serving_basis"] == "per 100 g" and p["normalized"] is True


def test_unit_in_label_name_kj():
    p = parse_nutrients("Per 100 g\nEnergy (kJ) 1883\nSugars (g) 5\nProtein (g) 3")
    assert abs(p["calories_kcal"] - 450) < 1
    p = parse_nutrients("Per 100 g\nEnergy (kJ/kcal) 1883/450\nSugars (g) 5\nProtein (g) 3")
    assert p["calories_kcal"] == 450


def test_two_nutrients_on_one_line():
    p = parse_nutrients("Per 100 g\nSaturated Fat 6 g Trans Fat 0 g\nSugars 5 g\nProtein 3 g")
    assert p["saturated_fat_g"] == 6


def test_unitless_sodium_in_grams():
    p = parse_nutrients("Per 100 g\nSodium 0.4\nSugars 5 g\nProtein 3 g")
    assert p["sodium_mg"] == 400


def test_implausible_value_is_dropped():
    p = parse_nutrients("Per 100 g\nSugars 180 g\nProtein 3 g\nFibre 2 g")
    assert p["sugar_g"] is None and any("implausible" in n for n in p["notes"])


def test_ocr_letter_digit_confusions():
    p = parse_nutrients("Per 100 g\nSugars lg\nSodium 5o mg\nProtein o.5 g")
    assert p["sugar_g"] == 1 and p["sodium_mg"] == 50 and p["protein_g"] == 0.5


def test_glued_columns_are_split():
    text = "Per 100g Per serve (25 g)\nEnergy (kcal) 480 120\nProtein (g) 71.8\nTotal Sugars (g) 205\nSaturated Fat (g) 8 2"
    p = parse_nutrients(text)
    assert p["protein_g"] == 7 and p["sugar_g"] == 20 and p["saturated_fat_g"] == 8


def test_g_misread_as_9_is_repaired():
    text = """Per 100g
Energy 560 kcal
Protein 15g
Total Sugars 39
Saturated Fat 13g
Dietary Fibre 59
Salt 2.39"""
    p = parse_nutrients(text)
    assert p["sugar_g"] == 3 and p["fibre_g"] == 5 and p["sodium_mg"] == 920


def test_9_repair_needs_evidence_of_printed_units():
    # No units anywhere on this label: leave "19" alone.
    p = parse_nutrients("Per 100 g\nSugars 19\nProtein 3\nFibre 2")
    assert p["sugar_g"] == 19


def test_label_glued_to_value():
    p = parse_nutrients("Per 100 g\nSugarslg\nProtein 13g\nSodium 5 mg\nEnergy 370 kcal")
    assert p["sugar_g"] == 1


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("PASS", name)
