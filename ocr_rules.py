import io
import os
import re
import shutil
from typing import Dict, Any, List, Optional
from PIL import Image, ImageDraw
import pytesseract

# Configure pytesseract path if on Windows and not in system PATH
if not shutil.which("tesseract") and os.path.exists(r"C:\Program Files\Tesseract-OCR\tesseract.exe"):
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Standard pack sizes under Schedule II (sample mappings in grams/ml)
SCHEDULE_II_PACK_SIZES = {
    "tea": [25, 50, 100, 250, 500, 1000],
    "biscuits": [25, 50, 75, 100, 150, 200, 250, 300],
    "soap": [25, 50, 75, 100, 125, 150]
}

# Common FMCG category nouns for Rule 6(1)(b)
COMMON_COMMODITY_NAMES = [
    "BISCUIT", "BISCUITS", "COOKIES", "CHOCOLATE", "CHOCOLATES",
    "NOODLES", "PASTA", "DETERGENT", "SHAMPOO", "SOAP", "TEA",
    "COFFEE", "RICE", "ATTA", "FLOUR", "WHEAT", "SNACK", "SNACKS",
    "NAMKEEN", "JUICE", "OIL", "GHEE", "MILK", "SPICE", "SPICES",
    "MASALA", "PULSES", "DAL", "SUGAR", "SALT", "BREAD", "BUTTER",
    "CHEESE", "PANEER", "YOGURT", "TOOTHPASTE", "LOTION", "CREAM",
    "CEREAL", "OATS", "SEEDS", "SAUCE", "KETCHUP", "VINEGAR",
    "HONEY", "WATER", "BEVERAGE", "CLEANER", "WASH", "CONDITIONER",
    "POWDER"
]

# Subset of food/perishable commodities for Proviso to Rule 6(1)
FOOD_COMMODITY_NAMES = {
    "BISCUIT", "BISCUITS", "COOKIES", "CHOCOLATE", "CHOCOLATES",
    "NOODLES", "PASTA", "TEA", "COFFEE", "RICE", "ATTA", "FLOUR",
    "WHEAT", "SNACK", "SNACKS", "NAMKEEN", "JUICE", "OIL", "GHEE",
    "MILK", "SPICE", "SPICES", "MASALA", "PULSES", "DAL", "SUGAR",
    "SALT", "BREAD", "BUTTER", "CHEESE", "PANEER", "YOGURT", "CEREAL",
    "OATS", "SEEDS", "SAUCE", "KETCHUP", "HONEY", "BEVERAGE"
}


def extract_text_with_boxes(image_bytes: bytes) -> tuple[str, Dict[str, Any]]:
    """Extract text and word-level bounding box data using Tesseract OCR."""
    if not image_bytes:
        return "", {}
    try:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)

        lines = []
        current_line = []
        last_line_id = None

        n_boxes = len(data.get("text", []))
        for i in range(n_boxes):
            word = data["text"][i].strip()
            line_id = (data["page_num"][i], data["block_num"][i], data["par_num"][i], data["line_num"][i])

            if last_line_id is not None and line_id != last_line_id:
                if current_line:
                    lines.append(" ".join(current_line))
                    current_line = []
            last_line_id = line_id

            if word:
                current_line.append(word)

        if current_line:
            lines.append(" ".join(current_line))

        full_text = "\n".join(lines).strip()
        if not full_text:
            full_text = pytesseract.image_to_string(image).strip()

        return full_text, data
    except Exception as e:
        try:
            image = Image.open(io.BytesIO(image_bytes))
            return pytesseract.image_to_string(image).strip(), {}
        except Exception:
            return "", {}


def run_tesseract_ocr(image_bytes: bytes) -> str:
    """Extract text from image bytes using Tesseract OCR."""
    text, _ = extract_text_with_boxes(image_bytes)
    return text


def extract_text(image_bytes: bytes) -> str:
    """Alias for run_tesseract_ocr."""
    return run_tesseract_ocr(image_bytes)


