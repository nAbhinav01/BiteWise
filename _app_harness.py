"""
Test harness for test_app.py - NOT part of the app.

Runs app.py inside Streamlit's AppTest with:
  * the file uploader replaced by a real image from HARNESS_IMAGE
  * Open Food Facts and the LLM API mocked (no internet / key needed)
OCR, parsing and scoring are REAL.
"""

import io
import os
import sys
from unittest.mock import MagicMock, patch

import requests
import streamlit as st

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)


class _Upload(io.BytesIO):
    name = "label.png"
    type = "image/png"


image_path = os.environ.get("HARNESS_IMAGE", "")
if image_path:
    _data = open(image_path, "rb").read()
    st.file_uploader = lambda *a, **k: _Upload(_data)


def _fake_get(*args, **kwargs):
    response = MagicMock()
    response.status_code = 200
    response.raise_for_status.return_value = None
    if os.environ.get("HARNESS_OFF") == "empty":
        response.json.return_value = {"products": []}
        return response
    product = lambda name, sugar: {
        "product_name": name, "brands": "Acme", "code": name, "nutriscore_grade": "a",
        "image_front_small_url": "https://images.openfoodfacts.org/images/products/demo.jpg",
        "nutriments": {"energy-kcal_100g": 100, "sugars_100g": sugar, "saturated-fat_100g": 0.5,
                       "sodium_100g": 0.05, "fiber_100g": 6, "proteins_100g": 8}}
    response.json.return_value = {"products": [product("Oats A", 2), product("Oats B", 3), product("Oats C", 4)]}
    return response


def _fake_post(*args, **kwargs):
    if os.environ.get("HARNESS_AI") == "fail":
        raise requests.exceptions.ConnectionError("blocked in test")
    response = MagicMock()
    response.status_code = 200
    response.raise_for_status.return_value = None
    response.json.return_value = {"choices": [{"message": {"content": "Mock AI explanation."}}]}
    return response


os.environ["GROQ_API_KEY"] = "gsk_test-key"
with patch.object(requests, "get", _fake_get), patch.object(requests, "post", _fake_post):
    exec(compile(open(os.path.join(HERE, "app.py")).read(), "app.py", "exec"))
