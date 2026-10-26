"""
Label extras: ingredients, allergens, ingredient notes and daily-intake share.
------------------------------------------------------------------------------
Everything here is plain, deterministic Python (no AI) and is INFORMATION ONLY:
none of it changes the Health Score.

  * extract_ingredients(text)   -> the ingredient list printed on the label
  * detect_allergens(text)      -> allergens mentioned (shown as a separate warning)
  * analyze_ingredients(items)  -> neutral notes (added sugars, refined oils ...)
  * per_serving(...) / daily_share(...) -> per-serving amounts and % of a
    reference daily intake, only when the serving size is known

Wording rule: an ingredient is described, never called "harmful".
"""

import re
from typing import Dict, List, Optional

# --------------------------------------------------------------------------
# Ingredients
# --------------------------------------------------------------------------
_STOP = re.compile(
    r"\b(?:contains|may\s+contain|allergen|allergy|nutrition(?:al)?\s+(?:facts|information|value)|"
    r"manufactured|marketed|best\s+before|mfd|net\s+(?:wt|weight|qty|quantity)|fssai|store\s+in|"
    r"directions|batch|mrp)\b",
    re.IGNORECASE,
)


def extract_ingredients(raw_text: str) -> str:
    """Return the ingredient list text found in the OCR text ('' if none)."""
    if not raw_text:
        return ""
    text = raw_text.replace("\r", "\n")
    match = re.search(r"ingredients?\s*[:\-]?", text, re.IGNORECASE)
    if match is None:
        return ""
    tail = text[match.end():]
    paragraph = re.split(r"\n\s*\n", tail, maxsplit=1)[0]
    stop = _STOP.search(paragraph)
    if stop:
        paragraph = paragraph[: stop.start()]
    paragraph = " ".join(paragraph.split())
    return paragraph.strip(" .;:-")[:900]


def split_ingredients(ingredient_text: str) -> List[str]:
    """Split on commas that are not inside brackets."""
    items, depth, current = [], 0, ""
    for ch in ingredient_text:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth = max(0, depth - 1)
        if ch in ",;" and depth == 0:
            if current.strip():
                items.append(current.strip())
            current = ""
        else:
            current += ch
    if current.strip():
        items.append(current.strip())
    return items


# --------------------------------------------------------------------------
# Allergens
# --------------------------------------------------------------------------
ALLERGEN_WORDS: Dict[str, List[str]] = {
    "Milk": ["milk", "whey", "casein", "caseinate", "lactose", "butter", "cream", "ghee", "cheese", "curd", "paneer", "milk solids"],
    "Peanuts": ["peanut", "peanuts", "groundnut", "groundnuts"],
    "Tree nuts": ["almond", "almonds", "cashew", "cashews", "walnut", "walnuts", "hazelnut", "hazelnuts",
                  "pistachio", "pistachios", "pecan", "macadamia", "tree nut", "tree nuts"],
    "Soy": ["soy", "soya", "soybean", "soybeans"],
    "Wheat / gluten": ["wheat", "gluten", "maida", "atta", "semolina", "suji", "barley", "rye"],
    "Egg": ["egg", "eggs", "albumen", "mayonnaise"],
    "Fish": ["fish", "anchovy", "anchovies"],
    "Shellfish": ["prawn", "prawns", "shrimp", "crab", "lobster", "shellfish"],
    "Sesame": ["sesame", "til"],
    "Mustard": ["mustard"],
}


def detect_allergens(text: str) -> List[str]:
    """Allergen groups mentioned in the ingredient / allergen text, in a fixed order."""
    lowered = (text or "").lower()
    found = []
    for group, words in ALLERGEN_WORDS.items():
        if any(re.search(r"(?<![a-z])" + re.escape(w) + r"(?![a-z])", lowered) for w in words):
            found.append(group)
    return found


def allergen_source_text(raw_text: str, ingredient_text: str) -> str:
    """Ingredient text plus any 'Contains ...' / 'May contain ...' statement on the label."""
    parts = [ingredient_text or ""]
    for match in re.finditer(r"(?:may\s+contain|contains|allergen[^:\n]*:)\s*([^\n.]{0,160})", raw_text or "", re.IGNORECASE):
        parts.append(match.group(1))
    return " ".join(parts)


