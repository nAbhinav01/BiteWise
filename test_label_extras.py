"""Unit tests for label_extras.py and the information-only nutrients in nutrient_parser.py."""

from label_extras import (analyze_ingredients, daily_share, detect_allergens, extract_ingredients,
                          per_serving, split_ingredients)
from nutrient_parser import parse_nutrients

LABEL = """NUTRITION FACTS
Per 100 g   Per serve (30 g)
Energy 480 kcal 144
Protein 7 g 2.1
Carbohydrate 60 g 18
Total Sugars 20 g 6
Includes 12 g Added Sugars
Total Fat 22 g 6.6
Saturated Fat 8 g 2.4
Trans Fat 0.1 g
Dietary Fibre 3 g
Sodium 400 mg
Potassium 150 mg
Calcium 120 mg
Iron 2.4 mg
Cholesterol 10 mg
Calories from Fat 200
"""


def test_extra_nutrients_are_read():
    p = parse_nutrients(LABEL)
    assert p["added_sugar_g"] == 12 and p["total_fat_g"] == 22 and p["carbs_g"] == 60
    assert p["trans_fat_g"] == 0.1 and p["potassium_mg"] == 150 and p["calcium_mg"] == 120
    assert p["iron_mg"] == 2.4 and p["cholesterol_mg"] == 10
    assert p["serving_size"] == 30


def test_total_fat_is_not_confused_with_saturated_trans_or_calories_from_fat():
    p = parse_nutrients("Per 100 g\nSaturated Fat 8 g\nTrans Fat 0.5 g\nCalories from Fat 200\nEnergy 300 kcal\nSugars 5 g\nProtein 3 g")
    assert p["total_fat_g"] is None and p["saturated_fat_g"] == 8 and p["trans_fat_g"] == 0.5


def test_missing_extras_are_none_never_zero():
    p = parse_nutrients("Per 100 g\nEnergy 300 kcal\nSugars 5 g\nProtein 3 g")
    assert p["potassium_mg"] is None and p["added_sugar_g"] is None and p["salt_g"] is None


def test_added_sugar_does_not_replace_total_sugar():
    p = parse_nutrients("Per 100 g\nEnergy 300 kcal\nTotal Sugars 20 g\nAdded Sugars 12 g\nProtein 3 g")
    assert p["sugar_g"] == 20 and p["added_sugar_g"] == 12


def test_glued_ocr_words_are_still_read():
    p = parse_nutrients("Per 100g\nEnergy 520 kcal\nTotalSugars 28g\nAdded Sugars 24g\nProtein 7 g")
    assert p["sugar_g"] == 28 and p["added_sugar_g"] == 24


def test_extras_are_scaled_with_the_serving_size():
    p = parse_nutrients("Serving size 50 g\nPer serving\nEnergy 100 kcal\nSugars 4 g\nProtein 2 g\nPotassium 100 mg")
    assert p["potassium_mg"] == 200 and p["sugar_g"] == 8


def test_ingredients_extracted_and_split():
    text = "NUTRITION\nEnergy 1 kcal\n\nIngredients: Wheat flour (maida), Sugar, Palm oil (palmolein, TBHQ),\nSalt.\nContains: Wheat.\nMfd by X"
    ing = extract_ingredients(text)
    assert ing.startswith("Wheat flour") and "Contains" not in ing
    assert split_ingredients(ing) == ["Wheat flour (maida)", "Sugar", "Palm oil (palmolein, TBHQ)", "Salt"]


def test_allergens_detected_and_no_false_positives():
    assert detect_allergens("milk solids, soy lecithin, wheat flour, peanuts") == ["Milk", "Peanuts", "Soy", "Wheat / gluten"]
    assert detect_allergens("rice, salt, turmeric") == []
    assert detect_allergens("until the end") == []                  # 'til' inside another word


def test_ingredient_notes_are_neutral_descriptions():
    notes = analyze_ingredients(["Refined wheat flour", "Sugar", "Palm oil", "Salt", "Aspartame"])
    titles = [n["title"] for n in notes]
    assert titles == ["Added sugars", "Refined grains", "Refined or hydrogenated fats", "Salt and sodium sources", "Artificial sweeteners"]
    assert not any("harm" in str(n["note"]).lower() or "bad" in str(n["note"]).lower() for n in notes)


def test_per_serving_and_daily_share():
    assert per_serving(20, 30) == 6.0 and per_serving(None, 30) is None and per_serving(20, None) is None
    assert daily_share("sodium_mg", 500) == 25 and daily_share("sodium_mg", None) is None
    assert daily_share("unknown_key", 5) is None
