"""
UI components for BiteWise (look & feel only - no business logic).

Everything visual lives here so app.py stays readable:
  * a small design system (dark charcoal + mint green, optional cream + forest
    green light theme) injected as CSS variables
  * HTML builders for the hero, step tracker, upload card, score ring,
    nutrient tiles, explanation card and alternative cards

Colour rules (same in both themes): green = positive, amber = warning,
red = genuinely poor. Score bands: Poor red, Below Average orange,
Moderate amber, Good light green, Excellent green.
"""

import base64
import html
import io
from typing import Dict, List, Optional

import streamlit as st

# --------------------------------------------------------------------------
# Palette
# --------------------------------------------------------------------------
BAND_COLORS = {
    "Poor": "#ef5b4f",
    "Below Average": "#f39a3d",
    "Moderate": "#f2c14e",
    "Good": "#8bd36a",
    "Excellent": "#34c77b",
}
BAND_ORDER = ["Poor", "Below Average", "Moderate", "Good", "Excellent"]
BAND_SUMMARY = {
    "Poor": "Poor nutritional quality. Best kept as a rare treat.",
    "Below Average": "Below-average nutritional quality. Enjoy only occasionally.",
    "Moderate": "Moderate nutritional quality. Fine in moderation.",
    "Good": "Good nutritional quality. A reasonable everyday choice.",
    "Excellent": "Excellent nutritional quality. A great everyday choice.",
}
GOOD, WARN, BAD = "#34c77b", "#f2c14e", "#ef5b4f"

THEMES = {
    "dark": dict(
        bg="#121615", glow="rgba(52,199,123,0.13)", card="#1b2220", card2="#222b28",
        border="#2d3935", text="#f2f5f3", muted="#9aa8a1", brand="#34c77b",
        brand2="#1f9d5c", ink="#06130c", shadow="0 8px 30px rgba(0,0,0,0.35)",
        track="#2b3632", input="#161c1a", chip="rgba(52,199,123,0.12)",
    ),
    "light": dict(
        bg="#faf6ea", glow="rgba(31,111,67,0.10)", card="#ffffff", card2="#f6f1e2",
        border="#e5dcc2", text="#17301f", muted="#5f7366", brand="#1f6f43",
        brand2="#2e9e5f", ink="#ffffff", shadow="0 8px 26px rgba(60,50,20,0.10)",
        track="#e9e2cb", input="#fffdf6", chip="rgba(31,111,67,0.10)",
    ),
}

QUOTES = [
    "Small choices add up to healthier habits.",
    "Know what's in your food.",
    "Read the label. Understand the choice.",
]

_ICONS = {
    "leaf": '<path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z"/><path d="M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 12 13 13 12"/>',
    "upload": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" x2="12" y1="3" y2="15"/>',
    "scan": '<path d="M3 7V5a2 2 0 0 1 2-2h2"/><path d="M17 3h2a2 2 0 0 1 2 2v2"/><path d="M21 17v2a2 2 0 0 1-2 2h-2"/><path d="M7 21H5a2 2 0 0 1-2-2v-2"/><path d="M7 8h8"/><path d="M7 12h10"/><path d="M7 16h6"/>',
    "chart": '<path d="M3 3v18h18"/><path d="M18 17V9"/><path d="M13 17V5"/><path d="M8 17v-3"/>',
    "sparkles": '<path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3Z"/>',
    "check": '<polyline points="20 6 9 17 4 12"/>',
    "alert": '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
    "image": '<rect width="18" height="18" x="3" y="3" rx="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.09-3.09a2 2 0 0 0-2.82 0L6 21"/>',
    "basket": '<path d="m15 11-1 9"/><path d="m19 11-4-7"/><path d="M2 11h20"/><path d="m3.5 11 1.6 7.4a2 2 0 0 0 2 1.6h9.8a2 2 0 0 0 2-1.6l1.7-7.4"/><path d="M4.5 15.5h15"/><path d="m5 11 4-7"/><path d="m9 11 1 9"/>',
    "search": '<circle cx="11" cy="11" r="7.5"/><path d="m21 21-4.35-4.35"/>',
    "shield": '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/><path d="M12 8v4"/><path d="M12 16h.01"/>',
    "list": '<path d="m3 17 2 2 4-4"/><path d="m3 7 2 2 4-4"/><path d="M13 6h8"/><path d="M13 12h8"/><path d="M13 18h8"/>',
    "plus": '<circle cx="12" cy="12" r="10"/><path d="M8 12h8"/><path d="M12 8v8"/>',
    "scale": '<path d="m16 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/><path d="m2 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z"/><path d="M7 21h10"/><path d="M12 3v18"/><path d="M3 7h2c2 0 5-1 7-2 2 1 5 2 7 2h2"/>',
    "quote": '<path d="M3 21c3 0 7-1 7-8V5c0-1.25-.76-2-2-2H4c-1.25 0-2 .75-2 2v6c0 1.25.75 2 2 2h4"/><path d="M15 21c3 0 7-1 7-8V5c0-1.25-.76-2-2-2h-4c-1.25 0-2 .75-2 2v6c0 1.25.75 2 2 2h4"/>',
}


def icon(name: str, size: int = 20) -> str:
    """Inline SVG icon (stroke follows the current text colour)."""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" '
            f'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
            f'stroke-linejoin="round">{_ICONS[name]}</svg>')


def _h(markup: str) -> str:
    """Collapse HTML to one line: Streamlit's markdown turns indented or blank-line-separated
    HTML into code blocks, so nothing may start a line with spaces."""
    return "".join(line.strip() for line in markup.splitlines() if line.strip())