# --------------------------------------------------------------------------
# Ingredient notes (neutral wording)
# --------------------------------------------------------------------------
_NOTE_RULES = [
    ("Added sugars", ["sugar", "glucose", "fructose", "dextrose", "syrup", "jaggery", "honey", "maltodextrin", "invert", "molasses"],
     "These add sugar on top of what is naturally in the food. Worth noticing if you are limiting sugar."),
    ("Refined grains", ["maida", "refined wheat flour", "refined flour", "white flour", "wheat flour", "enriched flour"],
     "Refined flour has less fibre than whole grain. Whole grains usually keep you full for longer."),
    ("Refined or hydrogenated fats", ["palm oil", "palmolein", "hydrogenated", "vanaspati", "shortening", "vegetable oil", "edible vegetable oil", "refined oil"],
     "These are common in packaged snacks. Check the saturated and trans fat values alongside them."),
    ("Salt and sodium sources", ["salt", "monosodium glutamate", "msg", "sodium", "e621", "621"],
     "Contribute to the sodium value. Relevant if you are watching blood pressure."),
    ("Artificial sweeteners", ["aspartame", "sucralose", "acesulfame", "saccharin", "stevia", "steviol", "sweetener", "cyclamate", "neotame"],
     "Sweet without sugar. They are why a drink can show low sugar but still be a treat."),
]


def analyze_ingredients(items: List[str]) -> List[Dict[str, object]]:
    """Group matching ingredients into neutral notes: [{title, found, note}]."""
    notes = []
    for title, words, note in _NOTE_RULES:
        hits = []
        for item in items:
            low = item.lower()
            if any(re.search(r"(?<![a-z0-9])" + re.escape(w) + r"(?![a-z])", low) for w in words):
                hits.append(re.sub(r"\s+", " ", item).strip())
        if hits:
            notes.append({"title": title, "found": hits[:5], "note": note})
    return notes


def first_ingredient_note(items: List[str]) -> Optional[str]:
    """Ingredients are listed by weight, so the first one is the biggest part."""
    if not items:
        return None
    return f"Ingredients are listed from the largest amount to the smallest, so this product is mostly {items[0].lower()}."


# --------------------------------------------------------------------------
# Per serving and daily intake
# --------------------------------------------------------------------------
# Approximate adult reference amounts for a 2,000 kcal day (WHO / EU / FSSAI-style
# reference values, rounded). Individual needs vary - shown as a guide only.
DAILY_REFERENCE: Dict[str, float] = {
    "calories_kcal": 2000.0,
    "sugar_g": 50.0,           # WHO: free sugars under 10% of energy
    "added_sugar_g": 50.0,
    "saturated_fat_g": 22.0,   # WHO: under 10% of energy
    "total_fat_g": 67.0,       # about 30% of energy
    "carbs_g": 275.0,
    "fibre_g": 25.0,
    "protein_g": 50.0,
    "sodium_mg": 2000.0,       # WHO: under 2 g sodium (5 g salt)
    "salt_g": 5.0,
    "potassium_mg": 3500.0,
    "calcium_mg": 1000.0,
    "iron_mg": 17.0,
    "cholesterol_mg": 300.0,
    "trans_fat_g": 2.0,        # WHO: under 1% of energy
}
REFERENCE_NOTE = "Based on a 2,000 kcal reference day. Your needs may differ."


def per_serving(value_per_100: Optional[float], serving_size: Optional[float]) -> Optional[float]:
    """Amount in one serving, or None when either input is unknown."""
    if value_per_100 is None or not serving_size or serving_size <= 0:
        return None
    return round(value_per_100 * serving_size / 100.0, 2)


def daily_share(key: str, serving_amount: Optional[float]) -> Optional[int]:
    """Percent of the reference daily amount in one serving (None if unknown)."""
    reference = DAILY_REFERENCE.get(key)
    if serving_amount is None or not reference:
        return None
    return int(round(100.0 * serving_amount / reference))