def annotate_image(image_bytes: bytes, ocr_data: Dict[str, Any], fields: List[Dict[str, str]]) -> Optional[bytes]:
    """Draw bounding boxes around regions matching fail (red) and review (amber) fields."""
    if not image_bytes:
        return None
    try:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        if not ocr_data or "text" not in ocr_data or not len(ocr_data["text"]):
            out_buf = io.BytesIO()
            image.save(out_buf, format="PNG")
            return out_buf.getvalue()

        draw = ImageDraw.Draw(image)

        # Red for fail (#E14B4B), Amber for review (#E0A93A)
        FAIL_COLOR = (225, 75, 75)
        REVIEW_COLOR = (224, 169, 58)

        fail_tokens = set()
        review_tokens = set()

        for f in fields:
            verdict = f.get("verdict", "").lower()
            evidence = f.get("evidence", "")
            if not evidence or verdict not in ("fail", "review"):
                continue

            words = [w.strip(".,;:()[]{}\'\"").upper() for w in re.split(r'\s+', evidence) if len(w.strip(".,;:()[]{}\'\"")) >= 2]
            stopwords = {"MISSING", "FOUND", "DECLARATION", "DETAILS", "REQUIRED", "VERIFY", "NOT", "THE", "AND", "FOR", "STANDARD", "UNIT", "RULE"}
            filtered = [w for w in words if w not in stopwords]

            if verdict == "fail":
                fail_tokens.update(filtered)
            elif verdict == "review":
                review_tokens.update(filtered)

        n_boxes = len(ocr_data.get("text", []))
        for i in range(n_boxes):
            word = ocr_data["text"][i].strip().upper()
            if not word or len(word) < 2:
                continue

            conf = int(ocr_data.get("conf", [0])[i])
            if conf < 10:
                continue

            x = int(ocr_data["left"][i])
            y = int(ocr_data["top"][i])
            w = int(ocr_data["width"][i])
            h = int(ocr_data["height"][i])

            color = None
            if any(token == word or (len(token) >= 3 and (token in word or word in token)) for token in fail_tokens):
                color = FAIL_COLOR
            elif any(token == word or (len(token) >= 3 and (token in word or word in token)) for token in review_tokens):
                color = REVIEW_COLOR

            if color:
                draw.rectangle([x - 2, y - 2, x + w + 2, y + h + 2], outline=color, width=3)

        out_buf = io.BytesIO()
        image.save(out_buf, format="PNG")
        return out_buf.getvalue()
    except Exception as e:
        print(f"Annotation error: {e}")
        return None


