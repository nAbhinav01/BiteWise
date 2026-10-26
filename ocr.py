"""
OCR Module
----------
Wraps pytesseract/Tesseract to convert a preprocessed label image into
raw text.

Design notes:
  - The Tesseract executable path is configurable via the TESSERACT_CMD
    environment variable (or Streamlit secret of the same name), so
    this works across different machines without any hard-coded path.
    On Windows, Tesseract is rarely on PATH by default, so this is set
    to the install location (e.g.
    "C:\\Program Files\\Tesseract-OCR\\tesseract.exe").
  - On Linux/Mac, and on Streamlit Cloud (via packages.txt installing
    "tesseract-ocr"), Tesseract is normally already on PATH, so
    TESSERACT_CMD can be left blank.
  - All failure cases are turned into a clear RuntimeError with an
    actionable message, instead of letting a raw exception reach the
    user.
"""

import os
import shutil

import numpy as np
import pytesseract

try:
    # Loads variables from a local .env file, if one exists.
    # On Streamlit Cloud, secrets are provided differently (via
    # st.secrets) and this import/call simply has nothing to load,
    # which is harmless.
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def _get_tesseract_cmd() -> str:
    """
    Resolve the configured Tesseract executable path, checking (in
    order) the environment variable and, if running on Streamlit,
    st.secrets. Returns an empty string if nothing custom was set.
    """
    custom_path = os.getenv("TESSERACT_CMD", "").strip()
    if custom_path:
        return custom_path

    # Streamlit secrets are only available inside a Streamlit app
    # context; importing streamlit here is safe even outside one.
    try:
        import streamlit as st
        return str(st.secrets.get("TESSERACT_CMD", "")).strip()
    except Exception:
        # Not running inside Streamlit, or no secrets configured - fine.
        return ""


def configure_tesseract() -> None:
    """
    Point pytesseract at the correct Tesseract executable, if a custom
    path was configured. If not, pytesseract will fall back to
    whatever "tesseract" resolves to on the system PATH.
    """
    custom_path = _get_tesseract_cmd()
    if custom_path:
        pytesseract.pytesseract.tesseract_cmd = custom_path


def is_tesseract_available() -> bool:
    """
    Check whether Tesseract can actually be found, without running a
    full OCR pass. Used to show a helpful setup message up front
    instead of a confusing crash later.
    """
    configure_tesseract()

    custom_path = _get_tesseract_cmd()
    if custom_path:
        return os.path.isfile(custom_path)

    # No custom path configured - check if "tesseract" is on PATH.
    return shutil.which("tesseract") is not None


def extract_text(image: np.ndarray) -> str:
    """
    Run Tesseract OCR on a preprocessed image and return the raw
    extracted text.

    Args:
        image: a preprocessed image array (ideally the grayscale/
            binary output of preprocess_for_ocr()).

    Returns:
        The extracted text as a single string. May be an empty string
        if Tesseract ran successfully but found no readable text.

    Raises:
        RuntimeError: if Tesseract is not installed/configured
            correctly, or OCR fails for any other reason. The message
            is written to be shown directly to the end user.
    """
    configure_tesseract()

    if not is_tesseract_available():
        raise RuntimeError(
            "Tesseract OCR engine was not found on this system. "
            "Please install Tesseract separately (see README.md for "
            "instructions) and, if needed, set the TESSERACT_CMD "
            "environment variable to its full executable path."
        )

    # --psm 6: "Assume a single uniform block of text." Nutrition
    # labels are typically one dense block of lines, so this page
    # segmentation mode works better than Tesseract's default, which
    # expects a full page layout with paragraphs/columns.
    try:
        raw_text = pytesseract.image_to_string(image, config="--psm 6")
    except pytesseract.TesseractNotFoundError as exc:
        raise RuntimeError(
            "Tesseract is installed but could not be launched. Double-check "
            "the TESSERACT_CMD path is correct."
        ) from exc
    except pytesseract.TesseractError as exc:
        raise RuntimeError(f"Tesseract failed to process this image: {exc}") from exc
    except Exception as exc:  # pragma: no cover - safety net for unexpected errors
        raise RuntimeError(f"Unexpected error during OCR: {exc}") from exc

    return raw_text.strip()
