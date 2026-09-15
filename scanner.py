"""
PackSight Advanced Computer Vision & OCR Scanner Engine.
Enhanced integration adapted from the field-tested scanner pipeline.

Features:
- Auto-orientation detection (0°, 90°, 180°, 270°) with OCR readability scoring
- Multi-channel CV preprocessing (CLAHE, Red-channel adaptive threshold, Blue-channel Otsu, Inverted dot-matrix)
- Image quality assessment (Laplacian blur variance, brightness, specular glare)
- Brand & commodity recognition across 35+ FMCG categories
- High-precision field entity parsing (MRP, Net Qty, Dates, FSSAI, Batch, Consumer Care, Mfr, Origin)
- Collision-avoidant smart HUD badge annotation
"""

from __future__ import annotations

import io
import os
import re
import shutil
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Dict, List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image, ImageOps
import pytesseract
from pytesseract import Output

# Auto-configure Tesseract path
CANDIDATE_TESSERACT = [
    os.environ.get("TESSERACT_CMD", ""),
    shutil.which("tesseract") or "",
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Tesseract-OCR", "tesseract.exe"),
]
for p in CANDIDATE_TESSERACT:
    if p and os.path.isfile(p):
        pytesseract.pytesseract.tesseract_cmd = p
        break

OCR_SCALE = 2.0

MANDATORY_FIELDS: set[str] = {
    "MRP",
    "NET QUANTITY",
    "MANUFACTURER",
    "MARKETED BY",
    "CUSTOMER CARE",
    "MFG / PACKING DATE",
    "USE BY / BEST BEFORE",
    "LOT / BATCH",
    "COUNTRY OF ORIGIN",
}

OPTIONAL_FIELDS: set[str] = {
    "LICENSE",
    "INGREDIENTS",
    "MULTI UNIT PACKAGE",
}

ALL_SUPPORTED_FIELDS = sorted(MANDATORY_FIELDS | OPTIONAL_FIELDS)

FIELD_PATTERNS: dict[str, tuple[str, ...]] = {
    "MRP": (
        r"\bmrp\b",
        r"\bmaximum\s+retail\s+price\b",
        r"\b₹\s*\d+",
        r"\brs\.?\s*\d+",
    ),
    "NET QUANTITY": (
        r"\bnet\s*(?:quantity|qty|weight|wt|vol|volume)?\b",
        r"\bnetquantity\b",
        r"\bne[ti]\s*(?:quantity|qty|weight|wt)\b",
        r"\bnet\b[^\w\n]{0,10}\d+",
    ),
    "MANUFACTURER": (
        r"\bmanufactur(?:ed|ing)\s+(?:and\s+|&\s+)?(?:packed\s+)?by\b",
        r"\b(?:mfg|mfd|mig|wig|wfg|mid|iby)\s*[.:]?\s*by\b",
        r"\bpacked\s+by\b",
        r"\bproduced\s+by\b",
    ),
    "MARKETED BY": (
        r"\bmarketed\s+(?:and\s+|&\s+)?(?:packed\s+)?by\b",
        r"\b(?:marketed|mkt|mktg|mat|mlb|mkd)\s*[.:]?\s*by\b",
    ),
    "CUSTOMER CARE": (
        r"\b(?:customer|consumer)\s*(?:care|support|service|cell|helpline|centre)?\b",
        r"\b(?:helpline|toll\s*free)\b",
        r"wecare",
        r"\b1800\s*[-.\s]?\d{3,4}\b",
        r"\bp\.?o\.?\s*bag\b",
    ),
    "MFG / PACKING DATE": (
        r"\b(?:mfg|mfd)\b(?:\s*(?:date|on))?",
        r"\bmanufacturing\s+date\b",
        r"\b(?:packed|packing)\s+(?:on|date)\b",
        r"\bpkd\b",
    ),
    "USE BY / BEST BEFORE": (
        r"\buse\s*by\b",
        r"\bbest\s*before\b",
        r"\b(?:expiry|expires|expiration|exp\.?)\b",
    ),
    "LOT / BATCH": (
        r"\blot\s*(?:no|number)?\b",
        r"\bbatch\s*(?:no|number|code)?\b",
        r"\bb\.?\s*no\.?\b",
    ),
    "COUNTRY OF ORIGIN": (
        r"\bcountry\s+of\s+(?:origin|manufacture)\b",
        r"\bmade\s+in\b",
        r"\bproduct\s+of\b",
    ),
    "LICENSE": (
        r"\blic(?:ence|ense)?\s*[.:]?(?:\s*no|number)?\b",
        r"\bfssai\b",
        r"\bli[ce]\.?\s*(?:no|we|he)\.?\b",
        r"\b[12]\d{13}\b",
    ),
    "INGREDIENTS": (
        r"\bingredients?\b",
        r"\ballergen\s*note\b",
    ),
    "MULTI UNIT PACKAGE": (
        r"\bmulti\s*[- ]?\s*(?:unit|pack|package)\b",
        r"\b\d+\s*units?\b",
        r"\bpack\s+contains\s+\d+\s*serves?\b",
    ),
}

