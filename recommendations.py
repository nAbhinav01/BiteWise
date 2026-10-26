"""
Recommendations Module
-----------------------
Finds healthier alternatives using the free Open Food Facts (OFF) API.

Flow: category tag(s) -> fetch OFF products, healthier Nutri-Score grades
first (A, B, C), then popular ones -> score each with OUR OWN health_score
module (same formula as the scanned product, so the comparison is fair) ->
keep those scoring higher than the scanned product -> return the best few,
each with its image, a short reason and a link.

Nothing is invented: every product, nutrient value and image comes from
Open Food Facts; the score is calculated here from those values.

Failures (no internet, OFF down, nothing found) never crash the app:
find_alternatives() returns (list, message).
"""

import time
from functools import lru_cache
from typing import Dict, List, Optional, Sequence, Tuple, Union

import requests

from health_score import calculate_health_score

OFF_SEARCH_URL = "https://world.openfoodfacts.org/cgi/search.pl"
HEADERS = {"User-Agent": "BiteWise-FoodLabelHealthScanner/1.0 (college project)"}
FIELDS = "code,product_name,brands,nutriments,nutriscore_grade,url,image_front_small_url,image_small_url"
TIMEOUT_SECONDS = 12
TOTAL_BUDGET_SECONDS = 40          # stop searching after this long
GRADES_HEALTHIER_FIRST = ("a", "b", "c", None)  # None = most popular products


@lru_cache(maxsize=64)
def _fetch_products(category_tag: str, grade: Optional[str] = None, page_size: int = 50) -> Tuple[Dict, ...]:
    """Download products for a category (optionally one Nutri-Score grade). Cached."""
    params = {
        "action": "process", "json": 1,
        "tagtype_0": "categories", "tag_contains_0": "contains", "tag_0": category_tag,
        "sort_by": "unique_scans_n", "page_size": page_size, "fields": FIELDS,
    }
    if grade:
        params.update({"tagtype_1": "nutrition_grades", "tag_contains_1": "contains", "tag_1": grade})
    response = requests.get(OFF_SEARCH_URL, params=params, headers=HEADERS, timeout=TIMEOUT_SECONDS)
    response.raise_for_status()
    return tuple(response.json().get("products", []))


def clear_cache() -> None:
    """Forget downloaded results (used by the 'Try again' button)."""
    _fetch_products.cache_clear()


def nutriments_to_parsed(nutriments: Dict) -> Dict[str, object]:
    """Convert OFF per-100g nutriments into our parsed-nutrient dict."""
    def num(key: str) -> Optional[float]:
        value = nutriments.get(key)
        try:
            return None if value in (None, "") else float(value)
        except (TypeError, ValueError):
            return None

    sodium_g = num("sodium_100g")
    if sodium_g is None and num("salt_100g") is not None:
        sodium_g = num("salt_100g") / 2.5  # type: ignore[operator]
    kcal = num("energy-kcal_100g")
    if kcal is None and num("energy_100g") is not None:
        kcal = num("energy_100g") / 4.184  # type: ignore[operator]

    return {
        "calories_kcal": kcal,
        "sugar_g": num("sugars_100g"),
        "saturated_fat_g": num("saturated-fat_100g"),
        "sodium_mg": None if sodium_g is None else sodium_g * 1000,
        "fibre_g": num("fiber_100g"),
        "protein_g": num("proteins_100g"),
        "normalized": True,
    }


