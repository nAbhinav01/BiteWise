"""
Image Preprocessing Module
---------------------------
Prepares a food-label photo for OCR by cleaning it up: resizing,
converting to grayscale, mild contrast correction, noise removal, and
adaptive thresholding into a clean black-and-white image.

Tesseract reads clean, high-contrast, reasonably large black-and-white
text far more reliably than a raw colour photo - that is the whole
purpose of this module.
"""

from typing import Any

import cv2
import numpy as np
from PIL import Image


def load_image(uploaded_file: Any) -> np.ndarray:
    """
    Convert a file-like object (from Streamlit's file_uploader or
    camera_input) into an OpenCV-compatible BGR image array.

    Raises:
        ValueError: if the file cannot be read as a valid image.
    """
    try:
        pil_image = Image.open(uploaded_file).convert("RGB")
    except Exception as exc:
        raise ValueError(
            "Could not read this file as an image. Please upload a valid "
            "JPG or PNG file."
        ) from exc

    rgb_array = np.array(pil_image)
    # Streamlit/PIL work in RGB; OpenCV expects BGR internally.
    bgr_array = cv2.cvtColor(rgb_array, cv2.COLOR_RGB2BGR)
    return bgr_array


def preprocess_for_ocr(image: np.ndarray, min_width: int = 1000) -> np.ndarray:
    """
    Run a simple, explainable preprocessing pipeline on a label image to
    improve OCR accuracy.

    Steps (in order):
      1. Upscale the image if it is small (small text is hard for OCR).
      2. Convert to grayscale (OCR does not need colour information).
      3. Improve local contrast using CLAHE (helps with uneven lighting
         or a slight glare on the label).
      4. Remove small noise with a light median blur.
      5. Apply adaptive thresholding to turn the image into clean black
         text on a white background.

    Args:
        image: a BGR image array (as returned by load_image).
        min_width: if the image is narrower than this, it is upscaled.

    Returns:
        A single-channel (grayscale) black-and-white NumPy array, ready
        to be passed to pytesseract.
    """
    if image is None or image.size == 0:
        raise ValueError("Received an empty image - nothing to process.")

    # ---- 1. Resize / upscale small images -------------------------------
    height, width = image.shape[:2]
    if width < min_width:
        scale_factor = min_width / float(width)
        image = cv2.resize(
            image, None, fx=scale_factor, fy=scale_factor,
            interpolation=cv2.INTER_CUBIC,
        )

    # ---- 2. Grayscale conversion -----------------------------------------
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    # ---- 3. Contrast improvement (CLAHE) ----------------------------------
    # CLAHE = Contrast Limited Adaptive Histogram Equalization.
    # It boosts local contrast without over-brightening the whole image,
    # which helps when a label photo has uneven lighting or mild glare.
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    contrast_enhanced = clahe.apply(gray)

    # ---- 4. Noise removal ---------------------------------------------
    # A small median blur smooths out speckle noise without blurring
    # text edges too much.
    denoised = cv2.medianBlur(contrast_enhanced, 3)

    # ---- 5. Adaptive thresholding -----------------------------------------
    # Adaptive thresholding works better than a single global threshold
    # because lighting is rarely perfectly even across a real photo.
    processed = cv2.adaptiveThreshold(
        denoised,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        blockSize=31,  # size of the neighbourhood used to compute threshold
        C=15,          # constant subtracted from the mean - tweak for your images
    )

    return processed


def preprocess_gentle(image: np.ndarray, min_width: int = 1000) -> np.ndarray:
    """
    A softer alternative to preprocess_for_ocr.

    Hard binarisation (adaptive thresholding) can damage thin characters -
    e.g. a trailing "g" being read as "9" ("3.5 g" -> "3.59"). This variant
    only upscales, converts to grayscale, boosts local contrast (CLAHE) and
    lightly denoises, keeping the original letter shapes. The pipeline runs
    OCR on both versions and keeps the better result.
    """
    if image is None or image.size == 0:
        raise ValueError("The image is empty or could not be read.")
    height, width = image.shape[:2]
    if width < min_width:
        scale = min_width / width
        image = cv2.resize(image, (min_width, int(height * scale)), interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    gray = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    return cv2.fastNlMeansDenoising(gray, None, h=7, templateWindowSize=7, searchWindowSize=21)


def preprocess_plain(image: np.ndarray, min_width: int = 1000) -> np.ndarray:
    """Third OCR pass: just upscale + grayscale, no other changes."""
    if image is None or image.size == 0:
        raise ValueError("The image is empty or could not be read.")
    height, width = image.shape[:2]
    if width < min_width:
        scale = min_width / width
        image = cv2.resize(image, (min_width, int(height * scale)), interpolation=cv2.INTER_CUBIC)
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
