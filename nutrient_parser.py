"""
Nutrient Parser Module
---------------------------------
Turns raw OCR text into structured nutrient values using plain
regular expressions and simple rules. NO AI/LLM is used here - the
parser is fully deterministic and easy to explain in a viva.

What it does
  1. Cleans the OCR text (lower-case, fixes decimal commas, etc.).
  2. Detects the label basis: "per 100 g/ml" or "per serving".
  3. Finds each nutrient line (sugar, sodium/salt, saturated fat,
     energy, fibre, protein) and reads value + unit.
  4. Converts units (mg <-> g, kJ -> kcal, salt -> sodium).
  5. Normalises to per 100 g/ml ONLY when this is clearly possible,
     otherwise leaves values as-is and flags it in `notes`.

Output (dict) - missing nutrients are None:
    {
      "sugar_g": 18.0, "sodium_mg": 400.0, "saturated_fat_g": 6.0,
      "calories_kcal": 450.0, "fibre_g": 4.0, "protein_g": 8.0,
      "serving_basis": "per 100 g",
      "normalized": True,
      "notes": ["..."],
    }
"""

import re
from typing import Dict, List, Optional, Tuple

# Nutrient keys the rest of the project (Health Score) relies on.
NUTRIENT_KEYS: List[str] = [
    "sugar_g",
    "sodium_mg",
    "saturated_fat_g",
    "calories_kcal",
    "fibre_g",
    "protein_g",
]

# Extra nutrients: shown for information only. They are NEVER used in the Health
# Score, and a missing one is "Not available" (None), never zero.
EXTRA_KEYS: List[str] = [
    "added_sugar_g",
    "total_fat_g",
    "carbs_g",
    "trans_fat_g",
    "potassium_mg",
    "calcium_mg",
    "iron_mg",
    "cholesterol_mg",
    "salt_g",
]
EXTRA_DISPLAY: Dict[str, Tuple[str, str]] = {
    "added_sugar_g": ("Added Sugar", "g"),
    "total_fat_g": ("Total Fat", "g"),
    "carbs_g": ("Carbohydrates", "g"),
    "trans_fat_g": ("Trans Fat", "g"),
    "potassium_mg": ("Potassium", "mg"),
    "calcium_mg": ("Calcium", "mg"),
    "iron_mg": ("Iron", "mg"),
    "cholesterol_mg": ("Cholesterol", "mg"),
    "salt_g": ("Salt", "g"),
}
EXTRA_PATTERNS: Dict[str, str] = {
    "added_sugar_g": r"added\s+sugars?",
    "total_fat_g": r"(?:total\s*)?fats?",
    "carbs_g": r"(?:total\s*)?carbohydrates?|carbs?",
    "trans_fat_g": r"trans\s*(?:fat(?:ty\s+acids?)?|fats)?",
    "potassium_mg": r"potassium",
    "calcium_mg": r"calcium",
    "iron_mg": r"iron",
    "cholesterol_mg": r"cholesterol",
    "salt_g": r"salt",
}
# Words that, right before "fat", mean it is NOT the total-fat row.
TOTAL_FAT_SKIP = ("saturated", "saturates", "sat", "trans", "mono", "poly", "monounsaturated",
                  "polyunsaturated", "unsaturated", "from", "low", "reduced")
ALL_KEYS: List[str] = NUTRIENT_KEYS + EXTRA_KEYS

# Human-friendly names used when displaying the results table.
DISPLAY_NAMES: Dict[str, Tuple[str, str]] = {
    "calories_kcal": ("Energy", "kcal"),
    "sugar_g": ("Sugars", "g"),
    "saturated_fat_g": ("Saturated Fat", "g"),
    "sodium_mg": ("Sodium", "mg"),
    "fibre_g": ("Fibre", "g"),
    "protein_g": ("Protein", "g"),
}

ALL_DISPLAY: Dict[str, Tuple[str, str]] = {**DISPLAY_NAMES, **EXTRA_DISPLAY}

# Label wording variants for each nutrient (regular expressions).
LABEL_PATTERNS: Dict[str, str] = {
    "sugar_g": r"(?:total\s*)?sugars?",
    "saturated_fat_g": r"sat(?:urated|urates|\.)?\s*(?:fat(?:ty\s+acids?)?|fats)?",
    "calories_kcal": r"energy|calories|kcal",
    "fibre_g": r"(?:dietary\s+)?fib(?:re|er)",
    "protein_g": r"proteins?",
    "sodium_mg": r"sodium",
}
SALT_PATTERN = r"salt"

