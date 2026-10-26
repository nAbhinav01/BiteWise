"""
Health Score Module
-------------------------------------------------------
Calculates a 0-100 "Health Score" with plain, deterministic Python.
No AI/LLM is involved in scoring - the LLM only explains the result.

IMPORTANT: this is an *adapted Nutri-Score-based* score, NOT the official
Nutri-Score. It reuses the Nutri-Score idea:
    negative points : energy, sugars, saturated fat, sodium
    positive points : fibre, protein
    raw = negative - positive         (lower raw = healthier)
and maps raw onto the five Nutri-Score classes A-E, which become the five
score bands (A=81-100 ... E=0-20).

Safety rules added after testing on real labels (so unhealthy food is not
called healthy):
  1. Drinks use stricter beverage thresholds (food thresholds are far too
     lenient for liquids).
  2. Protein is NOT counted when negative points >= 11 (original Nutri-Score
     rule; we cannot see fruit/veg/nut content, so we stay conservative).
  3. Sweeteners in a drink add +4 negative points.
  4. If a key negative nutrient (energy, sugars, saturated fat, sodium) is
     missing, or values could not be normalized to per 100 g/ml, the score
     is capped at 60 ("Moderate") because we cannot prove the food is good.

Limitation: fruit/vegetable/nut content is not visible in the nutrition
table, so results can differ from the official Nutri-Score.
"""

from typing import Dict, List, Sequence

# A value earns 1 point for each threshold it is STRICTLY greater than.
# ---- Foods ----
ENERGY_KJ_FOOD = [335 * i for i in range(1, 11)]                              # 0-10 pts
SUGAR_G_FOOD = [3.4, 6.8, 10, 14, 17, 20, 24, 27, 31, 34, 37, 41, 44, 48, 51]  # 0-15
# ---- Drinks (per 100 ml) ----
ENERGY_KJ_DRINK = [30 * i for i in range(1, 11)]                              # 0-10 pts
SUGAR_G_DRINK = [0.5, 2, 3.5, 5, 6, 7, 8, 9, 10, 11]                          # 0-10 pts
PROTEIN_G_DRINK = [1.2, 1.5, 1.8, 2.1, 2.4, 2.7, 3.0]                         # 0-7 pts
# ---- Shared ----
SAT_FAT_G = [float(i) for i in range(1, 11)]                                  # 0-10 pts
SODIUM_MG = [80.0 * i for i in range(1, 21)]                                  # 0-20 pts
FIBRE_G = [3.0, 4.1, 5.2, 6.3, 7.4]                                           # 0-5 pts
PROTEIN_G_FOOD = [2.4, 4.8, 7.2, 9.6, 12, 14, 17]                             # 0-7 pts

KJ_PER_KCAL = 4.184
PROTEIN_CUTOFF = 11        # negative points at/above this -> protein ignored
SWEETENER_POINTS = 4       # extra negative points for sweetened drinks
UNCERTAIN_MAX_SCORE = 60   # cap when data is incomplete / not normalized
MIN_NUTRIENTS = 3          # need at least this many nutrients to score

# Raw-point bands (low raw, high raw, class letter) -> mapped to score ranges.
# Foods follow the Nutri-Score class limits; drinks are stricter.
FOOD_BANDS = [(-10, 0, "A"), (1, 2, "B"), (3, 10, "C"), (11, 18, "D"), (19, 40, "E")]
DRINK_BANDS = [(-10, 0, "A"), (1, 2, "B"), (3, 5, "C"), (6, 9, "D"), (10, 40, "E")]
LETTER_SCORE_RANGE = {"A": (81, 100), "B": (61, 80), "C": (41, 60), "D": (21, 40), "E": (0, 20)}

# (min score, max score, label) - 5 equal bands as in the project spec.
SCORE_BANDS = [
    (0, 20, "Poor"),
    (21, 40, "Below Average"),
    (41, 60, "Moderate"),
    (61, 80, "Good"),
    (81, 100, "Excellent"),
]

NEGATIVE_KEYS = {"calories_kcal": "Energy", "sugar_g": "Sugars",
                 "saturated_fat_g": "Saturated Fat", "sodium_mg": "Sodium"}


def points_for(value: float, thresholds: Sequence[float]) -> int:
    """Number of thresholds the value is strictly greater than."""
    return sum(1 for t in thresholds if value > t)


def score_category(score: int) -> str:
    """Map a 0-100 score to its category label."""
    for low, high, label in SCORE_BANDS:
        if low <= score <= high:
            return label
    return "Unknown"


def raw_to_score(raw: int, is_drink: bool = False) -> int:
    """
    Convert raw Nutri-Score-style points to a 0-100 score. The raw value
    falls in a class band (A-E); the score is placed linearly inside that
    class's 20-point score range (healthier raw -> higher score).
    """
    bands = DRINK_BANDS if is_drink else FOOD_BANDS
    raw = max(bands[0][0], min(bands[-1][1], raw))
    for low, high, letter in bands:
        if low <= raw <= high:
            s_low, s_high = LETTER_SCORE_RANGE[letter]
            if high == low:
                return s_high
            fraction = (raw - low) / (high - low)   # 0 at best raw (low), 1 at worst raw (high)
            return round(s_high - fraction * (s_high - s_low))
    return 0


