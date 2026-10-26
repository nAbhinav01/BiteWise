"""
Creates sample_images/rich_label_with_extras.png - a synthetic label that also prints the
information-only nutrients (added sugar, total fat, carbohydrates, trans fat, potassium,
calcium, iron, cholesterol), an ingredient list and allergens. Used by test_app.py.

Run once:   python generate_rich_label.py
"""
from PIL import Image, ImageDraw, ImageFont

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
LINES = [
    ("NUTRITION FACTS", True),
    ("Per 100 g          Per serve (30 g)", False),
    ("Energy 520 kcal       156", False),
    ("Protein 7 g           2.1", False),
    ("Carbohydrate 62 g     18.6", False),
    ("Total Sugars 28 g     8.4", False),
    ("Added Sugars 24 g     7.2", False),
    ("Total Fat 26 g        7.8", False),
    ("Saturated Fat 12 g    3.6", False),
    ("Trans Fat 0.2 g       0.1", False),
    ("Dietary Fibre 2 g     0.6", False),
    ("Sodium 310 mg         93", False),
    ("Potassium 180 mg      54", False),
    ("Calcium 90 mg         27", False),
    ("Iron 2.1 mg           0.6", False),
    ("Cholesterol 12 mg     4", False),
    ("", False),
    ("Ingredients: Refined wheat flour (maida), Sugar,", False),
    ("Palm oil, Milk solids, Glucose syrup, Salt, Cocoa", False),
    ("powder, Emulsifier (soy lecithin).", False),
    ("Contains: Wheat, Milk, Soy.", False),
]

img = Image.new("RGB", (900, 40 + 44 * len(LINES)), (250, 250, 245))
draw = ImageDraw.Draw(img)
y = 24
for text, bold in LINES:
    draw.text((30, y), text, fill=(20, 20, 20), font=ImageFont.truetype(BOLD if bold else FONT, 30 if bold else 28))
    y += 44
img.save("sample_images/rich_label_with_extras.png")
print("saved sample_images/rich_label_with_extras.png")
