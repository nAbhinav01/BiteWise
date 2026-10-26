"""
BiteWise - AI-Assisted Food Label Health Scanner
--------------------------------------------------
Main Streamlit application.

Three-step flow:   1 Upload  ->  2 Review values  ->  3 Results

Pipeline behind it:
  image -> OpenCV preprocessing -> Tesseract OCR (cross-checked passes)
        -> regex nutrient parsing -> rule-based Health Score
        -> LLM plain-language explanation -> Open Food Facts alternatives

Design notes
  * The score is always calculated by deterministic Python (health_score.py).
    The LLM only explains it.
  * OCR can misread numbers, so the review step lets the user correct or add
    values (including the serving size) before the score is calculated.
  * All styling lives in ui.py; this file holds the flow and the logic wiring.
"""

import io
import json
import os
import random
import uuid

import streamlit as st

import ui
from ai_explanation import explain_score, key_status
from category_detector import UNKNOWN_LABEL, category_labels, get_off_tags
from health_score import calculate_health_score
from label_extras import (REFERENCE_NOTE, allergen_source_text, analyze_ingredients, daily_share, detect_allergens,
                          extract_ingredients, first_ingredient_note, per_serving, split_ingredients)
from nutrient_parser import ALL_DISPLAY, DISPLAY_NAMES, EXTRA_DISPLAY, EXTRA_KEYS, NUTRIENT_KEYS, count_found
from pipeline import AUTO_DETECT, detect_sweeteners, is_drink, resolve_category, run_ocr_pipeline
from recommendations import clear_cache, find_alternatives

MIN_NUTRIENTS_TO_SCORE = 3
BASIS_100 = "Per 100 g / 100 ml"
BASIS_SERVING = "Per serving"
BASIS_UNSURE = "Not sure"

# One-sentence explanations shown in the "?" tooltips of the value fields.
FIELD_HELP = {
    "calories_kcal": "Energy: the calories in 100 g (or 100 ml) of the product, in kcal.",
    "sugar_g": "Total sugars (natural + added) in grams. Lower is better.",
    "saturated_fat_g": "The type of fat that is best kept low. Lower is better.",
    "sodium_mg": "Sodium in mg (the part of salt that matters). If only salt is printed, salt in g x 400 = sodium in mg.",
    "fibre_g": "Dietary fibre in grams. Helps digestion and keeps you full - higher is better.",
    "protein_g": "Protein in grams. Counts as a positive, higher is better.",
}
FIELD_HELP.update({
    "added_sugar_g": "Sugar added during manufacturing, in grams. It is part of total sugars, not an extra amount on top.",
    "total_fat_g": "All fat in grams (saturated fat is part of it).",
    "carbs_g": "Total carbohydrates in grams (sugars and fibre are part of it).",
    "trans_fat_g": "Trans fat in grams. Separate from saturated fat - best kept as low as possible.",
    "potassium_mg": "Potassium in mg. Only enter it if the label prints it.",
    "calcium_mg": "Calcium in mg. Mostly on fortified foods and dairy.",
    "iron_mg": "Iron in mg. Mostly on fortified foods and cereals.",
    "cholesterol_mg": "Cholesterol in mg, if printed.",
    "salt_g": "Salt in grams, if printed. Salt and sodium are related but not the same number.",
})
FIELD_STEP = {"calories_kcal": 1.0, "sodium_mg": 5.0, "potassium_mg": 5.0, "calcium_mg": 5.0, "cholesterol_mg": 5.0}

_ICON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "favicon.png")
st.set_page_config(page_title="BiteWise - Food Label Health Scanner",
                   page_icon=_ICON if os.path.exists(_ICON) else "🔍", layout="centered")

# --------------------------------------------------------------------------
# Session state
# --------------------------------------------------------------------------
state = st.session_state
state.setdefault("step", 1)
state.setdefault("quote_i", random.randrange(len(ui.QUOTES)))
ui.inject_css(light=bool(state.get("light_mode", False)))

left, right = st.columns([5, 2], vertical_alignment="center")
with left:
    ui.render(ui.brand_bar())
with right:
    st.toggle("Light mode", key="light_mode")


