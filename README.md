# 🥗 AI-Assisted Food Label Health Scanner

Upload or capture a photo of a packaged-food **nutrition label** and get:

1. the nutrients read from the label (OCR + rule-based parsing),
2. a **Health Score (0–100)** from a transparent, rule-based formula adapted from Nutri-Score,
3. a short **plain-language explanation** written by an LLM (Groq),
4. **healthier alternatives** from the same category, found through Open Food Facts.

> **B.Tech (IIoT) minor project** — Abhinav Bhatt, University School of Automation and Robotics (USAR), GGSIPU.
> Guide: Dr. Pooja Rana.

---

## How it works

```
 Image (upload / camera)
        │
        ▼
 OpenCV preprocessing ──► Tesseract OCR (3 passes, cross-checked)
        │
        ▼
 Rule-based nutrient parser (regex)  ──►  values per 100 g / 100 ml
        │
        ▼
 Health Score  (deterministic Python, adapted Nutri-Score)
        │                         │
        ▼                         ▼
 LLM explanation            Category detection ──► Open Food Facts
 (explains only)                                    healthier alternatives
        └──────────────┬──────────┘
                       ▼
                 Streamlit UI
```

**Design rules**

* The **score is always calculated by plain Python** (`health_score.py`). The LLM never extracts nutrients and never decides or changes the score — it only explains it.
* Nutrient extraction is **regex/rule-based** (no LLM), so results are repeatable and explainable.
* Every external service can fail without breaking the app: no API key → built-in template explanation; Open Food Facts down → a message instead of alternatives; unreadable value → you can correct it by hand.

## Features

* Upload a JPG/PNG or use the camera.
* Three OCR passes with different preprocessing; values are cross-checked and repaired for common slips (`g` read as `9`, glued table columns, `lg` for `1g`).
* Understands **per 100 g/ml** and **per serving** labels (scales using the serving size), kJ → kcal, and salt → sodium.
* **Editable values**: fix any misread number and click *Recalculate* — no need to re-scan.
* **Separate, stricter scoring for drinks**; artificial sweeteners in a drink add penalty points.
* Safety caps: if key nutrients are missing or values are unverified, the score never exceeds *Moderate*.
* Category auto-detection (or choose manually) → ≥ 3 healthier alternatives when available.

## Score bands

| Score | Category |
|---|---|
| 0–20 | Poor |
| 21–40 | Below Average |
| 41–60 | Moderate |
| 61–80 | Good |
| 81–100 | Excellent |

**Method (adapted Nutri-Score).** Negative points for energy, sugars, saturated fat and sodium; positive points for fibre and protein. `raw = negative − positive`. The raw value falls in a Nutri-Score class (A–E), and each class maps to one 20-point band above. Protein is ignored when negative points are ≥ 11 (original Nutri-Score rule, because fruit/veg/nut content cannot be seen on the label). Drinks use stricter thresholds.

> ⚠️ This is an **adapted Nutri-Score-based Health Score, not the official Nutri-Score**. It cannot see fruit, vegetable or nut content, so it can differ from an official rating. It is an educational estimate, not medical or dietary advice.

---

## Installation (run on your own computer)

**Requirements:** Python 3.10+ and the Tesseract OCR engine.

```bash
# 1. Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate            # Windows
source venv/bin/activate         # macOS / Linux

# 2. Install Python packages
pip install -r requirements.txt

# 3. (Optional) create your settings file
cp .env.example .env             # Windows: copy .env.example .env

# 4. Run
streamlit run app.py
```

### Installing Tesseract (required — `pytesseract` is only a wrapper)

| System | Steps |
|---|---|
| **Windows** | Install from <https://github.com/UB-Mannheim/tesseract/wiki>, then set `TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe` in `.env` (use your real path). |
| **macOS** | `brew install tesseract` |
| **Ubuntu / Debian** | `sudo apt-get update && sudo apt-get install tesseract-ocr` |
| **Streamlit Cloud** | Nothing to do — `packages.txt` installs it automatically. |

Check it worked: `tesseract --version` should print a version number.

### AI explanation (optional but recommended)

The app works without any key (it shows a built-in template explanation). For the LLM explanation add a **free Groq key** (no card needed):

1. Sign up at <https://console.groq.com> and open **API Keys** (<https://console.groq.com/keys>).
2. Click **Create API Key** and copy it (it starts with `gsk_` and is shown only once).

Local: put it in `.env`:

```
GROQ_API_KEY=gsk_your-key-here
```

Streamlit Cloud: *App → Settings → Secrets*, then paste:

```toml
GROQ_API_KEY = "gsk_your-key-here"
```

Then reboot the app. Optional setting: `GROQ_MODEL`. If a model is busy or has been retired, the app tries another one automatically; if Groq cannot answer, the built-in explanation is shown together with the reason.
The pill on the explanation card shows whether the text came from the AI or the template.

> 🔒 **Never commit real keys.** `.env` and `.streamlit/secrets.toml` are in `.gitignore`. If a key is ever exposed, delete it and create a new one.

## Deploying on Streamlit Community Cloud

1. Push this repository to GitHub (keep every `.py` file in the repository root — do not move them into sub-folders).
2. On <https://share.streamlit.io> choose *New app*, pick the repository and set **Main file path** to `app.py`.
3. Add your API key under *Settings → Secrets* (see above).
4. Deploy. `requirements.txt` and `packages.txt` install everything, including Tesseract.

