"""
Category Detector Module
-----------------------------------
Guesses the product category from keywords in the OCR text using simple
rules (no AI). The category is used to search Open Food Facts for
healthier products of the SAME kind.

If nothing matches, detect_category() returns None and the app lets the
user pick a category manually.
"""

import re
from typing import Dict, List, Optional

# label shown to user -> (Open Food Facts category tag, keywords)
CATEGORIES: Dict[str, Dict[str, object]] = {
    "Breakfast Cereals": {"tag": "en:breakfast-cereals",
        "keywords": ["cereal", "corn flakes", "cornflakes", "muesli", "granola", "oats", "oatmeal", "porridge"]},
    "Biscuits & Cookies": {"tag": "en:biscuits",
        "keywords": ["biscuit", "cookie", "cracker", "wafer"]},
    "Chips & Crisps": {"tag": "en:chips-and-crisps",
        "keywords": ["chips", "crisps", "potato chip", "namkeen", "nachos"]},
    "Snacks": {"tag": "en:snacks",
        "keywords": ["snack", "puffs", "popcorn", "bhujia", "trail mix", "namkeen"]},
    "Chocolates & Sweets": {"tag": "en:chocolates",
        "keywords": ["chocolate", "cocoa", "candy", "toffee", "confectionery", "gummies"]},
    "Soft Drinks & Beverages": {"tag": "en:beverages",
        "keywords": ["soda", "cola", "soft drink", "carbonated", "energy drink", "beverage", "sparkling"]},
    "Fruit Juices": {"tag": "en:fruit-juices",
        "keywords": ["juice", "nectar", "squash"]},
    "Dairy & Yogurt": {"tag": "en:yogurts",
        "keywords": ["yogurt", "yoghurt", "curd", "dahi", "milk", "lassi"]},
    "Instant Noodles & Pasta": {"tag": "en:instant-noodles",
        "keywords": ["noodle", "instant noodles", "pasta", "macaroni", "vermicelli"]},
    "Bread & Bakery": {"tag": "en:breads",
        "keywords": ["bread", "bun", "bakery", "cake", "muffin", "rusk"]},
    "Sauces & Spreads": {"tag": "en:sauces",
        "keywords": ["ketchup", "sauce", "mayonnaise", "spread", "peanut butter", "jam", "dressing"]},
}

UNKNOWN_LABEL = "Other / Not sure"


def category_labels() -> List[str]:
    """All category names (for the manual dropdown)."""
    return list(CATEGORIES.keys())


def get_off_tag(label: str) -> Optional[str]:
    """Open Food Facts tag for a category label (None if unknown)."""
    entry = CATEGORIES.get(label)
    return str(entry["tag"]) if entry else None


# Broader Open Food Facts categories to try when the main one has too few results.
FALLBACK_TAGS: Dict[str, List[str]] = {
    'en:breakfast-cereals': ['en:cereals-and-their-products'],
    'en:biscuits': ['en:biscuits-and-cakes', 'en:sweet-snacks', 'en:snacks'],
    'en:chips-and-crisps': ['en:salty-snacks', 'en:snacks'],
    'en:snacks': ['en:salty-snacks'],
    'en:chocolates': ['en:cocoa-and-its-products', 'en:sweet-snacks'],
    'en:beverages': [],
    'en:fruit-juices': ['en:juices-and-nectars', 'en:fruit-based-beverages'],
    'en:yogurts': ['en:fermented-milk-products', 'en:dairies'],
    'en:instant-noodles': ['en:noodles', 'en:pastas'],
    'en:breads': ['en:cereals-and-potatoes'],
    'en:sauces': ['en:condiments'],
}


def get_off_tags(label: str) -> List[str]:
    """Main Open Food Facts tag followed by broader fallback tags."""
    main = get_off_tag(label)
    if main is None:
        return []
    return [main] + FALLBACK_TAGS.get(main, [])


def detect_category(text: str) -> Optional[str]:
    """Return the category label with the most keyword hits, or None."""
    if not text:
        return None
    lowered = text.lower()
    best_label, best_hits = None, 0
    for label, entry in CATEGORIES.items():
        hits = sum(
            1 for kw in entry["keywords"]  # type: ignore[union-attr]
            if re.search(r"\b" + re.escape(kw), lowered)
        )
        if hits > best_hits:
            best_label, best_hits = label, hits
    return best_label