# Tokenizer used to read the numbers that follow a nutrient name.
TOKEN_RE = re.compile(r"(?P<num>\d+(?:[.,]\d+)?)(?P<pct>\s*%)?|(?P<word>[a-zµ]+)", re.IGNORECASE)
UNIT_AFTER = re.compile(r"\s*(kcal|kj|mcg|µg|ug|mg|g|ml)(?![a-z0-9])", re.IGNORECASE)
UNIT_WORDS = {"kcal", "kj", "mg", "mcg", "µg", "ug", "g", "ml"}
# Words allowed between a nutrient name and its number (e.g. "Total", "approx").
FILLER_WORDS = {"total", "of", "which", "value", "approx", "approximately", "per",
                "serve", "serving", "content", "amount", "and", "dv", "rda", "nrv", "ri"}

# Anything above these (per 100 g/ml) is physically implausible -> OCR error.
PLAUSIBLE_MAX = {
    "sugar_g": 100.0,
    "saturated_fat_g": 100.0,
    "fibre_g": 100.0,
    "protein_g": 100.0,
    "sodium_mg": 40000.0,
    "calories_kcal": 950.0,
    "added_sugar_g": 100.0,
    "total_fat_g": 100.0,
    "carbs_g": 100.0,
    "trans_fat_g": 100.0,
    "potassium_mg": 10000.0,
    "calcium_mg": 5000.0,
    "iron_mg": 200.0,
    "cholesterol_mg": 5000.0,
    "salt_g": 100.0,
}

KJ_PER_KCAL = 4.184
MG_SODIUM_PER_G_SALT = 400.0  # salt (g) = sodium (g) x 2.5


# ---------------------------------------------------------------------------
# Text cleaning
# ---------------------------------------------------------------------------
def clean_text(raw_text: str) -> str:
    """Lower-case the text and tidy common OCR noise."""
    text = raw_text.lower()
    text = text.replace("\r", "\n").replace("|", " ").replace("\t", " ")
    text = text.replace("μ", "µ")
    text = text.replace("<", " ").replace("~", " ")
    # Common OCR letter/digit confusions next to units: "lg" -> "1g", "5o mg" -> "50 mg".
    text = re.sub(r"(?<![a-z])[li](?=\s*(?:g|mg|kcal|kj)\b)", "1", text)
    text = re.sub(r"(sugars?|fat|fats|fib(?:re|er)|proteins?|sodium|salt|saturates?)[li](?=\s*(?:g|mg)\b)", r"\1 1", text)
    text = re.sub(r"(?<=\d)o(?![a-z])", "0", text)
    text = re.sub(r"(?<![a-z\d])o(?=[.,]\d)", "0", text)
    text = re.sub(r"[ ]{2,}", " ", text)
    return text.strip()


def _to_float(number_text: str) -> float:
    """'1,5' -> 1.5 (labels in some regions use a decimal comma)."""
    return float(number_text.replace(",", "."))


# ---------------------------------------------------------------------------
# Basis detection (per 100 g/ml vs per serving)
# ---------------------------------------------------------------------------
def detect_basis(text: str) -> Dict[str, object]:
    """
    Work out what the numbers on the label refer to.

    Returns a dict with:
      per100_pos / serving_pos : where the headers appear in the text
      per100_unit              : 'g' or 'ml' (or None)
      serving_size             : serving size number (or None)
      serving_unit             : 'g' or 'ml' (or None)
    """
    # Tolerates OCR slips such as "per 1009" (g read as 9) and "100gm".
    per100 = re.search(r"(?:per|for|/)\s*100\s*(g|ml|gm|gms|9)(?![a-z0-9])", text)
    if per100 is None:
        per100 = re.search(r"\b100\s*(g|ml)\b\s*(?:serving|portion)?", text)
    serving = re.search(r"per\s+(?:serving|serve|portion|pack|bar|piece|biscuit|slice|cup|scoop)", text)
    size = re.search(
        r"(?:serving|serve|portion)\s*size[^\d\n]{0,15}(\d+(?:[.,]\d+)?)\s*(g|ml)\b", text
    )
    if size is None:
        size = re.search(r"per\s+(?:serving|serve)\s*\(?\s*(\d+(?:[.,]\d+)?)\s*(g|ml)\b", text)

    return {
        "per100_pos": per100.start() if per100 else None,
        "per100_unit": ("ml" if per100.group(1) == "ml" else "g") if per100 else None,
        "serving_pos": serving.start() if serving else None,
        "serving_size": _to_float(size.group(1)) if size else None,
        "serving_unit": size.group(2) if size else None,
    }


