"""
AI Explanation Module (Groq)
--------------------------------
Uses an LLM served by Groq (https://groq.com, free tier, no card needed) ONLY to
explain, in plain language, a Health Score that was already calculated by
health_score.py.

The LLM never extracts nutrients and never decides or changes the score.
It is told the score, category and nutrient values and asked to explain.

Setup (the API key is NEVER written in code):
  - Local:           put GROQ_API_KEY in a .env file (see .env.example)
  - Streamlit Cloud: App settings -> Secrets (see .streamlit/secrets.toml.example)
Variables: GROQ_API_KEY (required for AI), GROQ_MODEL (optional).

Reliability
  * If a model is busy, rate-limited or slow, the next model in the list is tried.
  * If a model name has been retired, a working one is looked up from Groq's own
    model list, so the app keeps working without a code change.
  * If there is no key or Groq cannot answer, a built-in template explanation is
    returned, so the app always shows something useful (and says why).

Uses plain HTTPS calls via `requests` (no extra SDK to install).
"""

import os
import re
import time
from typing import Dict, List, Optional, Tuple

import requests

try:  # optional: load a local .env file if python-dotenv is installed
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # pragma: no cover
    pass

CHAT_URL = "https://api.groq.com/openai/v1/chat/completions"
MODELS_URL = "https://api.groq.com/openai/v1/models"
DEFAULT_MODEL = "llama-3.3-70b-versatile"
FALLBACK_MODELS = ["llama-3.1-8b-instant", "openai/gpt-oss-20b"]   # separate free-tier limits, very fast
# When asking Groq what is available, prefer these (best first); anything else it lists comes after.
PREFERRED_MODELS = ["openai/gpt-oss-120b", "openai/gpt-oss-20b", "llama-3.3-70b-versatile", "llama-3.1-8b-instant",
                    "qwen/qwen3-32b", "meta-llama/llama-4-scout-17b-16e-instruct", "meta-llama/llama-4-maverick-17b-128e-instruct"]
NOT_CHAT = ("whisper", "tts", "guard", "prompt", "embed", "transcri", "orpheus", "playai", "safeguard", "compound", "vision")
TIMEOUT_SECONDS = 20                                 # per attempt
TOTAL_BUDGET_SECONDS = 45                            # stop trying other models after this long
MAX_CHARS = 1200
KEY_PREFIX = "gsk_"

_WORKING_MODEL: Dict[str, str] = {}   # remembers a model that worked, for the life of the app process


class AIUnavailable(Exception):
    """Raised with a short, user-friendly reason when Groq did not answer."""


def _get_setting(name: str) -> Optional[str]:
    """Read a setting from environment variables, then Streamlit secrets."""
    value = os.getenv(name)
    if value:
        return value.strip().strip("\"'").strip()
    try:
        import streamlit as st
        secret = st.secrets.get(name)
        return str(secret).strip().strip("\"'").strip() if secret else None
    except Exception:  # no secrets file / not running in Streamlit
        return None


def has_key() -> bool:
    return bool(_get_setting("GROQ_API_KEY"))


def key_status() -> List[Tuple[str, str]]:
    """For the help box: whether the key can be seen and looks right. Never returns the key itself."""
    value = _get_setting("GROQ_API_KEY")
    if not value:
        return [("Groq", "GROQ_API_KEY not found")]
    if not value.startswith(KEY_PREFIX):
        return [("Groq", f"GROQ_API_KEY found, but it doesn't start with {KEY_PREFIX} - check for a typo or a wrong key")]
    return [("Groq", "GROQ_API_KEY found")]