def go(step: int) -> None:
    """Move to another step and redraw."""
    state["step"] = step
    st.rerun()


def start_over() -> None:
    state.pop("analysis", None)
    state["step"] = 1


analysis = state.get("analysis")
if state["step"] != 1 and not analysis:
    state["step"] = 1
quote = ui.QUOTES[state["quote_i"] % len(ui.QUOTES)]


# ==========================================================================
# STEP 1 - Upload
# ==========================================================================
def step_upload() -> None:
    ui.hero(quote)
    ui.steps(1)

    with st.container(border=True, key="upload_card"):
        ui.upload_header()
        method = st.radio("How would you like to add the label?", ["Upload image", "Use camera"],
                          horizontal=True, label_visibility="collapsed")
        if method == "Upload image":
            picked = st.file_uploader("Nutrition label image", type=["jpg", "jpeg", "png"],
                                      label_visibility="collapsed")
        else:
            picked = st.camera_input("Take a photo of the nutrition label", label_visibility="collapsed")

        image_bytes = picked.getvalue() if picked else (analysis["original"] if analysis else None)
        image_name = (getattr(picked, "name", None) or "camera photo") if picked else (analysis["name"] if analysis else "")
        if image_bytes:
            ui.ready_row(image_name, image_bytes)

    st.write("")
    category_choice = st.selectbox(
        "Product category",
        options=[AUTO_DETECT] + category_labels() + [UNKNOWN_LABEL],
        help="Auto-detect guesses the category from the label text. Drinks are scored with stricter drink rules, "
        "so choose it yourself if you know it.",
    )
    st.caption("Tip: photograph the nutrition table straight-on, in good light, filling the frame.")

    if st.button("Analyze Food Label", type="primary", width="stretch"):
        if not image_bytes:
            st.warning("Please upload or capture an image first.")
            return
        with st.status("Analyzing your label...", expanded=True) as status:
            def progress(message: str) -> None:
                st.write(f"✓ {message}")

            try:
                ocr = run_ocr_pipeline(io.BytesIO(image_bytes), progress=progress)
                progress("Preparing your results...")
            except (ValueError, RuntimeError) as error:
                status.update(label="Analysis failed", state="error", expanded=True)
                st.error(str(error))
                return
            status.update(label="Analysis complete", state="complete", expanded=False)

        parsed = ocr["parsed"]
        state["analysis"] = {
            "id": uuid.uuid4().hex[:8], "original": image_bytes, "name": image_name,
            "processed": ocr["processed"], "text": ocr["text"], "parsed": parsed,
            "values": {key: parsed[key] for key in NUTRIENT_KEYS},
            "basis": BASIS_100 if parsed["normalized"] else (BASIS_SERVING if parsed["serving_basis"] == "per serving" else BASIS_UNSURE),
            "extras": {key: parsed[key] for key in EXTRA_KEYS},
            "ingredients_text": extract_ingredients(ocr["text"]),
            "serving_size": parsed.get("serving_size"), "category_choice": category_choice, "explanation": None,
        }
        state["quote_i"] += 1
        st.toast("Analysis complete", icon="✅")
        go(2)