COMPILED_FIELD_PATTERNS = {
    field: tuple(re.compile(pattern, re.IGNORECASE) for pattern in patterns)
    for field, patterns in FIELD_PATTERNS.items()
}

DATE_PATTERN = re.compile(
    r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*"
    r"[\s./_-]*([0-9ilzs]{2,4})\b",
    re.IGNORECASE,
)
NUMERIC_DATE_PATTERN = re.compile(r"\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b")
EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b", re.I)
PHONE_PATTERN = re.compile(
    r"(?:\+?91[\s-]?)?(?:1800[\s-]?\d{3}[\s-]?\d{3,4}|\b\d{3,5}[\s-]\d{6,8}\b|\b1800[\s\d-]{6,10}\b)"
)
ALPHANUMERIC_CODE_PATTERN = re.compile(
    r"\b(?=[a-z0-9]{6,20}\b)(?=.*\d)[a-z0-9]+\b", re.I
)

# Color specifications in BGR format for OpenCV
FIELD_COLORS_BGR: dict[str, tuple[int, int, int]] = {
    "MRP": (255, 196, 0),
    "NET QUANTITY": (110, 220, 0),
    "MANUFACTURER": (0, 150, 255),
    "MARKETED BY": (170, 90, 255),
    "CUSTOMER CARE": (80, 80, 255),
    "MFG / PACKING DATE": (255, 90, 170),
    "USE BY / BEST BEFORE": (255, 0, 190),
    "LOT / BATCH": (235, 235, 0),
    "COUNTRY OF ORIGIN": (0, 190, 130),
    "LICENSE": (255, 180, 60),
    "INGREDIENTS": (200, 255, 60),
    "MULTI UNIT PACKAGE": (0, 210, 255),
}

STATUS_COLORS_BGR = {
    "pass": (74, 163, 22),     # Green #16a34a
    "fail": (38, 38, 220),     # Red #dc2626
    "review": (6, 119, 217),   # Amber #d97706
}