# --------------------------------------------------------------------------
# Prompt
# --------------------------------------------------------------------------
def build_prompt(parsed: Dict[str, object], score_result: Dict[str, object], category: Optional[str]) -> str:
    """Create the instruction text sent to the LLM."""
    lines = []
    for row in score_result.get("breakdown", []):  # type: ignore[union-attr]
        lines.append(f"- {row['Nutrient']}: {row['Value']} ({row['Type']}, {row['Points']}/{row['Max']} points)")
    missing = score_result.get("missing") or []
    return (
        "You are a friendly nutrition-label assistant for a college project.\n"
        "A Health Score (0-100, higher is healthier) was ALREADY calculated by a fixed "
        "rule-based formula adapted from Nutri-Score. Do NOT change, recalculate or "
        "question the score. Only explain it.\n\n"
        f"Health Score: {score_result['score']}/100 ({score_result['category']})\n"
        f"Product category: {category or 'unknown'}\n"
        f"Values per 100 g/ml and their points:\n" + "\n".join(lines) + "\n"
        + (f"Not found on label: {', '.join(missing)}\n" if missing else "")
        + "\nWrite 3 to 4 short sentences in simple language: why the score is what it is "
        "(mention the 1-2 nutrients that matter most), and one practical tip. "
        "Use only the numbers above. Do not give medical advice or diagnose anything. "
        "Do not use markdown headings or bullet points."
    )


# --------------------------------------------------------------------------
# HTTP helpers
# --------------------------------------------------------------------------
def _reason_from_response(response: "requests.Response") -> str:
    """Turn an HTTP error from Groq into one short sentence (never includes the key)."""
    code = response.status_code
    detail = ""
    try:
        body = response.json()
        error = body.get("error", body) if isinstance(body, dict) else {}
        detail = str(error.get("message", "")) if isinstance(error, dict) else ""
    except ValueError:
        pass
    lowered = detail.lower()
    if code in (401, 403) or (code == 400 and ("api key" in lowered or "api_key" in lowered)):
        return f"the Groq API key was rejected ({code}) - create a new key at console.groq.com/keys"
    model_gone = any(w in lowered for w in ("decommission", "not found", "does not exist", "not supported", "no longer available"))
    if code == 404 or (code == 400 and "model" in lowered and model_gone):
        return f"the model name was not found ({code}): {detail[:140] or 'no details given'}"
    if code == 429:
        return "the free-tier usage limit was reached (429) - wait a minute and try again"
    if code >= 500:
        return f"Groq had a temporary problem ({code})"
    return f"Groq returned an error ({code})"


def _post(payload: Dict[str, object], key: str) -> Dict[str, object]:
    """POST to Groq and return JSON; raises AIUnavailable with a friendly reason on any failure."""
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    try:
        response = requests.post(CHAT_URL, headers=headers, json=payload, timeout=TIMEOUT_SECONDS)
    except requests.exceptions.Timeout:
        raise AIUnavailable("Groq took too long to answer")
    except requests.exceptions.RequestException:
        raise AIUnavailable("could not connect to Groq")
    if response.status_code >= 400:
        raise AIUnavailable(_reason_from_response(response))
    try:
        return response.json()
    except ValueError:
        raise AIUnavailable("Groq sent an unreadable reply")


def discover_models(key: str) -> List[str]:
    """Chat models this key can use right now (names get retired), best first."""
    try:
        response = requests.get(MODELS_URL, headers={"Authorization": f"Bearer {key}"}, timeout=10)
        if response.status_code >= 400:
            return []
        ids = [str(m.get("id", "")) for m in response.json().get("data", []) if m.get("active", True)]
    except (requests.exceptions.RequestException, ValueError, AttributeError):
        return []
    chat = [i for i in ids if i and not any(w in i.lower() for w in NOT_CHAT)]
    chat.sort(key=lambda i: (PREFERRED_MODELS.index(i) if i in PREFERRED_MODELS else len(PREFERRED_MODELS), i))
    return chat


def _ask(model: str, key: str, prompt: str) -> str:
    payload: Dict[str, object] = {"model": model, "messages": [{"role": "user", "content": prompt}],
                                  "temperature": 0.3, "max_tokens": 700}
    if "gpt-oss" in model:
        payload["reasoning_effort"] = "low"          # short answer; do not spend the budget "thinking"
    data = _post(payload, key)
    try:
        text = str(data["choices"][0]["message"]["content"] or "")  # type: ignore[index]
    except (KeyError, IndexError, TypeError):
        raise AIUnavailable("Groq sent an unexpected reply")
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)   # some models print their reasoning
    if not text.strip():
        raise AIUnavailable("Groq answered with nothing")
    return text