# ---------------------------------------------------------------------------
# Value extraction
# ---------------------------------------------------------------------------
def _split_merged(raw: str, ratio: float) -> Optional[Tuple[float, float]]:
    """
    OCR sometimes glues two columns together ("20" + "5" -> "205"). When the
    label shows per-100 g AND per-serving columns and the serving size is
    known, split the digits so that  serving = per100 x serving_size/100.
    Returns (per100, per_serving) or None if no unique split fits.
    """
    best: Optional[Tuple[float, Tuple[float, float]]] = None
    for i in range(1, len(raw)):
        left, right = raw[:i], raw[i:]
        if not (re.fullmatch(r"\d+(?:\.\d+)?", left) and re.fullmatch(r"\d+(?:\.\d+)?", right)):
            continue
        a, b = float(left), float(right)
        expected = a * ratio
        error = abs(b - expected)
        if error <= max(0.1, 0.15 * expected) and (best is None or error < best[0]):
            best = (error, (a, b))
    return best[1] if best else None


def _numbers_after(line: str, start: int, ratio: Optional[float] = None) -> List[Tuple[float, Optional[str]]]:
    """
    Read (value, unit) pairs that follow a nutrient name on one line.
    - '%' columns (daily values) are skipped.
    - Reading stops at the first unrelated word (so ingredient lists such as
      "Sugar, Salt, Emulsifier (322)" are not mistaken for nutrient rows).
    - Units printed in the name, e.g. "Energy (kcal) 450" or "Sodium (mg) 400",
      are applied to numbers that have no unit of their own.
    """
    out: List[List[object]] = []
    hints: List[str] = []
    pos = start
    previous_word = ""
    while pos < len(line):
        token = TOKEN_RE.search(line, pos)
        if token is None:
            break
        pos = token.end()
        word = token.group("word")
        if word:
            word = word.lower()
            if word in UNIT_WORDS:
                hints.append(word)
            elif word not in FILLER_WORDS:
                break  # unrelated word -> not a nutrient row (or row finished)
            previous_word = word
            continue
        if token.group("pct"):
            continue
        number = _to_float(token.group("num"))
        if previous_word == "per" and number == 100:
            previous_word = ""
            continue  # the "per 100" header, not an amount
        previous_word = ""
        unit_match = UNIT_AFTER.match(line, pos)
        unit = None
        if unit_match:
            unit = unit_match.group(1).lower()
            pos = unit_match.end()
        out.append([number, unit, token.group("num")])

    # Two columns glued together by OCR (only one number found on the row).
    if ratio and len(out) == 1 and len(str(out[0][2])) >= 2:
        split = _split_merged(str(out[0][2]), ratio)
        if split:
            out = [[split[0], out[0][1], ""], [split[1], out[0][1], ""]]

    plain = [item for item in out if item[1] is None]
    if hints and plain:
        for index, item in enumerate(plain):
            item[1] = hints[index % len(hints)]
    return [(float(v), u) for v, u, _raw in out]  # type: ignore[arg-type,misc]


def _find_values(text: str, label_regex: str, skip_prefixes: Tuple[str, ...] = (), ratio: Optional[float] = None) -> List[Tuple[float, Optional[str]]]:
    """Return the (value, unit) list from the first nutrient row that matches the label."""
    pattern = re.compile(r"(?<![a-z])(?:" + label_regex + r")(?![a-z])")
    for line in text.split("\n"):
        if "ingredient" in line:
            continue
        for match in pattern.finditer(line):
            if any(line[: match.start()].strip().endswith(p) for p in skip_prefixes):
                continue
            values = _numbers_after(line, match.end(), ratio)
            if values:
                return values
    return []


def _convert(value: float, unit: Optional[str], target: str) -> Optional[float]:
    """Convert a mass value to the target unit ('g' or 'mg')."""
    unit = unit or target  # no unit printed -> assume the usual one
    to_grams = {"g": 1.0, "mg": 1e-3, "mcg": 1e-6, "µg": 1e-6, "ug": 1e-6}
    if unit not in to_grams:
        return None
    grams = value * to_grams[unit]
    return grams if target == "g" else grams * 1000.0