def calculate_health_score(
    parsed: Dict[str, object],
    is_drink: bool = False,
    has_sweeteners: bool = False,
) -> Dict[str, object]:
    """
    Calculate the Health Score from the parser output (values per 100 g/ml).

    Returns a dict with: score (int or None), category, letter, negative_points,
    positive_points, raw_points, breakdown (list of rows), missing,
    missing_negative, capped (bool), notes.
    """
    result: Dict[str, object] = {
        "score": None, "category": None, "letter": None, "negative_points": 0,
        "positive_points": 0, "raw_points": None, "breakdown": [],
        "missing": [], "missing_negative": [], "capped": False, "notes": [],
    }
    notes: List[str] = result["notes"]  # type: ignore[assignment]
    breakdown: List[Dict[str, object]] = result["breakdown"]  # type: ignore[assignment]

    kcal = parsed.get("calories_kcal")
    energy_table = ENERGY_KJ_DRINK if is_drink else ENERGY_KJ_FOOD
    sugar_table = SUGAR_G_DRINK if is_drink else SUGAR_G_FOOD
    protein_table = PROTEIN_G_DRINK if is_drink else PROTEIN_G_FOOD

    # (key, display name, value, unit, thresholds, is_negative)
    spec = [
        ("calories_kcal", "Energy", None if kcal is None else float(kcal) * KJ_PER_KCAL, "kJ", energy_table, True),
        ("sugar_g", "Sugars", parsed.get("sugar_g"), "g", sugar_table, True),
        ("saturated_fat_g", "Saturated Fat", parsed.get("saturated_fat_g"), "g", SAT_FAT_G, True),
        ("sodium_mg", "Sodium", parsed.get("sodium_mg"), "mg", SODIUM_MG, True),
        ("fibre_g", "Fibre", parsed.get("fibre_g"), "g", FIBRE_G, False),
        ("protein_g", "Protein", parsed.get("protein_g"), "g", protein_table, False),
    ]

    negative = 0
    positive_rows: List[Dict[str, object]] = []
    missing: List[str] = []
    for key, name, value, unit, thresholds, is_negative in spec:
        if value is None:
            missing.append(name)
            continue
        pts = points_for(float(value), thresholds)
        row = {
            "Nutrient": name,
            "Value": f"{float(value):g} {unit}" if key != "calories_kcal" else f"{float(kcal):g} kcal",  # type: ignore[arg-type]
            "Points": pts,
            "Type": "Negative (bad)" if is_negative else "Positive (good)",
            "Max": len(thresholds),
        }
        if is_negative:
            negative += pts
            breakdown.append(row)
        else:
            positive_rows.append(row)

    if has_sweeteners and is_drink:
        negative += SWEETENER_POINTS
        breakdown.append({"Nutrient": "Sweeteners", "Value": "present", "Points": SWEETENER_POINTS,
                          "Type": "Negative (bad)", "Max": SWEETENER_POINTS})
        notes.append("Artificial sweeteners were detected in this drink (+4 negative points).")

    # Rule 2: protein is ignored when negative points are already high.
    protein_ignored = negative >= PROTEIN_CUTOFF
    positive = 0
    for row in positive_rows:
        if protein_ignored and row["Nutrient"] == "Protein":
            row = dict(row, Points=0)
            notes.append("Protein points were not counted because the negative points are high "
                         "(original Nutri-Score rule).")
        positive += int(row["Points"])  # type: ignore[arg-type]
        breakdown.append(row)

    result["missing"] = missing
    result["missing_negative"] = [n for n in NEGATIVE_KEYS.values() if n in missing]
    if len(breakdown) < MIN_NUTRIENTS or (len(spec) - len(missing)) < MIN_NUTRIENTS:
        notes.append("Too few nutrients were extracted to calculate a reliable score.")
        return result

    raw = negative - positive
    score = raw_to_score(raw, is_drink)

    # Rule 4: never call a product healthy on incomplete / un-normalized data.
    uncertain = bool(result["missing_negative"]) or not parsed.get("normalized")
    if uncertain and score > UNCERTAIN_MAX_SCORE:
        score = UNCERTAIN_MAX_SCORE
        result["capped"] = True

    letter = next((l for lo, hi, l in (DRINK_BANDS if is_drink else FOOD_BANDS) if lo <= max(-10, min(40, raw)) <= hi), "E")
    result.update({
        "score": score, "category": score_category(score), "letter": letter,
        "negative_points": negative, "positive_points": positive, "raw_points": raw,
    })
    if result["missing_negative"]:
        notes.append("Missing key nutrients: " + ", ".join(result["missing_negative"])  # type: ignore[arg-type]
                     + ". The score is capped at 'Moderate' because it cannot be verified.")
    elif "Fibre" in missing or "Protein" in missing:
        notes.append("Fibre/protein not found; they add no points.")
    if not parsed.get("normalized"):
        notes.append("Values were not confirmed as per 100 g/ml, so the score is capped at 'Moderate'. "
                     "Correct the values below to get an exact score.")
    notes.append("Adapted Nutri-Score-based score" + (" (drinks thresholds)" if is_drink else "")
                 + "; not the official Nutri-Score.")
    return result