def render(markup: str) -> None:
    """Render an HTML snippet."""
    st.markdown(_h(markup), unsafe_allow_html=True)


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def band_color(category: Optional[str]) -> str:
    return BAND_COLORS.get(category or "", "#9aa8a1")


# --------------------------------------------------------------------------
# CSS
# --------------------------------------------------------------------------
_STATIC_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
html, body, .stApp, .stApp button, .stApp input, .stApp textarea, .stApp select {
  font-family: 'Plus Jakarta Sans', system-ui, -apple-system, 'Segoe UI', sans-serif !important; }
.stApp { background: radial-gradient(900px 420px at 88% -8%, var(--glow), transparent 60%),
         radial-gradient(700px 380px at -5% 30%, var(--glow), transparent 65%), var(--bg) !important;
         color: var(--text); }
[data-testid="stHeader"] { background: transparent !important; }
[data-testid="stAppDeployButton"], [data-testid="stDecoration"], footer { display: none !important; }
.block-container { max-width: 1080px !important; padding: 4rem 1.2rem 4rem !important; }
h1, h2, h3, h4, h5 { color: var(--text) !important; letter-spacing: -0.01em; }
.stApp p, .stApp li, .stApp label, [data-testid="stWidgetLabel"] p,
[data-testid="stMarkdownContainer"] p { color: var(--text); }
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p { color: var(--muted) !important; }
a { color: var(--brand); }

