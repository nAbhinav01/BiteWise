"""
Generate the sample nutrition-label images used for testing.

Run once:   python generate_sample_images.py

Creates, inside sample_images/:
  * 12 "clean" labels (rendered like a flat, well-lit nutrition table)
  * 12 "photo" versions (blur, noise, slight rotation, uneven lighting,
    JPEG compression - to imitate a phone photo)
  * ground_truth.csv - the correct nutrient values and the expected
    verdict for every image, so evaluate.py / test_samples.py can measure
    accuracy automatically.

These are SYNTHETIC labels with typical values for each product type
(not photos of real brands). Real photos should be added to this folder
and tested manually - see TESTING.md.
"""

import csv
import os
from typing import Dict, List

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

OUT_DIR = "sample_images"
FONTS = {
    "sans": "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "serif": "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    "mono": "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
}
BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
KEYS = ["calories_kcal", "sugar_g", "saturated_fat_g", "sodium_mg", "fibre_g", "protein_g"]

# Each label: product, lines to print, correct values per 100 g/ml,
# is_drink, expected verdict ("unhealthy" -> score <= 40, "healthy" -> >= 61),
# font + background colour.
LABELS: List[Dict] = [
    dict(id="01_potato_chips", product="Potato chips", drink=False, verdict="unhealthy", font="sans", bg=(250, 250, 245),
         lines=["NUTRITION FACTS", "Per 100 g", "Energy 536 kcal", "Protein 6 g", "Carbohydrate 52 g", "Total Sugars 0.5 g",
                "Total Fat 34 g", "Saturated Fat 3.5 g", "Dietary Fibre 4 g", "Sodium 600 mg"],
         truth=dict(calories_kcal=536, sugar_g=0.5, saturated_fat_g=3.5, sodium_mg=600, fibre_g=4, protein_g=6)),
    dict(id="02_instant_noodles", product="Instant noodles", drink=False, verdict="unhealthy", font="sans", bg=(255, 248, 225),
         lines=["NUTRITIONAL INFORMATION (Approx.)", "Per 100 g      Per serve (70 g)", "Energy (kcal)       430        301",
                "Protein (g)         9          6.3", "Total Sugars (g)    2          1.4", "Saturated Fat (g)  8          5.6",
                "Dietary Fibre (g)   3          2.1", "Sodium (mg)       1500       1050"],
         truth=dict(calories_kcal=430, sugar_g=2, saturated_fat_g=8, sodium_mg=1500, fibre_g=3, protein_g=9)),
    dict(id="03_digestive_biscuits", product="Digestive biscuits", drink=False, verdict="unhealthy", font="serif", bg=(245, 240, 230),
         lines=["Nutrition Information", "Per 100 g       Per serve (25 g)", "Energy (kcal)        480          120",
                "Protein (g)          7            1.8", "Total Sugars (g)    20            5", "Saturated Fat (g)    8            2",
                "Fibre (g)            3            0.8", "Sodium (mg)        400          100"],
         truth=dict(calories_kcal=480, sugar_g=20, saturated_fat_g=8, sodium_mg=400, fibre_g=3, protein_g=7)),
    dict(id="04_chocolate_bar", product="Chocolate bar", drink=False, verdict="unhealthy", font="sans", bg=(240, 235, 235),
         lines=["Nutrition Facts per 100 g", "Energy 540 kcal", "Protein 6 g", "Carbohydrate 58 g", "Sugars 55 g", "Fat 31 g",
                "Saturated Fat 18 g", "Fibre 3 g", "Salt 0.2 g"],
         truth=dict(calories_kcal=540, sugar_g=55, saturated_fat_g=18, sodium_mg=80, fibre_g=3, protein_g=6)),
    dict(id="05_cola_drink", product="Cola (soft drink)", drink=True, verdict="unhealthy", font="sans", bg=(252, 245, 245),
         lines=["Nutrition Information per 100 ml", "Energy 178 kJ / 42 kcal", "Protein 0 g", "Total Sugars 10.6 g",
                "Saturated Fat 0 g", "Sodium 5 mg"],
         truth=dict(calories_kcal=42, sugar_g=10.6, saturated_fat_g=0, sodium_mg=5, protein_g=0)),
    dict(id="06_orange_juice", product="Orange juice", drink=True, verdict="unhealthy", font="serif", bg=(255, 250, 235),
         lines=["Nutrition Facts (per 100 ml)", "Energy 46 kcal", "Protein 0.7 g", "Total Sugars 10 g", "Saturated Fat 0 g",
                "Dietary Fibre 0.2 g", "Sodium 2 mg"],
         truth=dict(calories_kcal=46, sugar_g=10, saturated_fat_g=0, sodium_mg=2, fibre_g=0.2, protein_g=0.7)),
    dict(id="07_plain_oats", product="Plain oats", drink=False, verdict="healthy", font="sans", bg=(248, 248, 240),
         lines=["Nutrition Facts (per 100 g)", "Energy 370 kcal", "Protein 13 g", "Carbohydrate 60 g", "Sugars 1 g", "Fat 7 g",
                "Saturated Fat 1.4 g", "Dietary Fibre 10 g", "Sodium 5 mg"],
         truth=dict(calories_kcal=370, sugar_g=1, saturated_fat_g=1.4, sodium_mg=5, fibre_g=10, protein_g=13)),
    dict(id="08_muesli", product="Muesli (no added sugar)", drink=False, verdict="healthy", font="mono", bg=(250, 247, 240),
         lines=["NUTRITION INFORMATION", "per 100 g", "Energy 360 kcal", "Protein 10 g", "Total Sugars 12 g",
                "Saturated Fat 1.5 g", "Dietary Fibre 8 g", "Sodium 30 mg"],
         truth=dict(calories_kcal=360, sugar_g=12, saturated_fat_g=1.5, sodium_mg=30, fibre_g=8, protein_g=10)),
    dict(id="09_plain_yogurt", product="Plain yogurt", drink=False, verdict="healthy", font="sans", bg=(245, 250, 252),
         lines=["Nutrition Facts per 100 g", "Energy 60 kcal", "Protein 4 g", "Total Sugars 4.5 g", "Saturated Fat 2 g",
                "Sodium 45 mg"],
         truth=dict(calories_kcal=60, sugar_g=4.5, saturated_fat_g=2, sodium_mg=45, protein_g=4)),
    dict(id="10_namkeen", product="Namkeen / bhujia", drink=False, verdict="unhealthy", font="sans", bg=(255, 245, 230),
         lines=["Nutritional Information per 100 g", "Energy 560 kcal", "Protein 15 g", "Total Sugars 3 g",
                "Saturated Fat 13 g", "Dietary Fibre 5 g", "Salt 2.3 g"],
         truth=dict(calories_kcal=560, sugar_g=3, saturated_fat_g=13, sodium_mg=920, fibre_g=5, protein_g=15)),
    dict(id="11_cookies_per_serving", product="Cookies (per serving only)", drink=False, verdict="unhealthy", font="sans", bg=(250, 245, 238),
         lines=["Serving size: 30 g", "Nutrition facts per serve", "Energy 150 kcal", "Protein 1.5 g", "Total Sugars 9 g",
                "Saturated Fat 3.6 g", "Sodium 90 mg"],
         truth=dict(calories_kcal=500, sugar_g=30, saturated_fat_g=12, sodium_mg=300, protein_g=5)),
    dict(id="12_granola_kj", product="Granola (energy in kJ)", drink=False, verdict="healthy", font="sans", bg=(248, 250, 244),
         lines=["Nutrition Facts (per 100 g)", "Energy 1550 kJ", "Protein 12 g", "Total Sugars 1 g", "Saturated Fat 1.2 g",
                "Dietary Fibre 9 g", "Sodium 8 mg"],
         truth=dict(calories_kcal=370.4, sugar_g=1, saturated_fat_g=1.2, sodium_mg=8, fibre_g=9, protein_g=12)),
]


