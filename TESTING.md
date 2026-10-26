# Testing Guide (Phase 9)

This project is tested at four levels. All automatic tests run with one command:

```
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q            # ~90 seconds (OCR runs on 24 sample images)
```
Tesseract must be installed for the image tests (they are skipped otherwise).

## 1. Unit tests (one file per module)

| File | What it checks |
|---|---|
| `test_parser.py` | Regex parsing: spec sample text, salt→sodium, kJ→kcal, per-100 vs per-serving, serving-size scaling, two-column labels, glued columns, ingredient-list noise, OCR slips ("lg", "5o", "g" read as "9"), missing nutrients, empty text |
| `test_score.py` | Health Score rules: Nutri-Score-style points, drink thresholds, sweeteners, protein rule, caps for missing/unverified data, band mapping, determinism, and a 10-product benchmark (unhealthy ≤ 40, healthy ≥ 61) |
| `test_recommend.py` | Category detection, Open Food Facts → nutrient conversion, filtering/sorting alternatives, network failure handled |
| `test_ai.py` | LLM prompt, Groq responses (mocked), model fallback and discovery, key diagnostics, fallback on network error / bad response / missing key |
| `test_pipeline.py` | Category resolution, drink detection, sweetener detection, OCR voting, a rendered label through OCR→parser→score |

## 2. Error-handling tests — `test_errors.py`
Invalid image, empty image, blank image (empty OCR), text with no nutrients, Tesseract missing, only 2 nutrients (no score), `None`/empty text.
(Open Food Facts failure, LLM failure and missing API key are in `test_recommend.py` / `test_ai.py`.)

## 3. Sample-data tests — `test_samples.py`, `evaluate.py`
* `data/sample_data.csv` — 20 products with typical values (unhealthy / moderate / healthy). Scoring must put each on the right side.
* `sample_images/` — 12 synthetic labels in two versions: **clean** and **photo-like** (blur, noise, rotation, uneven light, JPEG). `ground_truth.csv` holds the correct values.
* `python evaluate.py` prints accuracy and saves `data/evaluation_report.md` — use these numbers in the report's *Results* section.

Latest results on the synthetic samples: see `data/evaluation_report.md`.

## 4. End-to-end app tests — `test_app.py`
Runs the real `app.py` with Streamlit's AppTest (real OCR/parser/scorer; Open Food Facts and LLM mocked): no-image warning, unhealthy label scores low, healthy label scores high, correcting a value recalculates, switching category to drink changes scoring.

---

## Manual test plan (do this with REAL labels before the viva)

Synthetic labels are easier than real photos, so test real packets too. Take 8–10 photos
(snacks, biscuits, cereal, a drink, a healthy item) and fill in this table:

| # | Product | Photo type (flat/curved/glare) | OCR read all 6 values? | Values correct? | Score | Sensible? | Notes |
|---|---|---|---|---|---|---|---|
| 1 | | | | | | | |
| 2 | | | | | | | |

"Sensible?" = unhealthy foods score ≤ 40, healthy foods ≥ 61. If a value is wrong, correct it
in the app (Recalculate) and note it — this is useful evidence for the *Limitations* section.

## Edge-case checklist (manual, in the running app)

- [ ] Click **Analyze** with no image → warning, no crash
- [ ] Upload a non-image renamed to `.png` → friendly error
- [ ] Upload a photo with no nutrition table → "Could not detect…" message, form still usable
- [ ] Remove the `GROQ_API_KEY` secret → "Source: Template…" explanation appears
- [ ] Disconnect the internet → alternatives section shows a message, rest still works
- [ ] Choose "Other / Not sure" category → asks you to choose a category for alternatives
- [ ] Change the category dropdown after analysis → scores update without re-running OCR
- [ ] Edit a nutrient value → click **Recalculate** → score and explanation update

## Known limitations found by testing
* OCR can misread digits on blurred / glare-affected photos; the app cross-checks three OCR passes and lets you correct values, but a wrong digit can still slip through.
* Curved labels (bottles) and very small print are the hardest cases.
* Score ignores fruit/vegetable/nut content, so it can differ from the official Nutri-Score.
