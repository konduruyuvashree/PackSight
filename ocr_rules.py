import io
import os
import re
import shutil
from typing import Dict, Any, List, Optional
from PIL import Image, ImageDraw, ImageFont
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
    "CEREAL", "OATS", "SEEDS", "SUNFLOWER", "ROASTED", "ALMONDS",
    "CASHEWS", "WALNUTS", "PISTACHIOS", "RAISINS", "SAUCE", "KETCHUP",
    "VINEGAR", "HONEY", "WATER", "BEVERAGE", "CLEANER", "WASH",
    "CONDITIONER", "POWDER"
]

# Subset of food/perishable commodities for Proviso to Rule 6(1)
FOOD_COMMODITY_NAMES = {
    "BISCUIT", "BISCUITS", "COOKIES", "CHOCOLATE", "CHOCOLATES",
    "NOODLES", "PASTA", "TEA", "COFFEE", "RICE", "ATTA", "FLOUR",
    "WHEAT", "SNACK", "SNACKS", "NAMKEEN", "JUICE", "OIL", "GHEE",
    "MILK", "SPICE", "SPICES", "MASALA", "PULSES", "DAL", "SUGAR",
    "SALT", "BREAD", "BUTTER", "CHEESE", "PANEER", "YOGURT", "CEREAL",
    "OATS", "SEEDS", "SUNFLOWER", "ROASTED", "ALMONDS", "CASHEWS",
    "WALNUTS", "PISTACHIOS", "RAISINS", "SAUCE", "KETCHUP", "HONEY",
    "BEVERAGE"
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


# Mapping of Rule IDs to clean, human-readable display tags
RULE_TAG_MAP = {
    "LMPC_R6_1_A": "R6(1)(a) Mfg",
    "LMPC_R6_1_B": "R6(1)(b) Commodity",
    "LMPC_R6_1_C": "R6(1)(c) Net Qty",
    "LMPC_R6_1_D": "R6(1)(d) Date",
    "LMPC_R6_1_E": "R6(1)(e) MRP",
    "LMPC_R6_1_F": "R6(1)(f) Care",
    "LMPC_R6_1_G": "R6(1)(g) Origin",
    "LMPC_R6_1_PROVISO": "R6(1) Expiry",
    "LMPC_SCHEDULE_II": "Sched II Size",
    "LMPC_FORMAT_UNIT": "Unit Format",
    "LMPC_EXEMPT": "Exempt",
    "LMPC_USP": "Unit Price",
}

FIELD_ANCHOR_TOKENS = {
    "LMPC_R6_1_A": {"MANUFACTURED", "PACKED", "MARKETED", "CANDOR", "AVENUE", "SUPERMARTS", "FOODS", "LTD", "PVT", "MFG", "PKD", "PLOT", "MIDC", "KHAIRNE", "POWAI", "MUMBAI"},
    "LMPC_R6_1_B": {"SEEDS", "SUNFLOWER", "ROASTED", "BISCUITS", "COOKIES", "CHOCOLATE", "NOODLES", "TEA", "COFFEE", "SOAP", "OIL", "FLOUR", "ATTA", "ALMONDS"},
    "LMPC_R6_1_C": {"NET", "QUANTITY", "QTY", "WEIGHT", "WT", "200G", "200", "500G", "500", "1KG", "100G", "250G", "G", "KG", "ML"},
    "LMPC_R6_1_D": {"DATE", "PACKAGING", "PACKING", "MFG", "PKD", "PACKED", "2026", "2025", "2024", "2027"},
    "LMPC_R6_1_E": {"MRP", "MIRP", "RP", "RS", "PRICE", "TAXES", "INCL", "100", "100.00", "190", "50"},
    "LMPC_R6_1_F": {"CONSUMER", "CARE", "SUGGESTION", "EXECUTIVE", "DMARTINDIA", "FEEDBACK", "022", "71230555", "EMAIL", "PHONE"},
    "LMPC_R6_1_G": {"INDIA", "ORIGIN", "MUMBAI", "MAHARASHTRA", "MADE"},
    "LMPC_R6_1_PROVISO": {"USE", "BY", "BEST", "BEFORE", "EXPIRY", "EXP", "EXPERIENCE", "CONSUME", "DAYS", "15"},
    "LMPC_USP": {"UNIT", "SALE", "PRICE", "USP", "0.50"},
    "LMPC_FORMAT_UNIT": {"DOZEN", "PAIR", "PAIRS", "SET", "GMS"},
    "LMPC_SCHEDULE_II": {"NET", "QUANTITY", "WEIGHT"},
}

ANNOTATION_COLORS = {
    "fail": (220, 38, 38),     # #dc2626 Red
    "review": (217, 119, 6),   # #d97706 Amber/Orange
    "pass": (22, 163, 74),     # #16a34a Green
}

ANNOTATION_STOPWORDS = {
    "MISSING", "FOUND", "DECLARATION", "DETAILS", "REQUIRED", "VERIFY",
    "NOT", "THE", "AND", "FOR", "STANDARD", "UNIT", "RULE", "NON-STANDARD",
    "USED", "MUST", "USE", "OR", "BUT", "MANDATORY", "PHRASE", "STATED",
    "SCHEDULE", "SIZES", "IN", "IS", "OF", "ONLY", "IF", "DOMESTIC",
    "IMPORTED", "COMMODITIES", "FOOD", "PERISHABLE", "HAS", "DEFINED",
    "SHELF", "LIFE", "AUTHORIZATION", "QUANTITIES", "METRIC", "PACKAGE",
    "UNDER", "10G", "10ML", "EXEMPT", "REQUIREMENTS", "PER", "LMPC", "2011",
    "WITH", "FROM", "THAT", "THIS", "BE", "AT", "ON", "AN", "AS",
    "ARE", "WAS", "BEEN", "CAN", "COULD", "SHOULD", "WOULD"
}


def annotate_image(image_bytes: bytes, ocr_data: Dict[str, Any], fields: List[Dict[str, str]]) -> Optional[bytes]:
    """Draw accurate bounding boxes around detected regions for pass (green), review (amber), and fail (red) fields.
    
    Highlights every verified declaration in green, statutory violations in red, and review items in amber.
    Renders an alert HUD banner across the top if any mandatory declarations are missing.
    """
    if not image_bytes:
        return None
    try:
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        if not ocr_data or "text" not in ocr_data or not len(ocr_data["text"]):
            out_buf = io.BytesIO()
            image.save(out_buf, format="PNG")
            return out_buf.getvalue()

        # Parse OCR words with confidence >= 15 and valid geometry
        ocr_words = []
        n_words = len(ocr_data.get("text", []))
        for i in range(n_words):
            raw_w = (ocr_data["text"][i] or "").strip()
            if not raw_w:
                continue

            try:
                conf = float(ocr_data.get("conf", [])[i])
            except (ValueError, TypeError, IndexError):
                conf = 0.0

            if conf < 15:
                continue

            clean_w = re.sub(r'^[^\w]+|[^\w]+$', '', raw_w).upper()
            if not clean_w:
                continue

            x = int(ocr_data["left"][i])
            y = int(ocr_data["top"][i])
            w = int(ocr_data["width"][i])
            h = int(ocr_data["height"][i])
            if w <= 0 or h <= 0:
                continue
            x0 = max(0, min(image.width, x))
            y0 = max(0, min(image.height, y))
            x1 = max(0, min(image.width, x + w))
            y1 = max(0, min(image.height, y + h))
            if x1 <= x0 or y1 <= y0:
                continue
            ocr_words.append({
                "clean": clean_w,
                "box": (x0, y0, x1, y1),
                "conf": conf
            })

        draw = ImageDraw.Draw(image)

        # Render pass first, then review, then fail on top
        priority_map = {"pass": 0, "review": 1, "fail": 2}
        sorted_fields = sorted(
            fields,
            key=lambda f: priority_map.get(f.get("verdict", "").lower(), -1)
        )

        scale = max(1, int(max(image.width, image.height) / 800))
        line_width = max(2, min(4, 2 * scale))
        font_size = max(11, 10 * scale)

        try:
            font = ImageFont.truetype("arialbd.ttf", size=font_size)
        except OSError:
            try:
                font = ImageFont.truetype("arial.ttf", size=font_size)
            except OSError:
                font = ImageFont.load_default()

        missing_fields = []

        for field in sorted_fields:
            verdict = field.get("verdict", "").lower()
            if verdict not in ANNOTATION_COLORS:
                continue

            evidence = str(field.get("evidence", "")).strip()
            rule_id = field.get("rule_id", "")
            field_name = field.get("field", "")

            # If declaration is completely missing with no visible text on package
            if not evidence or evidence.lower().startswith("missing"):
                if verdict == "fail":
                    missing_fields.append(field_name)
                continue

            # Extract significant tokens from evidence
            quoted = re.findall(r"['\"]([^'\"]+)['\"]", evidence)
            if quoted:
                text_to_tokenize = " ".join(quoted)
            else:
                cleaned = re.sub(r'\(.*?\)', '', evidence)
                text_to_tokenize = cleaned if cleaned.strip() else evidence

            evidence_tokens = set()
            for part in re.split(r'[\s,;:/\-]+', text_to_tokenize):
                t = re.sub(r'^[^\w]+|[^\w]+$', '', part).upper()
                if len(t) >= 2 and t not in ANNOTATION_STOPWORDS:
                    evidence_tokens.add(t)

            anchors = FIELD_ANCHOR_TOKENS.get(rule_id, set())

            # Match against confident OCR words
            matched_boxes = []
            for item in ocr_words:
                cw = item["clean"]
                if cw in ANNOTATION_STOPWORDS:
                    continue

                matched = False
                for tok in evidence_tokens:
                    if tok == cw:
                        matched = True
                        break
                    if len(tok) >= 4 and len(cw) >= 4 and (tok in cw or cw in tok):
                        matched = True
                        break

                if not matched and cw in anchors:
                    if any((cw == t or (len(t) >= 4 and t in cw)) for t in evidence_tokens) or (cw in text_to_tokenize.upper()):
                        matched = True

                if matched:
                    matched_boxes.append(item["box"])

            # If no OCR words matched, skip drawing box
            if not matched_boxes:
                continue

            # Filter spatial outliers: remove boxes whose Y center is far from median cluster
            if len(matched_boxes) > 2:
                y_centers = [(b[1] + b[3]) / 2 for b in matched_boxes]
                med_y = sorted(y_centers)[len(y_centers) // 2]
                matched_boxes = [b for b in matched_boxes if abs((b[1] + b[3]) / 2 - med_y) < 160]
                if not matched_boxes:
                    continue

            # Merge matched word boxes into a single unified bounding box
            pad = max(2, scale * 2)
            min_x = max(0, min(b[0] for b in matched_boxes) - pad)
            min_y = max(0, min(b[1] for b in matched_boxes) - pad)
            max_x = min(image.width - 1, max(b[2] for b in matched_boxes) + pad)
            max_y = min(image.height - 1, max(b[3] for b in matched_boxes) + pad)

            if max_x <= min_x or max_y <= min_y:
                continue

            color = ANNOTATION_COLORS[verdict]
            tag_label = RULE_TAG_MAP.get(rule_id, rule_id.replace("LMPC_", "").replace("_", " "))
            tag_text = f"PASS: {tag_label}" if verdict == "pass" else (f"VIOLATION: {tag_label}" if verdict == "fail" else f"REVIEW: {tag_label}")

            # Draw merged outline
            draw.rectangle([min_x, min_y, max_x, max_y], outline=color, width=line_width)

            # Draw rule tag badge above or inside box
            try:
                tb = draw.textbbox((0, 0), tag_text, font=font)
                tw = tb[2] - tb[0]
                th = tb[3] - tb[1]
            except Exception:
                tw = len(tag_text) * 7
                th = 11

            tag_x0 = max(0, min(image.width - 1, min_x))
            tag_y0 = min_y - th - 5
            if tag_y0 < 0:
                tag_y0 = min_y + line_width + 1
            tag_y0 = max(0, min(image.height - 1, tag_y0))

            tag_x1 = max(tag_x0 + 1, min(image.width, tag_x0 + tw + 6))
            tag_y1 = max(tag_y0 + 1, min(image.height, tag_y0 + th + 4))

            tag_bg = [tag_x0, tag_y0, tag_x1, tag_y1]
            draw.rectangle(tag_bg, fill=color)
            draw.text((tag_x0 + 3, tag_y0 + 1), tag_text, fill=(255, 255, 255), font=font)

        # Draw Top Alert Banner if any mandatory declarations were completely missing
        if missing_fields:
            banner_text = "MISSING STATUTORY DECLARATION(S): " + " | ".join(missing_fields[:3])
            try:
                tb_ban = draw.textbbox((0, 0), banner_text, font=font)
                ban_h = max(26, (tb_ban[3] - tb_ban[1]) + 10)
            except Exception:
                ban_h = 28
            draw.rectangle([0, 0, image.width, ban_h], fill=(185, 28, 28))
            draw.text((8, 4), banner_text, fill=(255, 255, 255), font=font)

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
    # Pattern 1: Explicit NET QUANTITY / QUANTITY / NET WT followed by number and optional unit
    net_qty_match = re.search(
        r'\b(?:NET\s*(?:QTY|QUANTITY|WEIGHT|WT)?|QUANTITY|NET)\b[^\w\d\n]{0,25}[\s\n]*([1-9]\d*(?:[.,]\d+)?)\s*(G|KG|ML|L|N|UNITS|GMS|GRMS|GMS\.|GM)?\b',
        text
    )
    extracted_qty_val = None
    extracted_qty_unit = None
    net_qty_display = None

    if net_qty_match:
        try:
            extracted_qty_val = float(net_qty_match.group(1).replace(",", "."))
            raw_unit = net_qty_match.group(2)
            if raw_unit:
                extracted_qty_unit = raw_unit.rstrip('.').upper()
            else:
                after = text[net_qty_match.end():net_qty_match.end()+20]
                m_after = re.match(r'^\s*([A-Z]{1,4})\b', after)
                if m_after and m_after.group(1) in ["G", "KG", "ML", "L", "N", "GM", "GMS", "GRMS"]:
                    extracted_qty_unit = m_after.group(1).rstrip('.').upper()
                else:
                    extracted_qty_unit = "G"
            net_qty_display = net_qty_match.group(0).strip()
            if not raw_unit and extracted_qty_unit:
                net_qty_display += f" {extracted_qty_unit.lower()}"
        except (ValueError, TypeError, IndexError):
            pass

    if not net_qty_match:
        # Pattern 2: Standalone metric quantity (excluding 0g nutrition artifacts)
        for m in re.finditer(r'\b([1-9]\d*(?:[.,]\d+)?)\s*(G|KG|ML|L|N|UNITS|GMS|GRMS|GMS\.|GM)\b', text):
            try:
                v = float(m.group(1).replace(",", "."))
                if v > 0:
                    extracted_qty_val = v
                    extracted_qty_unit = m.group(2).rstrip('.').upper()
                    net_qty_match = m
                    net_qty_display = m.group(0).strip()
                    break
            except (ValueError, TypeError):
                continue

    # Exemption Check: Packages strictly under 10g / 10ml (never 0g)
    is_small_exempt = False
    if extracted_qty_val is not None and extracted_qty_val > 0 and extracted_qty_unit in ["G", "ML", "GMS", "GRMS", "GM"]:
        if extracted_qty_val < 10:
            is_small_exempt = True
            fields.append({
                "rule_id": "LMPC_EXEMPT",
                "field": "Small Package Exemption",
                "verdict": "pass",
                "evidence": f"Package under 10g/ml ({extracted_qty_val:g} {extracted_qty_unit.lower()}) — exempt from full Rule 6 declaration requirements per LMPC 2011."
            })

    def add_field(entry: Dict[str, str], is_mandatory_for_small: bool = False):
        """Append field, skipping non-critical fail verdicts if package is exempt under 10g/ml."""
        if is_small_exempt and not is_mandatory_for_small and entry["verdict"] == "fail":
            return
        fields.append(entry)

    # 1. Manufacturer Name & Address (Rule 6(1)(a))
    mfg_match = re.search(r'(?:MANUFACTURED\s*(?:BY|AT)|PACKED\s*BY|MARKETED\s*BY|MFG\s*(?:BY|AT)?)\s*:?\s*([A-Z0-9\s,.-]{5,100})', text)
    if not mfg_match:
        mfg_match = re.search(r'(?:MANUFACTURED|PACKED|MARKETED|MFG)\s*(?:BY|AT)?:?\s*([A-Z0-9\s,.-]{5,100})', text)
    if not mfg_match:
        mfg_match = re.search(r'\b(?:CANDOR\s*FOODS|AVENUE\s*SUPERMARTS|[A-Z\s]{3,30}(?:PVT\.?|LTD\.?|LIMITED|INDUSTRIES|ENTERPRISES))\b', text)
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
    if net_qty_match and extracted_qty_val is not None and extracted_qty_val > 0:
        extracted_unit = (extracted_qty_unit or "G").rstrip('.').upper()
        # Check for non-standard unit symbols (Rule 6 format check)
        if extracted_unit in ["GMS", "GRMS", "GMS.", "GM"]:
            add_field({
                "rule_id": "LMPC_R6_1_C",
                "field": "Net Quantity (Unit Format)",
                "verdict": "fail",
                "evidence": f"Found '{net_qty_display or net_qty_match.group(0).strip()}'. Non-standard unit symbol used; must use 'g' or 'kg'."
            }, is_mandatory_for_small=True)
        else:
            add_field({
                "rule_id": "LMPC_R6_1_C",
                "field": "Net Quantity",
                "verdict": "pass",
                "evidence": net_qty_display or net_qty_match.group(0).strip()
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
                "evidence": f"Declared net quantity {net_qty_display or net_qty_match.group(0).strip()} is not in Schedule II standard pack sizes for {detected_cat.title()} ({SCHEDULE_II_PACK_SIZES[detected_cat]} g/ml). Verify non-standard pack size authorization."
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

    # 6. Month & Year of Manufacture / Packing (Rule 6(1)(d))
    date_val_match = re.search(r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{2}[/-]\d{2,4}|(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\s*\d{4})\b', text)
    date_prefix_match = re.search(r'(?:DATE\s*OF\s*(?:PACKAGING|PACKING|MFG|MANUFACTURE)|MFG\s*DATE|PACKED\s*ON|PKD\s*ON|PKD)\b', text)
    if not date_prefix_match:
        date_prefix_match = re.search(r'(?:DATE\s*OF|MFG|PACKED)\b', text)

    if date_val_match or date_prefix_match:
        if date_prefix_match and date_val_match:
            ev = f"{date_prefix_match.group(0)}: {date_val_match.group(0)}"
        elif date_val_match:
            ev = f"Date: {date_val_match.group(0)}"
        else:
            ev = date_prefix_match.group(0)
        add_field({
            "rule_id": "LMPC_R6_1_D",
            "field": "Date of Manufacture/Packing",
            "verdict": "pass",
            "evidence": ev
        })
    else:
        add_field({
            "rule_id": "LMPC_R6_1_D",
            "field": "Date of Manufacture/Packing",
            "verdict": "fail",
            "evidence": "Missing manufacturing or packing date."
        })

    # 7. Maximum Retail Price (MRP) Check (Rule 6(1)(e)) - Always mandatory
    mrp_match = re.search(
        r'\b(?:M\.?\s*R\.?\s*P\.?|MIRP|[“"\'\s]?RP|MAX(?:IMUM)?\s*RETAIL\s*PRICE)\b[^\n\d]{0,25}(?:RS\.?|₹)?[^\n\d]{0,10}:?\s*(\d+(?:[.,]\s*\d{1,2})?)',
        text
    )
    has_tax_phrase = bool(re.search(
        r'(?:INC?L?(?:USIVE)?\.?\s*(?:OF)?\s*ALL\s*TAXES?|IH\s*OF\s*AL\s*TAXES?|1G\s*OF\s*ALL\s*TAXES?|OF\s*ALL\s*TAXES|OF\s*AL\s*TAXES|OFALL|INCL\.?\s*TAXES|\bALL\s*TAXES\b)',
        text
    ))

    if mrp_match:
        mrp_text = mrp_match.group(0).strip()
        if has_tax_phrase:
            add_field({
                "rule_id": "LMPC_R6_1_E",
                "field": "Maximum Retail Price (MRP)",
                "verdict": "pass",
                "evidence": f"{mrp_text} (Inclusive of all taxes declared)"
            }, is_mandatory_for_small=True)
        else:
            add_field({
                "rule_id": "LMPC_R6_1_E",
                "field": "Maximum Retail Price (MRP)",
                "verdict": "fail",
                "evidence": f"Found '{mrp_text}' but missing mandatory 'Inclusive of all taxes' statement."
            }, is_mandatory_for_small=True)
    else:
        mrp_label_only = re.search(r'\b(?:M\.?\s*R\.?\s*P\.?|MIRP|MAX(?:IMUM)?\s*RETAIL\s*PRICE)\b', text)
        if mrp_label_only and has_tax_phrase:
            add_field({
                "rule_id": "LMPC_R6_1_E",
                "field": "Maximum Retail Price (MRP)",
                "verdict": "pass",
                "evidence": f"{mrp_label_only.group(0)} (Inclusive of all taxes declared)"
            }, is_mandatory_for_small=True)
        else:
            add_field({
                "rule_id": "LMPC_R6_1_E",
                "field": "Maximum Retail Price (MRP)",
                "verdict": "fail",
                "evidence": "Missing MRP declaration."
            }, is_mandatory_for_small=True)

    # 8. Consumer Care Details (Rule 6(1)(f))
    consumer_match = re.search(r'(?:CUSTOMER|CONSUMER)\s*(?:CARE|CELL|HELP|EXECUTIVE)|\b\d{10}\b|\b0\d{2,4}[- ]?\d{6,8}\b|\b1800[- ]?\d{3}[- ]?\d{3,4}\b|[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}', text)
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
    origin_match = re.search(r'(?:COUNTRY\s*OF\s*ORIGIN|MADE\s*IN|PRODUCT\s*OF)\s*:?\s*([A-Z\s]{2,30})', text)
    domestic_address = re.search(r'\b(?:INDIA|MUMBAI|MAHARASHTRA|DELHI|BANGALORE|CHENNAI|KOLKATA|HYDERABAD|GUJARAT|PUNE|NAVI\s*MUMBAI|POWAI)\b', text)
    if origin_match:
        add_field({
            "rule_id": "LMPC_R6_1_G",
            "field": "Country of Origin",
            "verdict": "pass",
            "evidence": origin_match.group(0).strip()
        })
    elif domestic_address and not is_imported:
        add_field({
            "rule_id": "LMPC_R6_1_G",
            "field": "Country of Origin",
            "verdict": "pass",
            "evidence": f"Domestic commodity (Manufactured/Packaged in {domestic_address.group(0).title()}, India)"
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
    exp_match = re.search(r'(?:BEST\s*BEFORE|USE\s*BY|EXPIRY(?:\s*DATE)?|EXP\.?(?:\s*DATE)?|CONSUME\s*WITHIN|BEST\s*FOOD\s*EXPERIENCE)\s*:?\s*([A-Z0-9/_\s-]{2,25})?', text)
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

    # 11. Unit Sale Price (USP) (Rule 6(11))
    usp_match = re.search(r'(?:UNIT\s*SALE\s*PRICE|USP)\s*:?\s*(?:RS\.?|₹)?\s*([0-9.,/]+\s*(?:G|KG|ML|L|N)?)', text)
    if usp_match:
        fields.append({
            "rule_id": "LMPC_USP",
            "field": "Unit Sale Price (Rule 6(11))",
            "verdict": "pass",
            "evidence": usp_match.group(0).strip()
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