COMMON_BRANDS = [
    ("KitKat", [r"\bkit\s*kat\b", r"\bkitkat\b"]),
    ("Nestlé", [r"\bnestle\b", r"\bnestlé\b"]),
    ("Parle-G", [r"\bparle\s*-?\s*g\b"]),
    ("Parle", [r"\bparle\b"]),
    ("Britannia", [r"\bbritannia\b"]),
    ("Amul", [r"\bamul\b"]),
    ("Cadbury", [r"\bcadbury\b", r"\bdairy\s*milk\b"]),
    ("Oreo", [r"\boreo\b"]),
    ("Lay's", [r"\blays\b", r"\blay's\b"]),
    ("Kurkure", [r"\bkurkure\b"]),
    ("Haldiram", [r"\bhaldiram\b", r"\bhaldiram's\b"]),
    ("Sunfeast", [r"\bsunfeast\b"]),
    ("Dark Fantasy", [r"\bdark\s*fantasy\b"]),
    ("Maggi", [r"\bmaggi\b"]),
    ("Tata Tea", [r"\btata\s*tea\b"]),
    ("Tata Salt", [r"\btata\s*salt\b"]),
    ("Dabur", [r"\bdabur\b"]),
    ("Colgate", [r"\bcolgate\b"]),
    ("Dettol", [r"\bdettol\b"]),
    ("Good Day", [r"\bgood\s*day\b"]),
    ("Marie Gold", [r"\bmarie\s*gold\b"]),
    ("Bourbon", [r"\bbourbon\b"]),
    ("Aashirvaad", [r"\baashirvaad\b"]),
    ("Saffola", [r"\bsaffola\b"]),
    ("Fortune", [r"\bfortune\b"]),
    ("Patanjali", [r"\bpatanjali\b"]),
    ("Nivea", [r"\bnivea\b"]),
    ("Himalaya", [r"\bhimalaya\b"]),
    ("Frooti", [r"\bfrooti\b"]),
    ("Maaza", [r"\bmaaza\b"]),
    ("Thums Up", [r"\bthums\s*up\b"]),
    ("Sprite", [r"\bsprite\b"]),
    ("Coca-Cola", [r"\bcoca\s*-?\s*cola\b", r"\bcoke\b"]),
    ("Pepsi", [r"\bpepsi\b"]),
    ("DMart Healthy Choice", [r"\bdmart\b", r"\bhealthy\s*choice\b"]),
]


# ---------------------------------------------------------------------------
# Image Quality Assessment
# ---------------------------------------------------------------------------

def assess_image_quality(image: np.ndarray) -> dict[str, Any]:
    """Assess image quality for package label scanning: blur variance, brightness, glare."""
    if image is None or image.size == 0:
        return {
            "acceptable": False,
            "blur_score": 0.0,
            "is_blurry": True,
            "brightness": 0.0,
            "glare_percent": 0.0,
            "status": "Poor",
            "recommendations": ["No valid image frame detected."],
        }

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
    laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    brightness = float(np.mean(gray))
    glare_pixels = int(np.sum(gray > 248))
    total_pixels = int(gray.size)
    glare_percent = float((glare_pixels / total_pixels) * 100) if total_pixels > 0 else 0.0

    is_blurry = laplacian_var < 70.0
    is_too_dark = brightness < 45.0
    is_too_bright = brightness > 220.0
    is_high_glare = glare_percent > 8.0

    recommendations: list[str] = []
    if is_blurry:
        recommendations.append("Hold camera steady or adjust focus.")
    if is_too_dark:
        recommendations.append("Increase lighting or move closer to light source.")
    if is_too_bright:
        recommendations.append("Decrease lighting to avoid overexposure.")
    if is_high_glare:
        recommendations.append("Tilt package slightly to reduce surface reflection glare.")

    acceptable = not (is_blurry or is_too_dark or is_high_glare)
    if not recommendations:
        recommendations.append("Frame quality optimal for inspection.")

    quality_status = "Optimal" if acceptable else ("Marginal" if laplacian_var >= 45 else "Poor")

    return {
        "acceptable": acceptable,
        "status": quality_status,
        "blur_score": round(laplacian_var, 1),
        "is_blurry": is_blurry,
        "brightness": round(brightness, 1),
        "glare_percent": round(glare_percent, 2),
        "recommendations": recommendations,
    }


# ---------------------------------------------------------------------------
# Auto-Orientation Detection
# ---------------------------------------------------------------------------