def call_groq(prompt: str) -> str:
    """Try the configured/default model, then fallbacks, then whatever Groq lists. Raises AIUnavailable."""
    key = _get_setting("GROQ_API_KEY") or ""
    order = [m for m in dict.fromkeys([_WORKING_MODEL.get("groq"), _get_setting("GROQ_MODEL"), DEFAULT_MODEL, *FALLBACK_MODELS]) if m]
    started = time.monotonic()
    tried: List[str] = []
    reason = "no answer from Groq"

    def attempt(model: str) -> Optional[str]:
        nonlocal reason
        tried.append(model)
        try:
            text = _ask(model, key, prompt)
            _WORKING_MODEL["groq"] = model
            return text
        except AIUnavailable as problem:
            reason = str(problem)
            return None

    def key_refused() -> bool:
        return "key was rejected" in reason

    for model in order:
        if len(tried) > 0 and time.monotonic() - started > TOTAL_BUDGET_SECONDS:
            raise AIUnavailable(reason)
        text = attempt(model)
        if text:
            return text
        if key_refused():
            raise AIUnavailable(reason)             # another model cannot fix a refused key

    listed: List[str] = []
    if "model name" in reason:                       # names get retired: ask Groq what is available now
        listed = discover_models(key)
        for model in listed:
            if model in tried:
                continue
            if time.monotonic() - started > TOTAL_BUDGET_SECONDS or len(tried) >= len(order) + 3:
                break
            text = attempt(model)
            if text:
                return text
            if key_refused():
                break
        if "model name" in reason:
            seen = ", ".join(listed[:4]) if listed else "none listed"
            reason = (f"no Groq model worked for this key. Groq said: {reason.split(': ', 1)[-1]}. "
                      f"Models Groq lists for this key: {seen}")
    raise AIUnavailable(reason)


# --------------------------------------------------------------------------
# Fallback + entry point
# --------------------------------------------------------------------------
def template_explanation(parsed: Dict[str, object], score_result: Dict[str, object]) -> str:
    """Simple non-AI fallback built only from the score breakdown."""
    score, category = score_result["score"], score_result["category"]
    rows = score_result.get("breakdown", [])
    bad = sorted((r for r in rows if r["Type"].startswith("Negative") and r["Points"] > 0),  # type: ignore[union-attr]
                 key=lambda r: r["Points"] / r["Max"], reverse=True)
    good = [r for r in rows if r["Type"].startswith("Positive") and r["Points"] > 0]  # type: ignore[union-attr]
    text = f"This product scored {score}/100, which is rated {category}."
    if bad:
        names = " and ".join(r["Nutrient"].lower() for r in bad[:2])
        text += f" The score is mainly pulled down by its {names}."
    if good:
        text += f" It gets some credit for {' and '.join(r['Nutrient'].lower() for r in good)}."
    if not bad and not good:
        text += " No nutrient stood out strongly in either direction."
    return text + " Compare it with the alternatives below to find a better choice."


def explain_score(parsed: Dict[str, object], score_result: Dict[str, object], category: Optional[str] = None) -> Tuple[str, str]:
    """
    Return (explanation_text, source). `source` says what produced it:
    "AI (Groq)" or "Template (...reason...)" so the UI can be transparent about it
    and tell the user how to fix the AI connection.
    """
    if score_result.get("score") is None:
        return "", "none"
    if not has_key():
        return (template_explanation(parsed, score_result), "Template (no Groq API key configured)")
    try:
        text = call_groq(build_prompt(parsed, score_result, category)).strip()
        return text[:MAX_CHARS], "AI (Groq)"
    except AIUnavailable as problem:
        return (template_explanation(parsed, score_result), f"Template (AI unavailable: {problem})")
