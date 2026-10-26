"""
Pipeline helpers
-----------------------------------------
Small glue functions that connect the modules built in earlier phases so
that app.py stays short and readable:

    image -> preprocessing -> OCR -> (nutrient_parser) -> (health_score)
          -> (ai_explanation) -> (recommendations)

Nothing here contains new "intelligence"; it only wires existing modules.
"""

import re
from typing import Callable, Dict, List, Optional

import numpy as np

from category_detector import UNKNOWN_LABEL, detect_category
from image_preprocessing import load_image, preprocess_for_ocr, preprocess_gentle, preprocess_plain
from nutrient_parser import DISPLAY_NAMES, EXTRA_KEYS, NUTRIENT_KEYS, count_found, parse_nutrients
from ocr import extract_text

AUTO_DETECT = "Auto-detect"
DRINK_CATEGORIES = {"Soft Drinks & Beverages", "Fruit Juices"}
SWEETENER_WORDS = [
    "aspartame", "sucralose", "acesulfame", "saccharin", "stevia", "steviol",
    "sweetener", "sweeteners", "cyclamate", "neotame", "advantame",
]


def _is_explicit(text: str, value: Optional[float]) -> bool:
    """True if the number appears in the OCR text directly followed by a unit
    (e.g. '3.5 g'). A number whose unit was lost ('3.59') is more suspicious."""
    if value is None:
        return False
    return re.search(r"(?<![\d.])" + re.escape(f"{value:g}") + r"\s*(?:g|mg|kcal|kj)\b", text.lower()) is not None


def _vote(candidates: List[tuple]) -> Optional[float]:
    """
    Choose one value for a nutrient from several OCR passes.
    candidates: (value, explicit_unit_flag) in priority order.
    Prefer values that were printed with their unit, then the most common
    value, then the earliest pass.
    """
    values = [c for c in candidates if c[0] is not None]
    if not values:
        return None
    explicit = [c for c in values if c[1]]
    pool = explicit or values
    counts: Dict[float, int] = {}
    for value, _flag in pool:
        counts[value] = counts.get(value, 0) + 1
    best_count = max(counts.values())
    for value, _flag in pool:  # first (highest priority) among the most common
        if counts[value] == best_count:
            return value
    return None


def run_ocr_pipeline(uploaded_file, progress: Optional[Callable[[str], None]] = None) -> Dict[str, object]:
    """
    Image -> preprocessing -> OCR -> nutrient parsing, cross-checked.

    OCR is the weakest step, and no single preprocessing style is best for
    every photo (hard thresholding can turn "3.5 g" into "3.59"). So:
      1. OCR runs on two versions of the image (gentle + thresholded).
      2. If both parse to identical nutrient values we are done.
      3. If they disagree, a third plain-grayscale pass is added and each
         nutrient is decided by a vote across the passes.

    `progress` (optional) is called with a short message at each real stage so
    the UI can show what is happening ("Improving image readability...").

    Returns {"processed", "text", "parsed", "variant"}.
    Raises ValueError (bad image) or RuntimeError (Tesseract problems); the
    caller shows these as friendly messages.
    """
    def say(message: str) -> None:
        if progress is not None:
            progress(message)

    say("Improving image readability...")
    image: np.ndarray = load_image(uploaded_file)

    def run(name: str, prep) -> Dict[str, object]:
        processed = prep(image)
        text = extract_text(processed)
        return {"name": name, "processed": processed, "text": text, "parsed": parse_nutrients(text)}

    say("Reading the nutrition label...")
    passes = [run("gentle", preprocess_gentle), run("thresholded", preprocess_for_ocr)]

    def values_of(entry: Dict[str, object]) -> tuple:
        return tuple(entry["parsed"][k] for k in NUTRIENT_KEYS)  # type: ignore[index]

    if values_of(passes[0]) != values_of(passes[1]):
        say("Double-checking unclear values...")
        passes.append(run("plain", preprocess_plain))
    say("Identifying nutrient values...")

    # Best single pass = most nutrients found, then most readable units (ties -> earlier pass).
    def quality(entry: Dict[str, object]) -> tuple:
        text = str(entry["text"]).lower()
        # A pass whose values could be normalized to per 100 g/ml beats one that could not.
        return (bool(entry["parsed"]["normalized"]), count_found(entry["parsed"]),  # type: ignore[index,arg-type]
                len(re.findall(r"\d\s*(?:g|mg|kcal|kj)\b", text)))

    best = max(passes, key=quality)
    parsed = dict(best["parsed"])  # type: ignore[arg-type]
    parsed["notes"] = list(parsed["notes"])

    # Only passes that agree with the best pass on the label basis may vote
    # (values per serving and values per 100 g must never be mixed).
    voters = [e for e in passes if e["parsed"]["serving_basis"] == best["parsed"]["serving_basis"]]  # type: ignore[index]
    per_100_basis = str(best["parsed"]["serving_basis"]).startswith("per 100")  # type: ignore[index]
    if len(voters) > 1:
        # Information-only nutrients: if the best pass missed one that another pass read, use it.
        for key in EXTRA_KEYS:
            if parsed[key] is None:
                parsed[key] = next((e["parsed"][key] for e in voters if e["parsed"][key] is not None), None)  # type: ignore[index]
        for key in NUTRIENT_KEYS:
            candidates = [
                (entry["parsed"][key],  # type: ignore[index]
                 per_100_basis and _is_explicit(str(entry["text"]), entry["parsed"][key]))  # type: ignore[index]
                for entry in sorted(voters, key=lambda e: e is not best)  # best pass first
            ]
            parsed[key] = _vote(candidates)
        parsed["notes"].append(f"Values were cross-checked across {len(voters)} OCR passes.")
        # A value missing from the best pass may now be filled by another pass.
        parsed["notes"] = [n for n in parsed["notes"] if not n.startswith("Not found on the label")]
        missing = [DISPLAY_NAMES[k][0] for k in NUTRIENT_KEYS if parsed[k] is None]
        if missing:
            parsed["notes"].append("Not found on the label: " + ", ".join(missing) + ".")

    return {"processed": best["processed"], "text": best["text"], "parsed": parsed, "variant": best["name"]}


def resolve_category(choice: str, text: str) -> Optional[str]:
    """Turn the dropdown choice (or auto-detection) into a category label."""
    if choice == AUTO_DETECT:
        return detect_category(text)
    if choice == UNKNOWN_LABEL:
        return None
    return choice


def is_drink(category: Optional[str], serving_basis: str) -> bool:
    """A product is scored with drink thresholds if its category is a drink,
    or (when the category is unknown) the label is expressed per 100 ml."""
    if category is not None:
        return category in DRINK_CATEGORIES
    return "ml" in (serving_basis or "")


def detect_sweeteners(text: str) -> bool:
    """True if the OCR text mentions artificial sweeteners (ingredients list)."""
    lowered = (text or "").lower()
    return any(re.search(r"\b" + word, lowered) for word in SWEETENER_WORDS)