def clean_text_simple(text: str) -> str:
    text = text.lower().replace("₹", " rs ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


STATUTORY_ORIENTATION_KEYWORDS = [
    "NET", "QUANTITY", "WEIGHT", "MRP", "MAX", "RETAIL", "PRICE", "RS", "TAXES",
    "MFG", "PACKED", "PACKAGING", "DATE", "PKD", "EXP", "EXPIRY", "USE BY", "BATCH",
    "LIC", "NO", "CONSUMER", "CARE", "FEEDBACK", "SUGGESTIONS", "EXECUTIVE",
    "INGREDIENTS", "NUTRITIONAL", "INFORMATION", "APPROX", "VALUES", "ENERGY", "KCAL",
    "PROTEIN", "CARBOHYDRATE", "FAT", "SUGAR", "SODIUM", "MG", "SERVING", "PER",
    "MANUFACTURED", "MARKETED", "BY", "LTD", "PVT", "FOODS", "INDIA", "MUMBAI",
    "BEST", "BEFORE", "STORE", "COOL", "DRY", "BUY", "BACK", "POUCH", "CONTAINER",
    "COMMODITY", "UNIT", "SALE", "SEEDS", "BISCUITS", "TEA", "SOAP", "OIL", "ATTA"
]


def orientation_score(image: np.ndarray) -> float:
    """Score readable OCR to find the correct upright angle across 0°, 90°, 180°, 270°."""
    h, w = image.shape[:2]
    scale = 800.0 / max(h, w) if max(h, w) > 800 else 1.0
    preview = cv2.resize(image, (int(w * scale), int(h * scale)))
    gray = cv2.cvtColor(preview, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.2, tileGridSize=(8, 8)).apply(gray)

    try:
        data = pytesseract.image_to_data(
            clahe,
            output_type=Output.DICT,
            config="--oem 3 --psm 11",
        )
    except Exception:
        return 0.0

    words: list[tuple[str, float]] = []
    for text, raw_conf in zip(data.get("text", []), data.get("conf", [])):
        text = (text or "").strip()
        try:
            conf = float(raw_conf)
        except Exception:
            conf = -1.0
        alnum = sum(c.isalnum() for c in text)
        if not text or alnum == 0 or conf < 10:
            continue
        words.append((text, conf))

    readable = sum((conf + 5) * min(len(t), 18) for t, conf in words)
    joined = clean_text_simple(" ".join(t for t, _ in words)).upper()

    keyword_hits = 0
    for kw in STATUTORY_ORIENTATION_KEYWORDS:
        if re.search(r'\b' + re.escape(kw) + r'\b', joined):
            keyword_hits += 1

    label_hits = sum(
        1 for patterns in COMPILED_FIELD_PATTERNS.values()
        if any(p.search(joined) for p in patterns)
    )
    date_bonus = 80 if DATE_PATTERN.search(joined) or NUMERIC_DATE_PATTERN.search(joined) else 0
    return readable + keyword_hits * 150 + label_hits * 250 + date_bonus


def find_best_orientation(image: np.ndarray) -> tuple[str, np.ndarray, int]:
    """Rotate image across 0°, 90°, 180°, 270° and pick the most readable angle."""
    views = {
        "0": (image, 0),
        "90_CW": (cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE), 90),
        "180": (cv2.rotate(image, cv2.ROTATE_180), 180),
        "270_CW": (cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE), 270),
    }

    best_score = float("-inf")
    selected_name = "0"
    selected_img = image
    selected_deg = 0

    for name, (cand, deg) in views.items():
        score = orientation_score(cand)
        if score > best_score:
            best_score = score
            selected_name = name
            selected_img = cand
            selected_deg = deg

    return selected_name, selected_img, selected_deg


# ---------------------------------------------------------------------------
# Multi-channel Preprocessing Variants
# ---------------------------------------------------------------------------