# ==========================================================================
# STEP 2 - Review values
# ==========================================================================
def step_review() -> None:
    ui.steps(2)
    parsed, values = analysis["parsed"], analysis["values"]
    ui.render('<div class="nl-card" style="margin-bottom:.6rem"><h3>' + ui.icon("scan", 20) + " Check the values we read</h3>"
              '<div class="nl-muted">Analysis complete &middot; compare with your label before calculating.</div></div>')
    ui.note("Please check the extracted values. OCR can misread numbers. Correct them before calculating your score.")

    # --- tell the user exactly what is missing / uncertain -----------------
    missing = [DISPLAY_NAMES[k][0] for k in NUTRIENT_KEYS if values[k] is None]
    issues = []
    if missing:
        issues.append(f"<b>Not available:</b> {', '.join(missing)}. If they are printed on your label, type them in below. "
                      "Leave them empty if the label doesn't list them.")
        key_missing = [m for m in missing if m in ("Energy", "Sugars", "Saturated Fat", "Sodium")]
        if key_missing:
            issues.append("Missing energy, sugars, saturated fat or sodium limits the score to <b>Moderate</b> - adding them gives an exact score.")
    if analysis["basis"] == BASIS_SERVING:
        issues.append("These values look like they are <b>per serving</b> and the serving size could not be read. "
                      "Enter the serving size below so we can convert to per 100 g/ml.")
    elif analysis["basis"] == BASIS_UNSURE:
        issues.append("We couldn't tell whether the values are <b>per 100 g/ml or per serving</b>. Pick the right option below.")
    if issues:
        ui.attention("A few things need your attention", issues)

    # --- editable form ------------------------------------------------------
    with st.form(f"review_{analysis['id']}", border=True):
        columns = st.columns(3)
        entered = {}
        for index, key in enumerate(NUTRIENT_KEYS):
            name, unit = DISPLAY_NAMES[key]
            suffix = "_missing" if parsed[key] is None else ""
            with columns[index % 3]:
                entered[key] = st.number_input(
                    f"{name} ({unit})", min_value=0.0, value=values[key], step=FIELD_STEP.get(key, 0.1),
                    format="%.2f", placeholder="Not available", help=FIELD_HELP[key],
                    key=f"nv_{key}_{analysis['id']}{suffix}",
                )
        with st.expander("More nutrients and ingredients (optional)"):
            st.caption("For information only - these never change the Health Score. Leave a box empty if the label doesn't print it; "
                       "empty means \"Not available\", not zero.")
            extra_cols = st.columns(3)
            entered_extras = {}
            for index, key in enumerate(EXTRA_KEYS):
                name, unit = EXTRA_DISPLAY[key]
                with extra_cols[index % 3]:
                    entered_extras[key] = st.number_input(
                        f"{name} ({unit})", min_value=0.0, value=analysis["extras"][key], step=FIELD_STEP.get(key, 0.1),
                        format="%.2f", placeholder="Not available", help=FIELD_HELP[key],
                        key=f"nx_{key}_{analysis['id']}",
                    )
            ingredients = st.text_area(
                "Ingredients (optional)", value=analysis["ingredients_text"], height=90,
                placeholder="Paste or type the ingredient list to get allergen alerts and ingredient notes",
                help="Used only for allergen alerts and ingredient notes. Copy it from the pack if the scan did not read it.",
                key=f"ing_{analysis['id']}")
        basis_col, size_col = st.columns(2)
        with basis_col:
            basis_options = [BASIS_100, BASIS_SERVING, BASIS_UNSURE]
            basis = st.selectbox("These values are...", basis_options, index=basis_options.index(analysis["basis"]),
                                 help="Check the header of the nutrition table: 'per 100 g' or 'per serving'.")
        with size_col:
            serving = st.number_input("Serving size (g or ml)", min_value=1.0, value=analysis["serving_size"], step=1.0,
                                      placeholder="e.g. 30", format="%.0f",
                                      help="Needed to convert per-serving values, and to show amounts per serving and % of daily intake. "
                                      "It is printed near the top of the table, e.g. 'Serving size 30 g'.")
        back_col, go_col = st.columns([1, 2])
        with back_col:
            back = st.form_submit_button("← Back", width="stretch")
        with go_col:
            calculate = st.form_submit_button("Calculate Health Score →", type="primary", width="stretch")

    if back:
        go(1)
    if calculate:
        analysis.update(values=entered, extras=entered_extras, ingredients_text=ingredients.strip(),
                        basis=basis, serving_size=serving, explanation=None)
        if count_found(entered) < MIN_NUTRIENTS_TO_SCORE:
            st.error(f"Please provide at least {MIN_NUTRIENTS_TO_SCORE} nutrient values "
                     f"(you have {count_found(entered)}) to calculate a Health Score.")
        else:
            go(3)

    # --- technical details stay collapsed -----------------------------------
    with st.expander("Raw OCR text and image"):
        st.image(analysis["original"], caption="Your image", width="stretch")
        st.image(analysis["processed"], caption="Preprocessed image (what the OCR engine read)", width="stretch")
        st.text_area("Text read from the label", value=analysis["text"] or "(nothing detected)", height=170, disabled=True)
    with st.expander("Parser notes"):
        for note_text in parsed["notes"] or ["No notes."]:
            st.write(f"- {note_text}")