def render(lines: List[str], font_key: str, bg: tuple, size: int = 30) -> np.ndarray:
    """Draw a label on a coloured background; returns a BGR array."""
    font = ImageFont.truetype(FONTS[font_key], size)
    title_font = ImageFont.truetype(BOLD, size + 4)
    line_h = int(size * 1.9)
    width = int(size * 24)
    image = Image.new("RGB", (width, line_h * len(lines) + 90), bg)
    draw = ImageDraw.Draw(image)
    y = 35
    draw.rectangle([10, 10, width - 10, line_h * len(lines) + 80], outline=(40, 40, 40), width=3)
    for index, text in enumerate(lines):
        draw.text((35, y), text, font=title_font if index == 0 else font, fill=(25, 25, 25))
        y += line_h
    return np.array(image)[:, :, ::-1].copy()


def make_photo_like(image: np.ndarray, seed: int) -> np.ndarray:
    """Imitate a phone photo: slight rotation, uneven light, blur, noise."""
    rng = np.random.default_rng(seed)
    h, w = image.shape[:2]
    matrix = cv2.getRotationMatrix2D((w / 2, h / 2), float(rng.uniform(-2.5, 2.5)), 1.0)
    out = cv2.warpAffine(image, matrix, (w, h), borderValue=(235, 235, 230)).astype(np.float32)
    gradient = np.linspace(rng.uniform(0.7, 0.9), 1.0, w)[None, :, None]
    out = out * gradient
    out = cv2.GaussianBlur(out, (3, 3), 0) + rng.normal(0, 8, out.shape)
    return np.clip(out, 0, 255).astype(np.uint8)


def main() -> None:
    os.makedirs(OUT_DIR, exist_ok=True)
    rows = []
    for index, label in enumerate(LABELS):
        clean = render(label["lines"], label["font"], label["bg"])
        photo = make_photo_like(clean, seed=index)
        files = {"clean": f"{label['id']}_clean.png", "photo": f"{label['id']}_photo.jpg"}
        cv2.imwrite(os.path.join(OUT_DIR, files["clean"]), clean)
        cv2.imwrite(os.path.join(OUT_DIR, files["photo"]), photo, [cv2.IMWRITE_JPEG_QUALITY, 80])
        for kind, filename in files.items():
            row = {"file": filename, "kind": kind, "product": label["product"],
                   "is_drink": int(label["drink"]), "verdict": label["verdict"]}
            for key in KEYS:
                row[key] = label["truth"].get(key, "")
            rows.append(row)
    with open(os.path.join(OUT_DIR, "ground_truth.csv"), "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["file", "kind", "product", "is_drink", "verdict"] + KEYS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} images + ground_truth.csv to {OUT_DIR}/")


if __name__ == "__main__":
    main()