def evaluate_label_rules(raw_ocr_text: str) -> Dict[str, Any]:
    """Evaluate LMPC packaging and labeling rules against raw OCR text."""
    text = raw_ocr_text.upper() if raw_ocr_text else ""
    fields: List[Dict[str, str]] = []

    # Pre-extract Net Quantity for small package exemption & Schedule II pack size checks
    net_qty_match = re.search(r'(NET\s*(QTY|QUANTITY|WEIGHT|WT)|NET)\s*:?\s*(\d+(\.\d+)?)\s*(G|KG|ML|L|N|UNITS|GMS|GRMS|GMS\.)', text)
    extracted_qty_val = None
    extracted_qty_unit = None
    if net_qty_match:
        try:
            extracted_qty_val = float(net_qty_match.group(3))
            extracted_qty_unit = net_qty_match.group(5).rstrip('.')
        except (ValueError, TypeError):
            pass

    # Exemption Check: Packages under 10g / 10ml
    is_small_exempt = False
    if extracted_qty_val is not None and extracted_qty_unit in ["G", "ML", "GMS", "GRMS"]:
        if extracted_qty_val < 10:
            is_small_exempt = True
            fields.append({
                "rule_id": "LMPC_EXEMPT",
                "field": "Small Package Exemption",
                "verdict": "pass",
                "evidence": "Package under 10g/ml — exempt from full Rule 6 declaration requirements per LMPC 2011."
            })

    def add_field(entry: Dict[str, str], is_mandatory_for_small: bool = False):
        """Append field, skipping non-critical fail verdicts if package is exempt under 10g/ml."""
        if is_small_exempt and not is_mandatory_for_small and entry["verdict"] == "fail":
            return
        fields.append(entry)

    # 1. Manufacturer Name & Address (Rule 6(1)(a))
    mfg_match = re.search(r'(MFG|MANUFACTURED|PACKED|MARKETED)\s*(BY|AT)?:?\s*([A-Z0-9\s,.-]{5,100})', text)
    if mfg_match:
        add_field({
            "rule_id": "LMPC_R6_1_A",
            "field": "Manufacturer / Packer Details",
            "verdict": "pass",
            "evidence": mfg_match.group(0).strip()
        })
    else:
        add_field({
            "rule_id": "LMPC_R6_1_A",
            "field": "Manufacturer / Packer Details",
            "verdict": "fail",
            "evidence": "Missing manufacturer or packer declaration."
        })

    # 2. Common / Generic Name of Commodity (Rule 6(1)(b))
    generic_name_match = re.search(r'\b(?:' + '|'.join(re.escape(w) for w in COMMON_COMMODITY_NAMES) + r')\b', text)
    if generic_name_match:
        matched_term = generic_name_match.group(0).strip()
        add_field({
            "rule_id": "LMPC_R6_1_B",
            "field": "Common / Generic Name of Commodity",
            "verdict": "pass",
            "evidence": matched_term
        })
    else:
        add_field({
            "rule_id": "LMPC_R6_1_B",
            "field": "Common / Generic Name of Commodity",
            "verdict": "fail",
            "evidence": "Missing common/generic name of commodity."
        })

    # 3. Net Quantity & Statutory Unit Format Check (Rule 6(1)(c)) - Always mandatory
    if net_qty_match:
        extracted_unit = net_qty_match.group(5)
        # Check for non-standard unit symbols (Rule 6 format check)
        if extracted_unit in ["GMS", "GRMS", "GMS."]:
            add_field({
                "rule_id": "LMPC_R6_1_C",
                "field": "Net Quantity (Unit Format)",
                "verdict": "fail",
                "evidence": f"Found '{net_qty_match.group(0)}'. Non-standard unit symbol used; must use 'g' or 'kg'."
            }, is_mandatory_for_small=True)
        else:
            add_field({
                "rule_id": "LMPC_R6_1_C",
                "field": "Net Quantity",
                "verdict": "pass",
                "evidence": net_qty_match.group(0).strip()
            }, is_mandatory_for_small=True)
    else:
        add_field({
            "rule_id": "LMPC_R6_1_C",
            "field": "Net Quantity",
            "verdict": "fail",
            "evidence": "Missing or improperly formatted net quantity."
        }, is_mandatory_for_small=True)

    # 4. Schedule II Pack-Size Check (for Tea, Biscuits, Soap)
    detected_cat = None
    if re.search(r'\b(BISCUITS?|COOKIES?)\b', text):
        detected_cat = "biscuits"
    elif re.search(r'\bTEA\b', text):
        detected_cat = "tea"
    elif re.search(r'\bSOAPS?\b', text):
        detected_cat = "soap"

    if detected_cat and extracted_qty_val is not None and extracted_qty_unit:
        qty_in_std = extracted_qty_val * 1000 if extracted_qty_unit in ["KG", "L"] else extracted_qty_val
        is_std = (qty_in_std in SCHEDULE_II_PACK_SIZES[detected_cat]) or (int(qty_in_std) in SCHEDULE_II_PACK_SIZES[detected_cat])
        if not is_std:
            fields.append({
                "rule_id": "LMPC_SCHEDULE_II",
                "field": "Standard Pack Size (Schedule II)",
                "verdict": "review",
                "evidence": f"Declared net quantity {net_qty_match.group(0).strip()} is not in Schedule II standard pack sizes for {detected_cat.title()} ({SCHEDULE_II_PACK_SIZES[detected_cat]} g/ml). Verify non-standard pack size authorization."
            })

    # 5. Prohibited Count-Unit Check
    prohibited_count_match = re.search(
        r'\b(?:\d+\s*(?:DOZEN|PAIRS?)|(?:DOZEN|HALF\s*DOZEN)|(?:SET\s*OF|PACK\s*OF|PAIR\s*OF)\s*\d+(?!\s*(?:G|KG|ML|L|N|UNITS?\b)))\b',
        text
    )
    if prohibited_count_match:
        fields.append({
            "rule_id": "LMPC_FORMAT_UNIT",
            "field": "Declaration Format (Count Units)",
            "verdict": "fail",
            "evidence": f"Found non-standard count declaration '{prohibited_count_match.group(0).strip()}'. Quantities must be declared in standard metric units or 'units/N'."
        })

    # 6. Month & Year of Manufacture (Rule 6(1)(d))
    date_match = re.search(r'(MFG|PACKED|DATE|PKD)\s*:?\s*(\d{2}[/-]\d{2,4}|[A-Z]{3}\s*\d{4})', text)
    if date_match:
        add_field({
            "rule_id": "LMPC_R6_1_D",
            "field": "Date of Manufacture/Packing",
            "verdict": "pass",
            "evidence": date_match.group(0).strip()
        })
    else:
        add_field({
            "rule_id": "LMPC_R6_1_D",
            "field": "Date of Manufacture/Packing",
            "verdict": "fail",
            "evidence": "Missing manufacturing or packing date."
        })

    # 7. Maximum Retail Price (MRP) Check (Rule 6(1)(e)) - Always mandatory
    mrp_match = re.search(r'MRP\s*:?\s*(RS\.?|₹)?\s*(\d+(\.\d{1,2})?)', text)
    has_tax_phrase = "INCLUSIVE OF ALL TAXES" in text or "INCL. OF ALL TAXES" in text

    if mrp_match:
        if has_tax_phrase:
            add_field({
                "rule_id": "LMPC_R6_1_E",
                "field": "Maximum Retail Price (MRP)",
                "verdict": "pass",
                "evidence": f"{mrp_match.group(0)} (Inclusive of all taxes stated)"
            }, is_mandatory_for_small=True)
        else:
            add_field({
                "rule_id": "LMPC_R6_1_E",
                "field": "Maximum Retail Price (MRP)",
                "verdict": "fail",
                "evidence": f"Found '{mrp_match.group(0)}' but missing mandatory 'Inclusive of all taxes' phrase."
            }, is_mandatory_for_small=True)
    else:
        add_field({
            "rule_id": "LMPC_R6_1_E",
            "field": "Maximum Retail Price (MRP)",
            "verdict": "fail",
            "evidence": "Missing MRP declaration."
        }, is_mandatory_for_small=True)

    # 8. Consumer Care Details (Rule 6(1)(f))
    consumer_match = re.search(r'(CUSTOMER|CONSUMER)\s*(CARE|CELL|HELP)|\b\d{10}\b|[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}', text)
    if consumer_match:
        add_field({
            "rule_id": "LMPC_R6_1_F",
            "field": "Consumer Care Contact",
            "verdict": "pass",
            "evidence": consumer_match.group(0).strip()
        })
    else:
        add_field({
            "rule_id": "LMPC_R6_1_F",
            "field": "Consumer Care Contact",
            "verdict": "fail",
            "evidence": "Missing consumer grievance/care details."
        })

    # 9. Country of Origin (Rule 6(1)(g))
    is_imported = bool(re.search(r'\b(IMPORTED\s*BY|IMPORTER|IMPORTED)\b', text))
    origin_match = re.search(r'(COUNTRY\s*OF\s*ORIGIN|MADE\s*IN|PRODUCT\s*OF)\s*:?\s*([A-Z\s]{2,30})', text)
    if origin_match:
        add_field({
            "rule_id": "LMPC_R6_1_G",
            "field": "Country of Origin",
            "verdict": "pass",
            "evidence": origin_match.group(0).strip()
        })
    elif is_imported:
        add_field({
            "rule_id": "LMPC_R6_1_G",
            "field": "Country of Origin",
            "verdict": "fail",
            "evidence": "Missing country of origin declaration (mandatory for imported commodities)."
        })
    else:
        add_field({
            "rule_id": "LMPC_R6_1_G",
            "field": "Country of Origin",
            "verdict": "review",
            "evidence": "Missing country of origin declaration (mandatory only if imported; verify if commodity is domestic)."
        })

    # 10. Best-Before / Use-By Date (Proviso to Rule 6(1))
    exp_match = re.search(r'(BEST\s*BEFORE|USE\s*BY|EXPIRY(?:\s*DATE)?|EXP\.?(?:\s*DATE)?)\s*:?\s*(\d{2}[/-]\d{2,4}|[A-Z]{3}\s*\d{4}|\d+\s*(?:MONTHS?|DAYS?|YEARS?))', text)
    is_perishable = bool(generic_name_match and generic_name_match.group(0).strip() in FOOD_COMMODITY_NAMES)
    if exp_match:
        add_field({
            "rule_id": "LMPC_R6_1_PROVISO",
            "field": "Best-Before / Use-By Date",
            "verdict": "pass",
            "evidence": exp_match.group(0).strip()
        })
    elif is_perishable:
        add_field({
            "rule_id": "LMPC_R6_1_PROVISO",
            "field": "Best-Before / Use-By Date",
            "verdict": "fail",
            "evidence": "Missing best-before/use-by date (required for food/perishable commodities)."
        })
    else:
        add_field({
            "rule_id": "LMPC_R6_1_PROVISO",
            "field": "Best-Before / Use-By Date",
            "verdict": "review",
            "evidence": "Missing best-before/use-by date (verify if commodity is perishable / has defined shelf life)."
        })

    # Overall Score Calculation
    pass_count = sum(1 for f in fields if f["verdict"] == "pass")
    total_rules = len(fields)
    fail_count = sum(1 for f in fields if f["verdict"] == "fail")
    score = int((pass_count / total_rules) * 100) if total_rules > 0 else 0
    has_violation = fail_count > 0

    return {
        "score": score,
        "has_violation": has_violation,
        "fail_count": fail_count,
        "fields": fields
    }


def run_rule_engine(ocr_text: str) -> Dict[str, Any]:
    """Alias for evaluate_label_rules."""
    return evaluate_label_rules(ocr_text)


def score_and_verdict(results: Dict[str, Any]):
    """Extract score, has_violation, and fail_count from evaluation results."""
    return results["score"], results["has_violation"], results["fail_count"]
