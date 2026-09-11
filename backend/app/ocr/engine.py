"""
OCR engine wrapper.

Defaults to Tesseract (offline, no API key needed — reliable for a live
hackathon demo). Swap OCR_ENGINE=google_vision in .env for higher accuracy
if you have credentials and a stable connection at pitch time.
"""
from dataclasses import dataclass

import cv2
import numpy as np
import pytesseract
from PIL import Image

from app.config import settings


@dataclass
class OCRWord:
    text: str
    left: int
    top: int
    width: int
    height: int
    confidence: float


def preprocess_image(image_path: str) -> np.ndarray:
    """Basic preprocessing: grayscale, denoise, adaptive threshold.
    Keeps the pipeline explainable — no black-box enhancement model."""
    img = cv2.imread(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    denoised = cv2.fastNlMeansDenoising(gray, h=10)
    thresh = cv2.adaptiveThreshold(
        denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 11
    )
    return thresh


def is_image_usable(image_path: str, blur_threshold: float = 100.0) -> tuple[bool, str]:
    """Cheap blur/quality gate — reject bad captures before wasting an OCR call."""
    img = cv2.imread(image_path)
    if img is None:
        return False, "Could not read image file."
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    if laplacian_var < blur_threshold:
        return False, f"Image too blurry (sharpness score {laplacian_var:.1f}, need >= {blur_threshold})."
    return True, "OK"


def run_tesseract(image_path: str) -> tuple[str, list[OCRWord]]:
    processed = preprocess_image(image_path)
    pil_img = Image.fromarray(processed)

    full_text = pytesseract.image_to_string(pil_img)
    data = pytesseract.image_to_data(pil_img, output_type=pytesseract.Output.DICT)

    words = []
    for i in range(len(data["text"])):
        text = data["text"][i].strip()
        if not text:
            continue
        conf_raw = data["conf"][i]
        try:
            conf = float(conf_raw)
        except (TypeError, ValueError):
            conf = -1.0
        if conf < 0:
            continue
        words.append(
            OCRWord(
                text=text,
                left=data["left"][i],
                top=data["top"][i],
                width=data["width"][i],
                height=data["height"][i],
                confidence=conf / 100.0,
            )
        )
    return full_text, words


def run_google_vision(image_path: str) -> tuple[str, list[OCRWord]]:
    """Optional higher-accuracy path. Requires google-cloud-vision installed
    and GOOGLE_APPLICATION_CREDENTIALS set. Not installed by default to keep
    the offline demo path dependency-light."""
    from google.cloud import vision  # local import — optional dependency

    client = vision.ImageAnnotatorClient()
    with open(image_path, "rb") as f:
        content = f.read()
    image = vision.Image(content=content)
    response = client.text_detection(image=image)

    if response.error.message:
        raise RuntimeError(response.error.message)

    annotations = response.text_annotations
    full_text = annotations[0].description if annotations else ""

    words = []
    for ann in annotations[1:]:
        vertices = ann.bounding_poly.vertices
        xs = [v.x for v in vertices]
        ys = [v.y for v in vertices]
        words.append(
            OCRWord(
                text=ann.description,
                left=min(xs),
                top=min(ys),
                width=max(xs) - min(xs),
                height=max(ys) - min(ys),
                confidence=0.9,  # Vision API doesn't return per-word confidence in this call
            )
        )
    return full_text, words


def extract_text(image_path: str) -> tuple[str, list[OCRWord]]:
    if settings.ocr_engine == "google_vision":
        return run_google_vision(image_path)
    return run_tesseract(image_path)