def _fix_lost_unit(value: float, unit: Optional[str], units_printed: bool) -> Tuple[float, bool]:
    """
    A very common OCR slip reads the unit "g" as the digit "9" (so "3.5 g"
    becomes "3.59" and "5 g" becomes "59"). We only repair a number when ALL hold:
      - it has no unit of its own,
      - the rest of the label clearly prints units (units_printed),
      - it has 2+ digits and ends in 9.
    Returns (value, was_repaired). Over-reading ("3.59") is the safe error
    direction, but a wrong "59" for fibre could mislead, so we repair it.
    """
    if unit is not None or not units_printed:
        return value, False
    text = f"{value:g}"
    digits = text.replace(".", "")
    if len(digits) < 2 or not text.endswith("9"):
        return value, False
    trimmed = text[:-1].rstrip(".")
    try:
        return float(trimmed), True
    except ValueError:
        return value, False


def _pick(values: List[Tuple[float, Optional[str]]], column: int) -> Tuple[float, Optional[str]]:
    """Choose the right column when a line holds several numbers."""
    return values[column] if column < len(values) else values[0]


def _energy_kcal(values: List[Tuple[float, Optional[str]]], column: int) -> Optional[float]:
    """Energy: prefer kcal, otherwise convert kJ, otherwise assume kcal."""
    kcal = [v for v, u in values if u == "kcal"]
    if kcal:
        return kcal[column] if column < len(kcal) else kcal[0]
    kj = [v for v, u in values if u == "kj"]
    if kj:
        chosen = kj[column] if column < len(kj) else kj[0]
        return round(chosen / KJ_PER_KCAL, 1)
    plain = [v for v, u in values if u is None]
    if plain:
        chosen = plain[column] if column < len(plain) else plain[0]
        # An energy number above 950 cannot be kcal per 100 g, so it must be kJ.
        return round(chosen / KJ_PER_KCAL, 1) if chosen > 950 else chosen
    return None


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
def parse_nutrients(raw_text: str) -> Dict[str, object]:
    """Parse raw OCR text into the structured nutrient dictionary."""
    result: Dict[str, object] = {key: None for key in ALL_KEYS}
    result.update({"serving_basis": "unknown", "normalized": False, "notes": [],
                   "serving_size": None, "serving_unit": None})
    notes: List[str] = result["notes"]  # type: ignore[assignment]

    if not raw_text or not raw_text.strip():
        notes.append("No text was provided to the parser.")
        return result

    text = clean_text(raw_text)
    basis = detect_basis(text)
    result["serving_size"] = basis["serving_size"]
    result["serving_unit"] = basis["serving_unit"]

    # If a label shows both columns, pick the column that is per 100 g/ml.
    has_both = basis["per100_pos"] is not None and basis["serving_pos"] is not None
    column = 0
    if has_both and basis["serving_pos"] < basis["per100_pos"]:  # type: ignore[operator]
        column = 1

    # Used to repair two columns that OCR glued into one number.
    ratio = (float(basis["serving_size"]) / 100.0) if (has_both and basis["serving_size"]) else None  # type: ignore[arg-type]

    # Does this label print units next to its numbers? (needed for the '9' repair)
    units_printed = len(re.findall(r"\d\s*(?:g|mg|kcal|kj)\b", text)) >= 3

    # ---- 1. Read raw values (still in label units) ----
    raw: Dict[str, Optional[float]] = {}
    for key, label in LABEL_PATTERNS.items():
        values = _find_values(text, label, skip_prefixes=("added",), ratio=ratio)
        if key == "sugar_g" and not values:
            values = _find_values(text, r"added\s+sugars?", ratio=ratio)
            if values:
                notes.append("Only 'added sugars' was found; used it as the sugar value.")
        if not values:
            raw[key] = None
        elif key == "calories_kcal":
            raw[key] = _energy_kcal(values, column)
        elif key == "sodium_mg":
            value, unit = _pick([v for v in values if v[1] not in ("kcal", "kj")] or values, column)
            if unit is None and value < 10:
                unit = "g"  # e.g. "Sodium 0.4" with no unit is almost surely grams
            raw[key] = _convert(value, unit or "mg", "mg")
        else:
            usable = [v for v in values if v[1] not in ("kcal", "kj")] or values
            value, unit = _pick(usable, column)
            value, repaired = _fix_lost_unit(value, unit, units_printed)
            if repaired:
                notes.append(f"{DISPLAY_NAMES[key][0]}: read '{value:g}' (a trailing '9' was treated as a misread 'g').")
            raw[key] = _convert(value, unit, "g")

    # Extra (information-only) nutrients, read the same way.
    for key, label in EXTRA_PATTERNS.items():
        values = _find_values(text, label, skip_prefixes=TOTAL_FAT_SKIP if key == "total_fat_g" else (), ratio=ratio)
        if key == "added_sugar_g" and not values:
            us_style = re.search(r"includes?\s+(\d+(?:[.,]\d+)?)\s*(g|mg)?\s*added\s+sugars?", text)
            if us_style:
                values = [(_to_float(us_style.group(1)), us_style.group(2))]
        if not values:
            raw[key] = None
            continue
        usable = [v for v in values if v[1] not in ("kcal", "kj")] or values
        value, unit = _pick(usable, column)
        target = EXTRA_DISPLAY[key][1]
        if target == "g":
            value, _repaired = _fix_lost_unit(value, unit, units_printed)
        raw[key] = _convert(value, unit, target)

    # Salt -> sodium, only when sodium itself is not printed.
    if raw.get("sodium_mg") is None:
        salt_values = _find_values(text, SALT_PATTERN, ratio=ratio)
        if salt_values:
            value, unit = _pick(salt_values, column)
            value, repaired = _fix_lost_unit(value, unit, units_printed)
            if repaired:
                notes.append(f"Salt: read '{value:g}' (a trailing '9' was treated as a misread 'g').")
            salt_g = _convert(value, unit, "g")
            if salt_g is not None:
                raw["sodium_mg"] = round(salt_g * MG_SODIUM_PER_G_SALT, 1)
                notes.append("Sodium was calculated from salt (1 g salt = 400 mg sodium).")

    # ---- 2. Decide the factor that converts values to per 100 g/ml ----
    factor: Optional[float] = None
    if basis["per100_pos"] is not None:
        factor = 1.0
        unit_label = basis["per100_unit"] or "g"
        result["serving_basis"] = f"per 100 {unit_label}"
        result["normalized"] = True
    elif basis["serving_pos"] is not None or basis["serving_size"] is not None:
        size = basis["serving_size"]
        if size and size > 0:
            factor = 100.0 / float(size)  # type: ignore[arg-type]
            result["serving_basis"] = f"per serving ({size:g} {basis['serving_unit']}) -> converted to per 100 {basis['serving_unit']}"
            result["normalized"] = True
        else:
            result["serving_basis"] = "per serving"
            notes.append(
                "Values are per serving and the serving size was not readable, "
                "so they could not be normalized to per 100 g/ml."
            )
    else:
        notes.append(
            "Could not tell whether values are per 100 g/ml or per serving, "
            "so they could not be normalized."
        )

    # ---- 3. Apply factor + sanity checks ----
    for key in ALL_KEYS:
        value = raw.get(key)
        if value is None:
            continue
        if factor is not None:
            value = value * factor
        value = round(value, 2)
        if factor is not None and value > PLAUSIBLE_MAX[key]:
            notes.append(f"Ignored an implausible {ALL_DISPLAY[key][0]} value ({value:g}); likely an OCR misread.")
            continue
        result[key] = value

    missing = [DISPLAY_NAMES[k][0] for k in NUTRIENT_KEYS if result[k] is None]
    if missing:
        notes.append("Not found on the label: " + ", ".join(missing) + ".")
    return result


# ---------------------------------------------------------------------------
# Helpers used by the UI / later phases
# ---------------------------------------------------------------------------
def count_found(parsed: Dict[str, object]) -> int:
    """How many of the six core nutrients were extracted."""
    return sum(1 for key in NUTRIENT_KEYS if parsed.get(key) is not None)


def has_enough_nutrients(parsed: Dict[str, object], minimum: int = 3) -> bool:
    """True if at least `minimum` core nutrients were extracted."""
    return count_found(parsed) >= minimum


def to_display_rows(parsed: Dict[str, object]) -> List[Dict[str, str]]:
    """Rows for the 'Extracted Nutrients' table shown in the UI."""
    rows = []
    for key in NUTRIENT_KEYS:
        name, unit = DISPLAY_NAMES[key]
        value = parsed.get(key)
        rows.append({
            "Nutrient": name,
            "Value": f"{value:g} {unit}" if value is not None else "Not found",
        })
    return rows