def preprocess_variants(image: np.ndarray, scale: float = OCR_SCALE) -> dict[str, np.ndarray]:
    """Create complementary OCR views for bright, dark, colored, and dot-matrix packaging."""
    scaled = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(scaled, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.4, tileGridSize=(8, 8)).apply(gray)

    # Red channel variant for dark text on red/orange packaging
    r_chan = scaled[:, :, 2]
    clahe_red = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(r_chan)
    adapt_red = cv2.adaptiveThreshold(
        r_chan, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 25, 10
    )

    # Blue channel Otsu threshold for white text on red/warm backgrounds
    b_chan = scaled[:, :, 0]
    _, otsu_blue = cv2.threshold(b_chan, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Inverted grayscale for dot-matrix codes and reverse text
    inv_clahe = cv2.bitwise_not(clahe)

    return {
        "clahe": clahe,
        "clahe_red": clahe_red,
        "adapt_red": adapt_red,
        "otsu_blue": otsu_blue,
        "inv_clahe": inv_clahe,
    }


# ---------------------------------------------------------------------------
# Value Extraction & Normalization
# ---------------------------------------------------------------------------

def canonical_month_date(raw_value: str | tuple[str, str]) -> str:
    if isinstance(raw_value, tuple):
        month, raw_year = raw_value
        table = str.maketrans({"i": "1", "l": "1", "z": "2", "s": "5"})
        year = raw_year.lower().translate(table)
        return f"{month.upper()}/{year}"

    clean = clean_text_simple(str(raw_value))
    match = re.search(r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s*([0-9ilzs]{1,4})", clean, re.I)
    if not match:
        return str(raw_value).strip()
    table = str.maketrans({"i": "1", "l": "1", "z": "2", "s": "5"})
    year = match.group(2).lower().translate(table)
    return f"{match.group(1).upper()}/{year}"


def extract_value(field: str, text: str) -> Optional[str]:
    raw = " ".join(text.split())
    soft = raw.replace("₹", " Rs ")

    if field == "MRP":
        match = re.search(r"(?:mrp|maximum\s+retail\s+price)[^\d]{0,20}(?:rs\.?|₹)?\s*([0-9]{1,5}(?:[.,][0-9]{1,2})?)", soft, re.I)
        if not match:
            match = re.search(r"(?:rs\.?|₹)\s*([0-9]{1,5}(?:[.,][0-9]{1,2})?)", soft, re.I)
        return f"₹{match.group(1).replace(',', '.')}" if match else None

    if field == "NET QUANTITY":
        match = re.search(r"(?:net\s*(?:quantity|qty|weight|wt|vol|volume)?)[^\d$sS]{0,15}([$sS0-9]{2,4}(?:[.,][0-9]+)?)\s*(?:g|gm|kg|ml|l|ltr|q)?", soft, re.I)
        if match:
            num = match.group(1).replace("S", "5").replace("s", "5").replace("$", "5")
            return f"{num} g"
        match = re.search(r"\b([0-9]{1,4}(?:[.,][0-9]+)?\s*(?:kg|g|gm|gms|ml|l|ltr))\b", soft, re.I)
        return match.group(1).strip() if match else None

    if field in {"MFG / PACKING DATE", "USE BY / BEST BEFORE"}:
        dates = DATE_PATTERN.findall(raw)
        if dates:
            return canonical_month_date(dates[0])
        numeric = NUMERIC_DATE_PATTERN.search(raw)
        return numeric.group(0) if numeric else None

    if field == "LOT / BATCH":
        match = re.search(r"(?:lot|batch|b\.?no)\s*(?:no|number)?\s*[:#-]?\s*([a-z0-9-]{4,})", soft, re.I)
        if match:
            return match.group(1).upper()
        return None

    if field == "LICENSE":
        fssai = re.search(r"\b([12]\d{13})\b", raw)
        if fssai:
            return fssai.group(1)
        match = re.search(r"(?:lic(?:ence|ense)?|fssai)[^\d]{0,10}(\d{7,14})", soft, re.I)
        return match.group(1) if match else None

    if field == "CUSTOMER CARE":
        parts = []
        phone = PHONE_PATTERN.search(raw)
        if phone:
            parts.append(phone.group(0).strip())
        email = EMAIL_PATTERN.search(raw)
        if email:
            parts.append(email.group(0).lower())
        return " | ".join(parts) if parts else None

    if field == "MANUFACTURER":
        m = re.search(r"(?:(?:manufactur(?:ed|ing)\s+(?:and\s+|&\s+)?(?:packed\s+)?by|(?:mfg|mfd)\s*[.:]?\s*by)[.:\s]*(.+))", raw, re.I)
        if m:
            val = re.split(r"(?:Lic\.|Licence|License|Mkt\s*by|Allergen)", m.group(1), flags=re.I)[0].strip(" ,;:-|")
            if len(val) > 4:
                return val
        return None

    if field == "MARKETED BY":
        m = re.search(r"(?:(?:marketed\s+(?:and\s+|&\s+)?(?:packed\s+)?by|mkt\s*[.:]?\s*by)[.:\s]*(.+))", raw, re.I)
        if m:
            val = re.split(r"(?:Mfg\s*by|Lic\.|Licence|License)", m.group(1), flags=re.I)[0].strip(" ,;:-|")
            if len(val) > 4:
                return val
        return None

    if field == "COUNTRY OF ORIGIN":
        match = re.search(r"(?:country\s+of\s+origin|made\s+in|product\s+of)[.:\s]+([a-z\s]{3,20})", soft, re.I)
        if match:
            return match.group(1).strip().title()
        if any(k in soft.lower() for k in ["india", "mumbai", "delhi", "pune", "bengaluru", "chennai"]):
            return "India"
        return None

    return None


def detect_brand_name(raw_text: str) -> str:
    """Identify prominent FMCG brand from packaging text."""
    for brand, patterns in COMMON_BRANDS:
        for pat in patterns:
            if re.search(pat, raw_text, re.IGNORECASE):
                return brand

    m = re.search(r"(?:by|mfg by)\s+([A-Za-z0-9\s&]{3,25}?)(?:\s+(?:ltd|limited|pvt|private))", raw_text, re.I)
    if m:
        cand = m.group(1).strip().title()
        if len(cand) >= 3 and cand.lower() not in ("the", "and", "india"):
            return cand

    return "Packaged Commodity"


# ---------------------------------------------------------------------------
# Smart HUD Badge Annotation
# ---------------------------------------------------------------------------

def draw_smart_hud_badge(
    image: np.ndarray,
    text: str,
    box: dict[str, int],
    color: tuple[int, int, int],
    occupied_rects: list[tuple[int, int, int, int]],
) -> None:
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 0.40
    thickness = 1
    (tw, th), baseline = cv2.getTextSize(text, font, scale, thickness)
    pad = 4
    badge_w = tw + pad * 2
    badge_h = th + pad * 2
    img_h, img_w = image.shape[:2]

    def overlaps(r1, r2):
        return not (r1[2] < r2[0] or r1[0] > r2[2] or r1[3] < r2[1] or r1[1] > r2[3])

    bx_clamped = max(2, min(box["x1"], img_w - badge_w - 2))
    pos_above = (bx_clamped, max(2, box["y1"] - badge_h - 2), bx_clamped + badge_w, max(2, box["y1"] - 2))
    pos_below = (bx_clamped, min(img_h - 2, box["y2"] + 2), bx_clamped + badge_w, min(img_h - 2, box["y2"] + badge_h + 2))
    pos_right = (min(img_w - badge_w - 2, box["x2"] + 4), max(2, box["y1"]), min(img_w - 2, box["x2"] + 4 + badge_w), max(2, box["y1"] + badge_h))

    chosen = pos_above
    for cand in [pos_above, pos_below, pos_right]:
        if not any(overlaps(cand, occ) for occ in occupied_rects):
            chosen = cand
            break

    occupied_rects.append(chosen)
    x1, y1, x2, y2 = chosen
    # Dark HUD container with 1px border in field status color
    cv2.rectangle(image, (x1, y1), (x2, y2), (20, 20, 24), cv2.FILLED)
    cv2.rectangle(image, (x1, y1), (x2, y2), color, 1)
    cv2.putText(image, text, (x1 + pad, y2 - pad - baseline + 1), font, scale, (255, 255, 255), thickness, cv2.LINE_AA)


def annotate_smart_hud(
    image: np.ndarray,
    detections: list[dict[str, Any]],
) -> np.ndarray:
    """Draw thin non-occluding 2px bounding box and smart HUD badges."""
    annotated = image.copy()
    h, w = annotated.shape[:2]
    occupied_rects: list[tuple[int, int, int, int]] = []

    # Priority: pass first, then review, then fail on top
    priority_map = {"pass": 0, "review": 1, "fail": 2}
    sorted_dets = sorted(detections, key=lambda d: priority_map.get(d.get("verdict", "review").lower(), 1))

    # 1. Draw 2px thin outline boxes
    for det in sorted_dets:
        box = det.get("box")
        if not box:
            continue
        verdict = det.get("verdict", "review").lower()
        color = STATUS_COLORS_BGR.get(verdict, (6, 119, 217))
        cv2.rectangle(annotated, (box["x1"], box["y1"]), (box["x2"], box["y2"]), color, 2)

    # 2. Draw smart HUD tags
    for det in sorted_dets:
        box = det.get("box")
        if not box:
            continue
        verdict = det.get("verdict", "review").lower()
        color = STATUS_COLORS_BGR.get(verdict, (6, 119, 217))
        tag = det.get("tag", det.get("field", "Rule"))
        draw_smart_hud_badge(annotated, tag, box, color, occupied_rects)

    return annotated


# ---------------------------------------------------------------------------
# High-Level Scanner Pipeline for API
# ---------------------------------------------------------------------------

def run_advanced_scan(image_bytes: bytes) -> dict[str, Any]:
    """Complete CV pipeline: EXIF transpose, auto-orientation, adaptive auto-zoom, multi-pass OCR, entity parsing."""
    try:
        pil_img = Image.open(io.BytesIO(image_bytes))
        pil_img = ImageOps.exif_transpose(pil_img)
        image = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    except Exception:
        np_arr = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    if image is None:
        raise ValueError("Could not decode image bytes.")

    # 1. Assess quality
    quality = assess_image_quality(image)

    # 2. Find best orientation (auto-rotate if needed)
    ori_name, oriented, degrees = find_best_orientation(image)
    h, w = oriented.shape[:2]

    # 3. Adaptive Auto-Zoom for small letters & fine statutory typography
    min_dim = min(h, w)
    zoom_factor = max(1.5, min(3.2, 1800.0 / min_dim))
    zoomed = cv2.resize(oriented, None, fx=zoom_factor, fy=zoom_factor, interpolation=cv2.INTER_CUBIC)

    # Unsharp mask to sharpen small font edges
    blurred = cv2.GaussianBlur(zoomed, (0, 0), 1.2)
    sharpened = cv2.addWeighted(zoomed, 1.4, blurred, -0.4, 0)
    gray_zoom = cv2.cvtColor(sharpened, cv2.COLOR_BGR2GRAY)
    clahe_zoom = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8)).apply(gray_zoom)

    # Multi-pass OCR passes on zoomed image
    passes = []
    # Pass A: Sparse layout / multi-panel
    try:
        passes.append((pytesseract.image_to_data(clahe_zoom, output_type=Output.DICT, config="--oem 3 --psm 11"), 0))
    except Exception:
        pass

    # Pass B: Uniform / tabular declaration blocks
    try:
        passes.append((pytesseract.image_to_data(clahe_zoom, output_type=Output.DICT, config="--oem 3 --psm 6"), 0))
    except Exception:
        pass

    # Pass C: Regional statutory crop (bottom 55% of packaging)
    try:
        bot_y_start = int(sharpened.shape[0] * 0.45)
        bot_crop = clahe_zoom[bot_y_start:, :]
        passes.append((pytesseract.image_to_data(bot_crop, output_type=Output.DICT, config="--oem 3 --psm 6"), bot_y_start))
    except Exception:
        pass

    # Collect, rescale to original image coordinates, and deduplicate words
    unified_words: list[dict[str, Any]] = []
    seen_boxes: set[tuple[int, int, str]] = set()

    for d_pass, y_offset in passes:
        n = len(d_pass.get("text", []))
        for i in range(n):
            raw_w = (d_pass["text"][i] or "").strip()
            try:
                conf = float(d_pass["conf"][i])
            except (ValueError, TypeError, IndexError):
                conf = 0.0

            if not raw_w or conf < 15:
                continue

            # Rescale box back to unscaled oriented coordinates
            l = max(0, min(w - 1, int(round(d_pass["left"][i] / zoom_factor))))
            t = max(0, min(h - 1, int(round((d_pass["top"][i] + y_offset) / zoom_factor))))
            bw = max(1, min(w - l, int(round(d_pass["width"][i] / zoom_factor))))
            bh = max(1, min(h - t, int(round(d_pass["height"][i] / zoom_factor))))

            # Spatial dedup key (grid quantized to 8px)
            dedup_key = (l // 8, t // 8, raw_w.upper())
            if dedup_key in seen_boxes:
                continue
            seen_boxes.add(dedup_key)

            unified_words.append({
                "text": raw_w,
                "conf": conf,
                "left": l,
                "top": t,
                "width": bw,
                "height": bh,
                "box": (l, t, l + bw, t + bh),
            })

    # Sort words top-to-bottom, left-to-right to reconstruct natural reading order
    unified_words.sort(key=lambda item: (item["top"] // 14, item["left"]))

    # Group into lines
    lines: list[str] = []
    current_line: list[str] = []
    current_line_y = None

    for item in unified_words:
        w_text = item["text"]
        w_y = item["top"]
        if current_line_y is None or abs(w_y - current_line_y) > 16:
            if current_line:
                lines.append(" ".join(current_line))
                current_line = []
            current_line_y = w_y
        current_line.append(w_text)
    if current_line:
        lines.append(" ".join(current_line))

    combined_text = "\n".join(lines).strip()
    if not combined_text:
        try:
            combined_text = pytesseract.image_to_string(oriented).strip()
        except Exception:
            combined_text = ""

    # Build primary_data structure for annotate_image
    primary_data = {
        "text": [item["text"] for item in unified_words],
        "conf": [item["conf"] for item in unified_words],
        "left": [item["left"] for item in unified_words],
        "top": [item["top"] for item in unified_words],
        "width": [item["width"] for item in unified_words],
        "height": [item["height"] for item in unified_words],
    }

    # Detect brand
    brand = detect_brand_name(combined_text)

    # Extract structured entities
    entities: dict[str, str] = {}
    for f in ALL_SUPPORTED_FIELDS:
        val = extract_value(f, combined_text)
        if val:
            entities[f] = val

    # Encode upright oriented image to JPEG bytes
    _, buf = cv2.imencode(".jpg", oriented)
    oriented_bytes = buf.tobytes()

    return {
        "quality": quality,
        "orientation": {
            "angle": degrees,
            "name": ori_name,
        },
        "oriented_image_bytes": oriented_bytes,
        "oriented_cv_image": oriented,
        "raw_ocr_text": combined_text,
        "ocr_box_data": primary_data,
        "brand_name": brand,
        "extracted_entities": entities,
    }