/* ---------- brand / hero ---------- */
.nl-top { display:flex; align-items:center; gap:.7rem; margin: .2rem 0 .4rem; }
.nl-logo { width:42px; height:42px; border-radius:12px; display:grid; place-items:center;
  background: linear-gradient(145deg, #2a8a56, #1c6a3f); color: #ffffff;
  box-shadow: 0 6px 18px var(--glow); }
.nl-brand { font-weight:800; font-size:1.35rem; color:var(--text); letter-spacing:-0.02em; line-height:1.1; }
.nl-brand b { color: var(--brand); }
.nl-brand-sub { display:block; font-weight:500; font-size:.74rem; color:var(--muted); letter-spacing:0; }
.nl-hero h1 { font-size: clamp(2rem, 5vw, 3.1rem); line-height:1.08; font-weight:800; margin: 1.1rem 0 .6rem; padding:0; }
.nl-hero h1 span { color: var(--brand); }
.nl-sub { font-size:1.05rem; color:var(--muted) !important; max-width: 36rem; margin:0 0 1.1rem; }
.nl-features { display:grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap:.7rem; margin: .4rem 0 1rem; }
.nl-feature { display:flex; gap:.7rem; align-items:center; background:var(--card); border:1px solid var(--border);
  border-radius:16px; padding:.75rem .9rem; transition: border-color .2s, transform .2s; }
.nl-feature:hover { border-color: var(--brand); transform: translateY(-2px); }
.nl-ficon { color: var(--brand); display:grid; place-items:center; width:38px; height:38px; border-radius:11px; background: var(--chip); flex:none; }
.nl-feature b { display:block; color:var(--text); font-size:.95rem; }
.nl-feature small { color:var(--muted); font-size:.8rem; }
.nl-quote { display:flex; gap:.6rem; align-items:flex-start; color:var(--muted); font-style:italic; font-size:.98rem; margin:.2rem 0 1rem; }
.nl-quote svg { color: var(--brand); flex:none; margin-top:2px; }

/* ---------- step tracker ---------- */
.nl-steps { display:flex; align-items:center; gap:.5rem; margin: .6rem 0 1.2rem; flex-wrap:wrap; }
.nl-step { display:flex; align-items:center; gap:.55rem; color:var(--muted); font-weight:600; font-size:.9rem; }
.nl-dot { width:30px; height:30px; border-radius:50%; display:grid; place-items:center; border:2px solid var(--border);
  background:var(--card); font-size:.82rem; font-weight:700; color:var(--muted); }
.nl-step.done .nl-dot { background: var(--brand); border-color: var(--brand); color: var(--ink); }
.nl-step.active .nl-dot { border-color: var(--brand); color: var(--brand); box-shadow: 0 0 0 4px var(--chip); }
.nl-step.active, .nl-step.done { color: var(--text); }
.nl-line { flex: 1 1 28px; min-width:24px; max-width:90px; height:2px; background:var(--border); border-radius:2px; }
.nl-line.done { background: var(--brand); }

/* ---------- cards ---------- */
.nl-card { background:var(--card); border:1px solid var(--border); border-radius:20px; padding:1.2rem 1.3rem;
  box-shadow: var(--shadow); transition: border-color .2s, transform .2s; margin-bottom: .9rem; }
.nl-card:hover { border-color: color-mix(in srgb, var(--brand) 55%, var(--border)); }
.nl-card h3 { margin:0 0 .6rem; font-size:1.05rem; font-weight:700; display:flex; align-items:center; gap:.5rem; }
.nl-card h3 svg { color: var(--brand); }
.nl-eyebrow { font-size:.72rem; letter-spacing:.12em; text-transform:uppercase; color:var(--muted); font-weight:700; margin-bottom:.5rem; }
.nl-muted { color: var(--muted); }
.nl-note { border-left:4px solid var(--brand); background: var(--chip); border-radius: 0 12px 12px 0;
  padding:.7rem 1rem; margin: .2rem 0 1rem; color: var(--text); font-weight:600; font-size:.93rem; }
.nl-attn { border:1px solid color-mix(in srgb, var(--warn) 55%, transparent); background: color-mix(in srgb, var(--warn) 11%, var(--card));
  border-radius:16px; padding:.9rem 1.1rem; margin:.4rem 0 1rem; }
.nl-attn b { color: var(--warn); display:flex; gap:.45rem; align-items:center; margin-bottom:.35rem; }
.nl-attn ul { margin:.2rem 0 0 1.1rem; padding:0; color:var(--text); font-size:.92rem; }
.nl-attn li { margin:.2rem 0; }

/* ---------- upload card ---------- */
.st-key-upload_card { background:var(--card); border:2px dashed color-mix(in srgb, var(--brand) 55%, var(--border)) !important;
  border-radius:24px !important; padding: 1.4rem 1.4rem .6rem !important; box-shadow: var(--shadow); }
.nl-drop { text-align:center; padding:.2rem 0 .6rem; }
.nl-drop .nl-dropicon { width:56px; height:56px; margin:0 auto .6rem; border-radius:16px; display:grid; place-items:center;
  background: var(--chip); color: var(--brand); }
.nl-drop h3 { margin:.1rem 0 .25rem; font-size:1.25rem; font-weight:800; color:var(--text); }
.nl-drop p { margin:.1rem 0; color:var(--muted) !important; font-size:.95rem; }
.nl-pill { display:inline-block; padding:.18rem .7rem; border-radius:999px; background:var(--chip); color:var(--brand);
  font-weight:700; font-size:.78rem; margin:.5rem .2rem .2rem; border:1px solid color-mix(in srgb, var(--brand) 35%, transparent); }
.nl-ready { display:flex; gap:.9rem; align-items:center; background: var(--chip); border:1px solid color-mix(in srgb, var(--brand) 40%, transparent);
  border-radius:16px; padding:.6rem .8rem; margin:.5rem 0 .9rem; }
.nl-ready img { width:58px; height:58px; object-fit:cover; border-radius:12px; border:1px solid var(--border); }
.nl-ready b { color: var(--text); display:block; word-break: break-all; }
.nl-ready span { color: var(--brand); font-weight:700; font-size:.85rem; display:flex; align-items:center; gap:.3rem; }
[data-testid="stFileUploaderDropzone"] { background: transparent !important; border: none !important; justify-content:center; padding:.4rem 0 !important; }
[data-testid="stFileUploaderDropzoneInstructions"] { display:none !important; }
[data-testid="stFileUploaderFile"] { display:none !important; }
[data-testid="stFileUploader"] section button { border:1px solid var(--brand) !important; color: var(--brand) !important; background: transparent !important;
  border-radius: 999px !important; padding:.45rem 1.4rem !important; font-weight:700 !important; }
[data-testid="stFileUploader"] section button:hover { background: var(--chip) !important; }
[data-testid="stCameraInput"] { border-radius: 18px; overflow:hidden; }

/* radio as pill tabs */
div[role="radiogroup"] { gap:.4rem !important; justify-content:center; }
div[role="radiogroup"] > label { background: var(--card2); border:1px solid var(--border); border-radius:999px; padding:.4rem 1.1rem !important; cursor:pointer; transition: all .15s; }
div[role="radiogroup"] > label > div:first-child { display:none !important; }
div[role="radiogroup"] > label:hover { border-color: var(--brand); }
div[role="radiogroup"] > label:has(input:checked) { background: var(--brand); border-color: var(--brand); }
div[role="radiogroup"] > label:has(input:checked) p { color: var(--ink) !important; font-weight:700; }

/* ---------- buttons ---------- */
.stButton > button, [data-testid="stFormSubmitButton"] > button { border-radius: 14px !important; font-weight:700 !important; padding:.65rem 1.3rem !important;
  border:1px solid var(--border) !important; background: var(--card2) !important; color: var(--text) !important; transition: all .18s; }
.stButton > button:hover, [data-testid="stFormSubmitButton"] > button:hover { border-color: var(--brand) !important; transform: translateY(-1px); }
.stButton > button[kind="primary"], [data-testid="stFormSubmitButton"] > button[kind="primaryFormSubmit"] {
  background: linear-gradient(135deg, var(--brand), var(--brand2)) !important; color: var(--ink) !important; border: none !important;
  box-shadow: 0 8px 22px var(--glow); font-size:1.02rem !important; }
.stButton > button[kind="primary"] p, [data-testid="stFormSubmitButton"] > button[kind="primaryFormSubmit"] p { color: var(--ink) !important; }
.stButton > button[kind="primary"]:hover, [data-testid="stFormSubmitButton"] > button[kind="primaryFormSubmit"]:hover { filter: brightness(1.07); box-shadow: 0 10px 28px var(--glow); }

/* ---------- inputs ---------- */
[data-baseweb="input"], [data-baseweb="select"] > div, [data-baseweb="base-input"] { background: var(--input) !important; border-color: var(--border) !important; border-radius: 12px !important; }
[data-baseweb="input"] input, [data-baseweb="select"] div { color: var(--text) !important; }
[data-testid="stNumberInput"] button { background: transparent !important; color: var(--muted) !important; border:none !important; }
[class*="_missing"] [data-baseweb="input"] { border: 1px solid var(--warn) !important; box-shadow: 0 0 0 3px color-mix(in srgb, var(--warn) 22%, transparent); }
[data-testid="stExpander"] { background: var(--card); border:1px solid var(--border) !important; border-radius:16px !important; }
[data-testid="stExpander"] details, [data-testid="stExpander"] summary, [data-testid="stExpander"] details[open] > summary {
  background: transparent !important; color: var(--text) !important; }
[data-testid="stExpander"] summary:hover { background: var(--card2) !important; }
[data-testid="stExpander"] summary svg { color: var(--muted) !important; }
[data-testid="stExpander"] summary p { color: var(--text) !important; font-weight:600; }
[data-testid="stForm"] { border:1px solid var(--border) !important; border-radius:20px !important; background: var(--card); padding:1.2rem !important; }
[data-testid="stStatus"] { background: var(--card) !important; border:1px solid var(--border) !important; border-radius:16px !important; }
[data-testid="stToggle"] label p { color: var(--muted) !important; font-size:.85rem; }
[data-testid="stTooltipIcon"] svg { color: var(--muted); }
textarea { background: var(--input) !important; color: var(--text) !important; }

/* ---------- score card ---------- */
.nl-score { display:flex; gap:1.6rem; align-items:center; flex-wrap:wrap; }
.nl-ring { position:relative; width:190px; height:190px; flex:none; }
.nl-ring svg { transform: rotate(-90deg); }
.nl-ring .nl-ringtext { position:absolute; inset:0; display:grid; place-content:center; text-align:center; }
.nl-ringtext b { font-size:3.3rem; line-height:1; font-weight:800; color:var(--text); }
.nl-ringtext small { color:var(--muted); font-weight:600; }
.nl-score-body { flex:1 1 260px; min-width:240px; }
.nl-band { display:inline-block; padding:.28rem .95rem; border-radius:999px; font-weight:800; font-size:1.05rem; color:#14201a; }
.nl-score-body p { margin:.55rem 0; }
.nl-chips { display:flex; flex-wrap:wrap; gap:.4rem; margin:.4rem 0; }
.nl-chip { display:inline-flex; align-items:center; gap:.35rem; padding:.2rem .7rem; border-radius:999px; background:var(--card2); border:1px solid var(--border); font-size:.78rem; font-weight:600; color:var(--muted); }
.nl-chip.warn { color: var(--warn); border-color: color-mix(in srgb, var(--warn) 50%, transparent); }
.nl-scale { position:relative; display:flex; height:10px; border-radius:999px; overflow:hidden; margin: 1.2rem 0 .3rem; }
.nl-scale i { flex:1; }
.nl-marker { position:absolute; top:-5px; width:6px; height:20px; border-radius:4px; background: var(--text); box-shadow:0 0 0 3px var(--card); transform: translateX(-3px); }
.nl-scale-labels { display:flex; justify-content:space-between; font-size:.7rem; color:var(--muted); font-weight:600; }

/* ---------- nutrient tiles ---------- */
.nl-tiles { display:grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap:.7rem; margin-bottom:.9rem; }
.nl-tile { background:var(--card); border:1px solid var(--border); border-radius:16px; padding:.85rem .95rem; transition: border-color .2s, transform .2s; }
.nl-tile:hover { border-color: var(--brand); transform: translateY(-2px); }
.nl-tile-head { display:flex; justify-content:space-between; align-items:center; gap:.4rem; }
.nl-tile-name { font-weight:700; font-size:.9rem; color:var(--text); }
.nl-level { font-size:.7rem; font-weight:800; padding:.12rem .55rem; border-radius:999px; color:#14201a; }
.nl-tile-val { font-size:1.35rem; font-weight:800; margin:.3rem 0 .45rem; color:var(--text); }
.nl-tile-val small { font-size:.75rem; color:var(--muted); font-weight:600; }
.nl-bar { height:7px; border-radius:99px; background:var(--track); overflow:hidden; }
.nl-bar i { display:block; height:100%; border-radius:99px; }
.nl-tiles.core { grid-template-columns: repeat(3, 1fr); }
@media (min-width: 900px) { .nl-tiles.core { grid-template-columns: repeat(6, 1fr); gap:.55rem; } }
@media (max-width: 480px) { .nl-tiles.core { grid-template-columns: repeat(2, 1fr); } }
.nl-tiles.core .nl-tile { padding:.75rem .7rem; }
.nl-tiles.core .nl-tile-name { font-size:.82rem; }
.nl-tiles.core .nl-level { font-size:.64rem; padding:.1rem .45rem; }
.nl-tile.na { opacity:.75; }
.nl-na-text { font-size:.98rem !important; color:var(--muted) !important; font-weight:600 !important; }
.nl-tile.info .nl-tile-val { margin-bottom:.1rem; }
.nl-tile.info .nl-tile-name { font-size:.86rem; }
.nl-cap { color:var(--muted); font-size:.82rem; margin:.1rem 0 .5rem; }
.nl-keyhead { display:flex; justify-content:space-between; align-items:baseline; margin:.9rem 0 .5rem; flex-wrap:wrap; gap:.3rem; }
.nl-keyhead b { font-size:.72rem; letter-spacing:.12em; text-transform:uppercase; color:var(--muted); }
.nl-keyhead span { font-size:.78rem; color:var(--muted); }

/* ---------- per-serving table ---------- */
.nl-tablewrap { overflow-x:auto; }
.nl-ntable { width:100%; border-collapse:collapse; font-size:.9rem; min-width:420px; }
.nl-ntable th { text-align:left; font-size:.72rem; letter-spacing:.08em; text-transform:uppercase; color:var(--muted); padding:.4rem .5rem; border-bottom:1px solid var(--border); }
.nl-ntable td { padding:.5rem .5rem; border-bottom:1px dashed var(--border); color:var(--text); }
.nl-ntable tr:last-child td { border-bottom:none; }
.nl-ntable td.na { color:var(--muted); }
.nl-rda { display:flex; align-items:center; gap:.5rem; min-width:110px; }
.nl-rda .nl-bar { flex:1; height:6px; }
.nl-rda span { font-weight:700; min-width:2.6rem; }

/* ---------- allergens & ingredients ---------- */
.nl-allergen { border:1px solid color-mix(in srgb, var(--warn) 60%, transparent); background: color-mix(in srgb, var(--warn) 10%, var(--card));
  border-radius:20px; padding:1rem 1.2rem; margin:.2rem 0 .9rem; }
.nl-allergen h3 { margin:0 0 .5rem; font-size:1.02rem; font-weight:700; display:flex; gap:.5rem; align-items:center; color:var(--warn); }
.nl-allergen.clear { border-color: var(--border); background: var(--card); }
.nl-allergen.clear h3 { color: var(--text); }
.nl-allergen.clear h3 svg { color: var(--brand); }
.nl-chip.allergen { color:#14201a; background:var(--warn); border-color:transparent; font-size:.85rem; padding:.28rem .85rem; }
.nl-allergen p { margin:.5rem 0 0; color:var(--muted); font-size:.85rem; }
.nl-inote { padding:.6rem 0; border-bottom:1px dashed var(--border); }
.nl-inote:last-child { border-bottom:none; }
.nl-inote b { color:var(--text); display:block; }
.nl-inote small { color:var(--muted); display:block; margin-top:.1rem; font-size:.84rem; }
.nl-ing { display:flex; flex-wrap:wrap; gap:.35rem; margin:.4rem 0 .6rem; }

/* ---------- explanation ---------- */
.nl-explain-head { display:flex; justify-content:space-between; align-items:center; gap:.6rem; flex-wrap:wrap; }
.nl-source { font-size:.74rem; font-weight:700; padding:.18rem .7rem; border-radius:999px; background:var(--chip); color:var(--brand); border:1px solid color-mix(in srgb, var(--brand) 35%, transparent); }
.nl-source.tmpl { background: var(--card2); color: var(--muted); border-color: var(--border); }
.nl-explain-text { font-size:1rem; line-height:1.6; margin:.4rem 0 1rem; color:var(--text); }
.nl-two { display:grid; grid-template-columns: repeat(auto-fit, minmax(240px,1fr)); gap:.9rem; }
.nl-list { background:var(--card2); border-radius:14px; padding:.8rem 1rem; }
.nl-list h4 { margin:0 0 .5rem; font-size:.92rem; display:flex; gap:.4rem; align-items:center; }
.nl-list.down h4 { color: var(--bad); } .nl-list.up h4 { color: var(--good); }
.nl-list ul { list-style:none; margin:0; padding:0; }
.nl-list li { display:flex; justify-content:space-between; gap:.6rem; padding:.28rem 0; font-size:.9rem; border-bottom:1px dashed var(--border); }
.nl-list li:last-child { border-bottom:none; }
.nl-list li span { color:var(--muted); font-weight:600; white-space:nowrap; }
.nl-empty-li { color:var(--muted); font-size:.9rem; }

/* ---------- alternatives ---------- */
.nl-alts { display:grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap:.9rem; margin-bottom:.9rem; }
.nl-alt { background:var(--card); border:1px solid var(--border); border-radius:18px; overflow:hidden; display:flex; flex-direction:column; transition: transform .2s, border-color .2s; }
.nl-alt:hover { transform: translateY(-3px); border-color: var(--brand); }
.nl-alt-img { height:140px; background: var(--card2); display:grid; place-items:center; color: var(--muted); position:relative; }
.nl-alt-img img { position:absolute; inset:0; width:100%; height:100%; object-fit:contain; background:#fff; padding:6px; }
.nl-alt-body { padding:.8rem .95rem 1rem; display:flex; flex-direction:column; gap:.25rem; flex:1; }
.nl-alt-name { font-weight:700; color:var(--text); line-height:1.25; }
.nl-alt-brand { font-size:.8rem; color:var(--muted); }
.nl-alt-score { font-weight:700; margin-top:.2rem; display:flex; align-items:center; gap:.45rem; }
.nl-alt-score i { width:10px; height:10px; border-radius:50%; background: var(--c); display:inline-block; }
.nl-alt-reason { font-size:.85rem; color:var(--text); margin:.25rem 0 .5rem !important; }
.nl-alt-link { margin-top:auto; font-size:.82rem; font-weight:700; text-decoration:none; color:var(--brand); }
.nl-empty { text-align:center; padding:1.6rem 1rem; }
.nl-empty .nl-dropicon { width:56px; height:56px; margin:0 auto .6rem; border-radius:16px; display:grid; place-items:center; background:var(--chip); color:var(--brand); }
.nl-empty h3 { justify-content:center; }
.nl-footnote { color:var(--muted); font-size:.8rem; text-align:center; margin-top:1rem; }
.nl-sec { font-size:1.25rem; font-weight:800; margin: 1.4rem 0 .7rem; color:var(--text); display:flex; gap:.5rem; align-items:center; }
.nl-sec svg { color: var(--brand); }

@media (max-width: 640px) {
  .block-container { padding: 3.6rem .7rem 3rem !important; }
  .nl-ring { width:160px; height:160px; } .nl-ringtext b { font-size:2.7rem; }
}
"""


def inject_css(light: bool) -> None:
    """Inject the design system for the chosen theme."""
    t = THEMES["light" if light else "dark"]
    variables = ":root{" + "".join(f"--{k}:{v};" for k, v in t.items()) + f"--warn:{WARN};--good:{GOOD};--bad:{BAD};" + "}"
    st.markdown(f"<style>{variables}{_STATIC_CSS}</style>", unsafe_allow_html=True)


# --------------------------------------------------------------------------
# Page-level components
# --------------------------------------------------------------------------
def logo_svg(size: int = 24) -> str:
    """The BiteWise mark: scan-frame corners around a small search glyph. Clean and simple."""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
            f'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-label="BiteWise logo">'
            f'<path d="M3 8V6a3 3 0 0 1 3-3h2"/><path d="M16 3h2a3 3 0 0 1 3 3v2"/>'
            f'<path d="M21 16v2a3 3 0 0 1-3 3h-2"/><path d="M8 21H6a3 3 0 0 1-3-3v-2"/>'
            f'<circle cx="11" cy="11" r="3.6"/><path d="m13.8 13.8 3 3"/></svg>')


def brand_bar() -> str:
    return (f'<div class="nl-top"><span class="nl-logo">{logo_svg(25)}</span>'
            f'<div class="nl-brand">Bite<b>Wise</b><span class="nl-brand-sub">AI-assisted food label scanner</span></div></div>')


def hero(quote: str) -> None:
    render(f"""
    <div class="nl-hero">
      <h1>Scan Food Labels.<br><span>Make Healthier Choices.</span></h1>
      <p class="nl-sub">Upload a nutrition label. Get a score, a clear explanation and better options.</p>
      <div class="nl-features">
        <div class="nl-feature"><span class="nl-ficon">{icon("scan")}</span><div><b>OCR-powered</b><small>Reads nutrition labels</small></div></div>
        <div class="nl-feature"><span class="nl-ficon">{icon("chart")}</span><div><b>Health Score</b><small>Understand the result</small></div></div>
        <div class="nl-feature"><span class="nl-ficon">{icon("leaf")}</span><div><b>Better choices</b><small>Compare alternatives</small></div></div>
      </div>
      <div class="nl-quote">{icon("quote", 18)}<span>&ldquo;{esc(quote)}&rdquo;</span></div>
    </div>""")


def steps(current: int) -> None:
    """Step tracker: 1 Upload, 2 Review, 3 Results."""
    labels = ["Upload", "Review values", "Results"]
    parts = []
    for index, label in enumerate(labels, start=1):
        state = "done" if index < current else ("active" if index == current else "")
        dot = icon("check", 15) if index < current else str(index)
        parts.append(f'<div class="nl-step {state}"><span class="nl-dot">{dot}</span>{label}</div>')
        if index < len(labels):
            parts.append(f'<span class="nl-line {"done" if index < current else ""}"></span>')
    render(f'<div class="nl-steps">{"".join(parts)}</div>')


def upload_header() -> None:
    render(f"""
    <div class="nl-drop">
      <div class="nl-dropicon">{icon("image", 28)}</div>
      <h3>Upload your nutrition label</h3>
      <p>Drag and drop an image or browse files</p>
      <span class="nl-pill">JPG</span><span class="nl-pill">PNG</span>
      <p style="margin-top:.5rem">Or choose <b>Use Camera</b> to take a photo.</p>
    </div>""")


def thumbnail_b64(data: bytes, size: int = 116) -> str:
    """Small base64 JPEG thumbnail for the 'image ready' row ('' if unreadable)."""
    try:
        from PIL import Image
        image = Image.open(io.BytesIO(data)).convert("RGB")
        image.thumbnail((size, size))
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=80)
        return base64.b64encode(buffer.getvalue()).decode()
    except Exception:
        return ""


def ready_row(name: str, data: bytes) -> None:
    thumb = thumbnail_b64(data)
    img = f'<img src="data:image/jpeg;base64,{thumb}" alt="preview">' if thumb else ""
    render(f'<div class="nl-ready">{img}<div><b>{esc(name)}</b><span>{icon("check", 16)} Image ready to analyze</span></div></div>')


def note(text: str) -> None:
    render(f'<div class="nl-note">{esc(text)}</div>')


def attention(title: str, items: List[str]) -> None:
    lis = "".join(f"<li>{i}</li>" for i in items)
    render(f'<div class="nl-attn"><b>{icon("alert", 18)} {esc(title)}</b><ul>{lis}</ul></div>')


def section(title: str, icon_name: str) -> None:
    render(f'<div class="nl-sec">{icon(icon_name, 22)}{esc(title)}</div>')


# --------------------------------------------------------------------------
# Results components
# --------------------------------------------------------------------------
def score_card(result: Dict[str, object], is_drink: bool, category: Optional[str], estimate: bool = False) -> None:
    score = int(result["score"])  # type: ignore[arg-type]
    band = str(result["category"])
    color = band_color(band)
    radius, circ = 80, 2 * 3.14159265 * 80
    dash = circ * score / 100
    chips = [f'<span class="nl-chip">{"Drink" if is_drink else "Food"} scoring</span>']
    if category:
        chips.append(f'<span class="nl-chip">{esc(category)}</span>')
    if result.get("capped") or estimate:
        chips.append(f'<span class="nl-chip warn">{icon("alert", 13)} Estimate - limited data</span>')
    segs = "".join(f'<i style="background:{BAND_COLORS[b]}"></i>' for b in BAND_ORDER)
    render(f"""
    <div class="nl-card" data-score="{score}">
      <div class="nl-eyebrow">Your health score</div>
      <div class="nl-score">
        <div class="nl-ring">
          <svg width="190" height="190" viewBox="0 0 190 190">
            <circle cx="95" cy="95" r="{radius}" fill="none" stroke="var(--track)" stroke-width="16"/>
            <circle cx="95" cy="95" r="{radius}" fill="none" stroke="{color}" stroke-width="16" stroke-linecap="round"
                    stroke-dasharray="{dash:.1f} {circ:.1f}"/>
          </svg>
          <div class="nl-ringtext"><b>{score}</b><small>/ 100</small></div>
        </div>
        <div class="nl-score-body">
          <span class="nl-band" style="background:{color}">{esc(band)}</span>
          <p>{esc(BAND_SUMMARY.get(band, ""))}</p>
          <div class="nl-chips">{"".join(chips)}</div>
          <div class="nl-scale">{segs}<span class="nl-marker" style="left:{score}%"></span></div>
          <div class="nl-scale-labels"><span>Poor</span><span>Below avg</span><span>Moderate</span><span>Good</span><span>Excellent</span></div>
        </div>
      </div>
    </div>""")


_TILE_ORDER = [("Energy", "kcal"), ("Sugars", "g"), ("Saturated Fat", "g"), ("Sodium", "mg"), ("Fibre", "g"), ("Protein", "g")]


def _level(row: Dict[str, object]) -> tuple:
    """(label, colour, bar width %) for one breakdown row."""
    pts, mx = int(row["Points"]), max(1, int(row["Max"]))  # type: ignore[arg-type]
    frac = pts / mx
    if str(row["Type"]).startswith("Negative"):
        if pts == 0:
            return "Low", GOOD, 6
        if frac <= 0.3:
            return "Moderate", WARN, max(18, frac * 100)
        return "High", BAD, max(35, frac * 100)
    if pts == 0:
        return "Low", WARN, 6
    return "Good", GOOD, max(25, frac * 100)


def nutrient_tiles(result: Dict[str, object]) -> None:
    rows = {str(r["Nutrient"]): r for r in result["breakdown"]}  # type: ignore[union-attr]
    tiles = []
    for name, unit in _TILE_ORDER:
        row = rows.get(name)
        if row is None:
            tiles.append(f'<div class="nl-tile na"><div class="nl-tile-head"><span class="nl-tile-name">{name}</span>'
                         f'<span class="nl-level" style="background:var(--card2);color:var(--muted)">n/a</span></div>'
                         f'<div class="nl-tile-val nl-na-text">Not available</div><div class="nl-bar"><i style="width:0"></i></div></div>')
            continue
        label, color, width = _level(row)
        value = str(row["Value"]).split(" ")[0]
        tiles.append(f'<div class="nl-tile"><div class="nl-tile-head"><span class="nl-tile-name">{name}</span>'
                     f'<span class="nl-level" style="background:{color}">{label}</span></div>'
                     f'<div class="nl-tile-val">{esc(value)} <small>{unit}</small></div>'
                     f'<div class="nl-bar"><i style="width:{width:.0f}%;background:{color}"></i></div></div>')
    render(f'<div class="nl-tiles core">{"".join(tiles)}</div>')


def drivers(result: Dict[str, object]) -> tuple:
    """Deterministic 'what lowered / helped the score' lists from the score breakdown."""
    lowered, helped = [], []
    for row in result["breakdown"]:  # type: ignore[union-attr]
        name, pts, mx = str(row["Nutrient"]), int(row["Points"]), max(1, int(row["Max"]))
        value = str(row["Value"])
        if str(row["Type"]).startswith("Negative"):
            if pts / mx > 0.15 or (pts > 0 and name != "Energy"):
                lowered.append((pts / mx, f"{'High' if pts / mx > 0.3 else 'Some'} {name.lower()}", value))
            elif pts == 0 and name in ("Sugars", "Sodium", "Saturated Fat"):
                helped.append((0.0, f"Low {name.lower()}", value))
        elif pts > 0:
            helped.append((pts / mx, f"{name} adds points", value))
    lowered.sort(reverse=True)
    helped.sort(reverse=True)
    return [(t, v) for _, t, v in lowered], [(t, v) for _, t, v in helped]


def _list_html(items: List[tuple], empty: str) -> str:
    if not items:
        return f'<div class="nl-empty-li">{esc(empty)}</div>'
    return "<ul>" + "".join(f"<li>{esc(t)}<span>{esc(v)}</span></li>" for t, v in items) + "</ul>"


def explanation_card(text: str, source: str, lowered: List[tuple], helped: List[tuple]) -> None:
    is_ai = source.startswith("AI")
    pill = f'<span class="nl-source {"" if is_ai else "tmpl"}">{icon("sparkles", 13)} {esc(source if is_ai else "Built-in explanation")}</span>'
    paragraphs = "".join(f"<p class='nl-explain-text' style='margin:.3rem 0'>{esc(p)}</p>" for p in text.split("\n") if p.strip())
    render(f"""
    <div class="nl-card">
      <div class="nl-explain-head"><h3>{icon("sparkles", 20)} Why this score?</h3>{pill}</div>
      {paragraphs}
      <div class="nl-two" style="margin-top:.9rem">
        <div class="nl-list down"><h4>What lowered the score?</h4>{_list_html(lowered, "Nothing stood out as a big negative.")}</div>
        <div class="nl-list up"><h4>What helped the score?</h4>{_list_html(helped, "No standout positives on this label.")}</div>
      </div>
    </div>""")


def alternatives_grid(items: List[Dict[str, object]]) -> None:
    cards = []
    for item in items:
        color = band_color(str(item.get("Category")))
        image = str(item.get("Image") or "")
        img_tag = f'<img src="{esc(image)}" alt="" loading="lazy" referrerpolicy="no-referrer">' if image.startswith("https://") else ""
        link = str(item.get("Link") or "")
        link_html = (f'<a class="nl-alt-link" href="{esc(link)}" target="_blank" rel="noopener noreferrer">View on Open Food Facts &#8599;</a>'
                     if link.startswith("https://") else "")
        cards.append(f"""
        <div class="nl-alt">
          <div class="nl-alt-img">{icon("basket", 38)}{img_tag}</div>
          <div class="nl-alt-body">
            <div class="nl-alt-name">{esc(item.get("Product"))}</div>
            <div class="nl-alt-brand">{esc(item.get("Brand"))}</div>
            <div class="nl-alt-score" style="--c:{color}"><i></i>{esc(item.get("Score"))}/100 &middot; {esc(item.get("Category"))}</div>
            <p class="nl-alt-reason">{esc(item.get("Reason") or "")}</p>
            {link_html}
          </div>
        </div>""")
    render(f'<div class="nl-alts">{"".join(cards)}</div>')


def empty_state(title: str, body: str) -> None:
    render(f'<div class="nl-card nl-empty"><div class="nl-dropicon">{icon("basket", 28)}</div><h3>{esc(title)}</h3>'
           f'<p class="nl-muted">{body}</p></div>')


def _fmt(value: Optional[float], unit: str = "") -> str:
    return "Not available" if value is None else f"{value:g} {unit}".strip()


def key_heading(title: str, hint: str) -> None:
    render(f'<div class="nl-keyhead"><b>{esc(title)}</b><span>{esc(hint)}</span></div>')


def extra_tiles(items: List[tuple]) -> None:
    """Information-only nutrients: items = [(name, unit, value_or_None)]. Missing = 'Not available', never 0."""
    tiles = []
    for name, unit, value in items:
        if value is None:
            tiles.append(f'<div class="nl-tile info na"><div class="nl-tile-head"><span class="nl-tile-name">{esc(name)}</span></div>'
                         f'<div class="nl-tile-val nl-na-text">Not available</div></div>')
        else:
            tiles.append(f'<div class="nl-tile info"><div class="nl-tile-head"><span class="nl-tile-name">{esc(name)}</span></div>'
                         f'<div class="nl-tile-val">{value:g} <small>{esc(unit)}</small></div></div>')
    render(f'<div class="nl-tiles">{"".join(tiles)}</div>')


_LIMIT_KEYS = {"calories_kcal", "sugar_g", "added_sugar_g", "saturated_fat_g", "sodium_mg", "salt_g", "trans_fat_g", "cholesterol_mg", "total_fat_g"}


def nutrition_table(rows: List[Dict[str, object]], per100_label: str, serving_label: Optional[str], note: str) -> None:
    """rows: {key, name, unit, per100, serving, share}. Serving columns show 'Not available' when unknown."""
    body = []
    for row in rows:
        per100, serving, share = row["per100"], row["serving"], row["share"]
        unit = str(row["unit"])
        c100 = (f'<td>{_fmt(per100, unit)}</td>' if per100 is not None else '<td class="na">Not available</td>')  # type: ignore[arg-type]
        cs = (f'<td>{_fmt(serving, unit)}</td>' if serving is not None else '<td class="na">Not available</td>')  # type: ignore[arg-type]
        if share is None:
            cr = '<td class="na">Not available</td>'
        else:
            pct = int(share)  # type: ignore[arg-type]
            if str(row["key"]) in _LIMIT_KEYS:
                color = GOOD if pct < 20 else (WARN if pct < 35 else BAD)
            else:
                color = GOOD if pct >= 15 else "var(--muted)"
            cr = (f'<td><div class="nl-rda"><span>{pct}%</span><div class="nl-bar"><i style="width:{min(pct, 100)}%;background:{color}"></i></div></div></td>')
        body.append(f'<tr><td><b>{esc(row["name"])}</b></td>{c100}{cs}{cr}</tr>')
    head_serving = f"Per serving ({esc(serving_label)})" if serving_label else "Per serving"
    render(f"""
    <div class="nl-card">
      <h3>{icon("scale", 20)} Per serving vs per {esc(per100_label)}</h3>
      <div class="nl-tablewrap"><table class="nl-ntable">
        <thead><tr><th>Nutrient</th><th>Per {esc(per100_label)}</th><th>{head_serving}</th><th>% of daily intake</th></tr></thead>
        <tbody>{"".join(body)}</tbody></table></div>
      <div class="nl-cap" style="margin-top:.6rem">{esc(note)}</div>
    </div>""")


def allergen_card(found: List[str], has_text: bool) -> None:
    """Separate warning - allergens are NOT part of the Health Score."""
    if found:
        chips = "".join(f'<span class="nl-chip allergen">{esc(a)}</span>' for a in found)
        render(f"""<div class="nl-allergen"><h3>{icon("shield", 20)} Allergen alert</h3>
        <div class="nl-chips">{chips}</div>
        <p>Found in the ingredient text we read. This is a separate warning and does not change the Health Score. OCR can miss items, so always check the pack.</p></div>""")
    elif has_text:
        render(f"""<div class="nl-allergen clear"><h3>{icon("shield", 20)} Allergens</h3>
        <p style="margin:0">None of the common allergens were found in the ingredient text we read. OCR can miss words, so always check the pack if you have an allergy.</p></div>""")
    else:
        render(f"""<div class="nl-allergen clear"><h3>{icon("shield", 20)} Allergens</h3>
        <p style="margin:0">No ingredient list was read, so we can't check allergens. Add the ingredients in the review step, or check the pack. Not detecting an allergen does not mean the food is free of it.</p></div>""")


def ingredients_card(items: List[str], notes: List[Dict[str, object]], first_note: Optional[str]) -> None:
    chips = "".join(f'<span class="nl-chip">{esc(i)}</span>' for i in items[:24])
    more = f'<span class="nl-chip">+{len(items) - 24} more</span>' if len(items) > 24 else ""
    parts = [f'<div class="nl-ing">{chips}{more}</div>']
    if first_note:
        parts.append(f'<div class="nl-cap">{esc(first_note)}</div>')
    if notes:
        for n in notes:
            found = ", ".join(str(x) for x in n["found"])  # type: ignore[union-attr]
            parts.append(f'<div class="nl-inote"><b>{esc(n["title"])}: {esc(found)}</b><small>{esc(n["note"])}</small></div>')
    else:
        parts.append('<div class="nl-cap">Nothing in particular stood out in this ingredient list.</div>')
    render(f'<div class="nl-card">{"".join(parts)}'
           f'<div class="nl-cap" style="margin-top:.5rem">These notes describe ingredients. They are not a verdict and do not change the Health Score.</div></div>')


def footnote(text: str) -> None:
    render(f'<div class="nl-footnote">{esc(text)}</div>')