# ==========================================================================
# STEP 3 - Results
# ==========================================================================
def per100_values():
    """All nutrient values (scored + information-only) as per 100 g/ml, using the basis chosen in the review step."""
    values = {**analysis["values"], **analysis["extras"]}
    if analysis["basis"] == BASIS_SERVING and analysis["serving_size"]:
        size = analysis["serving_size"]
        return {k: (None if v is None else round(v * 100.0 / size, 2)) for k, v in values.items()}
    return values


def scoring_inputs():
    """Values the Health Score uses (the six core nutrients only) + the 'normalized' flag."""
    values = per100_values()
    basis, size = analysis["basis"], analysis["serving_size"]
    normalized = basis == BASIS_100 or (basis == BASIS_SERVING and bool(size))
    return dict({k: values[k] for k in NUTRIENT_KEYS}, normalized=normalized)


def step_results() -> None:
    ui.steps(3)
    parsed, text = analysis["parsed"], analysis["text"]
    inputs = scoring_inputs()
    category = resolve_category(analysis["category_choice"], text)
    drink = is_drink(category, parsed["serving_basis"])
    ingredient_text = analysis["ingredients_text"]
    sweeteners = detect_sweeteners(text + " " + ingredient_text)
    result = calculate_health_score(inputs, is_drink=drink, has_sweeteners=sweeteners)

    ui.render(f'<div class="nl-sec" style="margin-top:.2rem">{ui.icon("chart", 22)}Your results</div>'
              f'<div class="nl-quote">{ui.icon("quote", 18)}<span>&ldquo;{ui.esc(quote)}&rdquo;</span></div>')

    if result["score"] is None:
        st.warning("Not enough nutrient data to calculate a Health Score.")
        if st.button("← Add or fix values"):
            go(2)
        return

    # --- is the score only an estimate? (missing key values / unknown basis) ----
    reasons = []
    if result["missing_negative"]:
        reasons.append(f"Missing: <b>{', '.join(result['missing_negative'])}</b> - add them to get an exact score.")
    if analysis["basis"] == BASIS_SERVING and not analysis["serving_size"]:
        reasons.append("The values are per serving but no serving size was entered, so they could not be converted to per 100 g/ml.")
    elif not inputs["normalized"]:
        reasons.append("We couldn't confirm that the values are per 100 g/ml.")

    unit_label = "100 ml" if drink else "100 g"
    ui.score_card(result, drink, category, estimate=bool(reasons))
    ui.key_heading("Key nutrients", f"per {unit_label} \u00b7 used in the Health Score" if inputs["normalized"] else "as read from the label \u00b7 used in the Health Score")
    ui.nutrient_tiles(result)
    if reasons:
        title = "This score is an estimate" + (" (capped at Moderate)" if result["capped"] else "")
        ui.attention(title, reasons)
        if st.button("✏️ Add or fix values", key="fix_values"):
            go(2)

    # --- information-only extras (never part of the score) -----------------------
    per100 = per100_values()
    with st.expander("More nutrients"):
        ui.extra_tiles([(name, unit, per100[key]) for key, (name, unit) in EXTRA_DISPLAY.items()])
        st.caption("Shown for information only - they are not part of the Health Score. \"Not available\" means the label "
                   "didn't list it. It does not mean zero.")

    size = analysis["serving_size"]
    with st.expander("Per serving and daily intake", expanded=bool(size and inputs["normalized"])):
        if not inputs["normalized"]:
            ui.note("Choose whether the values are per 100 g/ml or per serving in the review step to see this table.")
        else:
            rows = []
            for key, (name, unit) in ALL_DISPLAY.items():
                serving_amount = per_serving(per100[key], size)
                rows.append(dict(key=key, name=name, unit=unit, per100=per100[key], serving=serving_amount,
                                 share=daily_share(key, serving_amount)))
            serving_label = f"{size:g} {'ml' if drink else 'g'}" if size else None
            ui.nutrition_table(rows, unit_label, serving_label, REFERENCE_NOTE)
            if not size:
                st.caption("Add the serving size to see amounts per serving and % of daily intake.")
                if st.button("Add serving size", key="add_serving"):
                    go(2)

    # --- allergens: a separate warning, never part of the score ----------------------
    allergens = detect_allergens(allergen_source_text(text, ingredient_text))
    ui.allergen_card(allergens, has_text=bool(allergen_source_text(text, ingredient_text).strip()))

    # --- explanation (AI explains only; score is already fixed) --------------
    key = json.dumps([inputs, category, drink, sweeteners], sort_keys=True)
    cached = analysis.get("explanation")
    if not cached or cached[0] != key:
        with st.spinner("Writing your explanation..."):
            body, source = explain_score(inputs, result, category)
        analysis["explanation"] = cached = (key, body, source)
    lowered, helped = ui.drivers(result)
    ui.explanation_card(cached[1], cached[2], lowered, helped)
    if cached[2].startswith("Template"):
        with st.expander("Why isn't the AI explanation showing?"):
            st.write(cached[2].replace("Template (", "").rstrip(")").capitalize() + ".")
            st.write("**What this app can see in Settings → Secrets** (names only, never the keys):")
            for label, status in key_status():
                st.write(f"- {label}: {status}")
            st.write("What to check: in **Settings → Secrets** there is a line `GROQ_API_KEY = \"gsk_...\"` (with quotes), "
                     "the key was created at console.groq.com/keys, and the app was rebooted after saving. "
                     "If it says the usage limit was reached or Groq took too long, wait a minute and try again. "
                     "The built-in explanation above is always available as a fallback.")
            if st.button("🔄 Try the AI explanation again", key="retry_ai"):
                analysis["explanation"] = None
                st.rerun()

    # --- ingredient analysis (neutral notes) -----------------------------------------
    items = split_ingredients(ingredient_text)
    with st.expander("Ingredient analysis", expanded=bool(items)):
        if items:
            ui.ingredients_card(items, analyze_ingredients(items), first_ingredient_note(items))
        else:
            ui.note("No ingredient list was read from this label. Add it in the review step to get ingredient notes and allergen alerts.")
            if st.button("Add ingredients", key="add_ingredients"):
                go(2)

    # --- alternatives ----------------------------------------------------------
    ui.section("Healthier alternatives", "leaf")
    if category is None:
        ui.empty_state("Choose a category to compare", "We couldn't tell what kind of product this is. Pick a category and we'll look for better options.")
        pick_category()
    else:
        st.caption(f"Category: {category}")
        with st.spinner("Finding healthier options..."):
            alternatives, message = find_alternatives(
                get_off_tags(category), result["score"], is_drink=drink, current_values=inputs)
        if alternatives:
            ui.alternatives_grid(alternatives)
            if message:
                st.caption(message)
        else:
            ui.empty_state(
                "No better match found - yet",
                f"{ui.esc(message)}<br>You can try again, or search a different category.")
            retry, other = st.columns(2)
            with retry:
                if st.button("🔄 Try again", width="stretch"):
                    clear_cache()
                    st.rerun()
            with other:
                pick_category(exclude=category)

    # --- navigation ---------------------------------------------------------------
    st.write("")
    back_col, new_col = st.columns([1, 2])
    with back_col:
        if st.button("← Edit values", width="stretch"):
            go(2)
    with new_col:
        if st.button("Scan Another Product", type="primary", width="stretch"):
            start_over()
            st.rerun()
    ui.footnote("Educational project. The Health Score is an adapted Nutri-Score-based estimate from the label, not medical or dietary advice.")


def pick_category(exclude=None) -> None:
    """Dropdown that switches the category used for scoring type and alternatives."""
    options = [c for c in category_labels() if c != exclude]

    def _switch() -> None:
        analysis["category_choice"] = state["alt_category"]

    st.selectbox("Search another category", options, index=None, placeholder="Choose a category",
                 key="alt_category", on_change=_switch)


# --------------------------------------------------------------------------
if state["step"] == 1:
    step_upload()
elif state["step"] == 2:
    step_review()
else:
    step_results()