def build_reason(current: Optional[Dict[str, object]], alt: Dict[str, object], score_gain: int) -> str:
    """One short sentence on why this product is better, using real values only."""
    if not current:
        return f"Scores {score_gain} points higher on the same scale."
    options: List[Tuple[float, str]] = []

    def lower(key: str, label: str, unit: str, min_diff: float) -> None:
        a, c = alt.get(key), current.get(key)
        if a is None or c is None:
            return
        diff = float(c) - float(a)
        if diff >= min_diff and float(a) <= 0.75 * float(c):
            options.append((diff / max(float(c), 1e-9), f"{label} ({float(a):g} vs {float(c):g} {unit})"))

    def higher(key: str, label: str, unit: str, min_diff: float) -> None:
        a, c = alt.get(key), current.get(key)
        if a is None:
            return
        base = 0.0 if c is None else float(c)
        if float(a) - base >= min_diff:
            options.append(((float(a) - base) / max(float(a), 1e-9) * 0.8, f"{label} ({float(a):g} vs {base:g} {unit})"))

    lower("sugar_g", "Less sugar", "g", 2)
    lower("sodium_mg", "Less sodium", "mg", 60)
    lower("saturated_fat_g", "Less saturated fat", "g", 1)
    lower("calories_kcal", "Fewer calories", "kcal", 40)
    higher("fibre_g", "More fibre", "g", 2)
    higher("protein_g", "More protein", "g", 3)
    if not options:
        return f"Scores {score_gain} points higher on the same scale."
    options.sort(reverse=True)
    return " · ".join(text for _, text in options[:2])


def _evaluate(products: Sequence[Dict], current_score: int, is_drink: bool,
              current_values: Optional[Dict[str, object]], seen: set) -> List[Dict[str, object]]:
    """Score products and keep the clearly better ones with complete key data."""
    found: List[Dict[str, object]] = []
    for item in products:
        name = (item.get("product_name") or "").strip()
        if not name or name.lower() in seen:
            continue
        parsed = nutriments_to_parsed(item.get("nutriments") or {})
        result = calculate_health_score(parsed, is_drink=is_drink)
        if result["score"] is None or result["missing_negative"] or result["capped"] or result["score"] <= current_score:
            continue
        seen.add(name.lower())
        found.append({
            "Product": name,
            "Brand": (item.get("brands") or "").split(",")[0].strip() or "-",
            "Score": result["score"],
            "Category": result["category"],
            "Sugar (g/100g)": round(parsed["sugar_g"], 1),  # type: ignore[arg-type]
            "Nutri-Score (OFF)": (item.get("nutriscore_grade") or "-").upper(),
            "Link": item.get("url") or f"https://world.openfoodfacts.org/product/{item.get('code', '')}",
            "Image": item.get("image_front_small_url") or item.get("image_small_url") or "",
            "Reason": build_reason(current_values, parsed, int(result["score"]) - current_score),  # type: ignore[arg-type]
        })
    return found


def find_alternatives(
    category_tags: Union[str, Sequence[str]],
    current_score: int,
    top_n: int = 5,
    is_drink: bool = False,
    current_values: Optional[Dict[str, object]] = None,
) -> Tuple[List[Dict[str, object]], str]:
    """
    Return (alternatives, message). `message` is empty when all went well,
    otherwise a friendly explanation. Tries the main category first, then
    broader fallback categories, until `top_n` better products are found.
    """
    tags = [category_tags] if isinstance(category_tags, str) else list(category_tags)
    if not tags:
        return [], "No product category is selected yet."

    started = time.monotonic()
    collected: List[Dict[str, object]] = []
    seen: set = set()
    reached_off = False
    try:
        for tag in tags:
            for grade in GRADES_HEALTHIER_FIRST:
                if len(collected) >= top_n or time.monotonic() - started > TOTAL_BUDGET_SECONDS:
                    break
                products = _fetch_products(tag, grade)
                reached_off = True
                collected += _evaluate(products, current_score, is_drink, current_values, seen)
            if len(collected) >= top_n or time.monotonic() - started > TOTAL_BUDGET_SECONDS:
                break
    except requests.exceptions.RequestException:
        if not collected:
            return [], ("Could not reach Open Food Facts (internet issue or the service is "
                        "busy). Please try again in a moment.")
    except ValueError:
        if not collected:
            return [], "Open Food Facts returned an unexpected response. Please try again."

    collected.sort(key=lambda row: row["Score"], reverse=True)  # type: ignore[arg-type,return-value]
    top = collected[:top_n]
    if not top:
        return [], ("No healthier products with complete nutrition data were found for this category."
                    if reached_off else "Could not reach Open Food Facts. Please try again.")
    if len(top) < 3:
        return top, "Only a few healthier products with complete data were found."
    return top, ""