## Using the app

1. Upload a clear, straight-on photo of the **nutrition table** (or use the camera).
2. Leave the category on *Auto-detect* or choose it (drinks are scored with drink rules).
3. Click **Analyze Food Label**.
4. Compare the extracted values with the label; correct any wrong number and click **Recalculate**.
5. Read the score, explanation and alternatives.

**Photo tips:** fill the frame with the table, good light, no glare, hold the camera parallel to the label; flat labels work best, curved bottles are hardest.

## Project structure

```
app.py                  Streamlit UI (ties everything together)
pipeline.py             OCR → parse pipeline, 3-pass voting, category/drink helpers
image_preprocessing.py  OpenCV preprocessing (gentle / thresholded / plain)
ocr.py                  Tesseract wrapper with friendly errors
nutrient_parser.py      Regex nutrient parser + per-100 normalisation
health_score.py         Deterministic Health Score (adapted Nutri-Score)
ai_explanation.py       Groq explanation (+ template fallback)
category_detector.py    Keyword-based category detection
recommendations.py      Open Food Facts search + scoring of alternatives
data/sample_data.csv    20-product scoring benchmark
data/evaluation_report.md   Latest accuracy results
sample_images/          24 labelled test labels + ground_truth.csv
generate_sample_images.py   Re-creates the sample images
evaluate.py             Measures accuracy → data/evaluation_report.md
test_*.py               Automated tests (see TESTING.md)
packages.txt            apt packages for Streamlit Cloud (tesseract-ocr)
requirements.txt        Python packages
```

## Testing

```bash
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q          # ~90 s; OCR image tests are skipped if Tesseract is missing
python evaluate.py           # accuracy report
```

**Latest results on the bundled synthetic labels** (`data/evaluation_report.md`):

| Test set | Nutrient values read correctly | Healthy/unhealthy verdict correct |
|---|---|---|
| 12 clean labels | 69 / 69 | 12 / 12 |
| 12 photo-like labels (blur, noise, rotation, uneven light) | 69 / 69 | 12 / 12 |
| 20-product scoring benchmark (no OCR) | — | 20 / 20 |

These labels are **synthetic**; real photos are harder. See `TESTING.md` for the manual test plan and the edge-case checklist.

## Limitations

* OCR can still misread digits on blurred, glary, curved or low-resolution photos; always compare with the label (the editable form is there for this).
* English, printed nutrition tables only; no barcode scanning, handwriting or regional languages.
* Fruit/vegetable/nut content and food-specific Nutri-Score rules are not modelled, so scores can differ from the official Nutri-Score.
* Alternatives depend on the completeness of Open Food Facts data and need internet access; the AI explanation needs an API key and internet (a template is used otherwise).
* A single-image, single-product workflow; no user accounts or personalised scoring.

## Future scope

Barcode scanning as a faster input, a mobile app, multilingual OCR, personalised scoring profiles designed with certified nutrition professionals, and fruit/vegetable/nut estimation from the ingredients list.

## References and acknowledgements

* Santé publique France / Scientific Committee of the Nutri-Score (2022). *Update of the Nutri-Score algorithm.* <https://www.santepubliquefrance.fr/nutri-score>
* Open Food Facts contributors. *Open Food Facts: free and open database of food products.* <https://world.openfoodfacts.org/>
* Smith, R. (2007). An overview of the Tesseract OCR engine. *Proceedings of ICDAR 2007*, 2, 629–633. <https://doi.org/10.1109/ICDAR.2007.4376991>
* Built with Streamlit, OpenCV, Tesseract / pytesseract, Pandas and the Groq API.

*Educational project. Not medical or dietary advice.*

## Interface (BiteWise)

* 3-step flow: **Upload -> Review values -> Results**, with dark (default) and light themes (toggle at the top).
* Review step: every extracted value is editable; choose whether values are per 100 g/ml or per serving and enter the serving size if it was not readable. Missing values are listed so you can add them.
* Results dashboard: score ring, key nutrient tiles, AI explanation ("What lowered / helped the score?"), healthier alternatives as cards, and "Scan Another Product".
* If no better product is found, the app explains why and lets you retry or search another category.
* Theme colours live in `.streamlit/config.toml` and `ui.py`. API keys go only in environment variables / Streamlit Secrets.
* If the AI explanation falls back to the built-in text, the reason (e.g. key rejected 403, model 404, quota 429) is shown in the "Why isn't the AI explanation showing?" expander.

### Extra nutrients, allergens and ingredients (information only)

* Besides the six scored nutrients, the app reads **added sugar, total fat, carbohydrates, trans fat, potassium, calcium, iron, cholesterol and salt** when the label prints them. They appear under **More nutrients** and **never change the Health Score**.
* A nutrient the label does not list is shown as **"Not available"**, never as zero.
* **Per serving vs per 100 g** table with **% of daily intake** (2,000 kcal reference day) appears when the serving size is known; add it in the review step if the scan missed it.
* **Allergen alert** (milk, peanuts, tree nuts, soy, wheat/gluten, egg, fish, shellfish, sesame, mustard) is a separate warning from the ingredient text; paste the ingredients in the review step if the scan did not read them.
* **Ingredient analysis** gives neutral notes (added sugars, refined flour, palm/hydrogenated oils, salt sources, sweeteners). It describes ingredients and does not label them harmful.
* New files: `label_extras.py`, `favicon.png`, `generate_rich_label.py`, `test_label_extras.py`.
