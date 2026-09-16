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
    "SWEETENED CONDENSED MILK", "CONDENSED MILK", "SKIMMED MILK", "MILKMAID", "DAIRY",
    "BISCUIT", "BISCUITS", "COOKIES", "CHOCOLATE", "CHOCOLATES",
    "NOODLES", "PASTA", "DETERGENT", "SHAMPOO", "SOAP", "TEA",
    "COFFEE", "RICE", "ATTA", "FLOUR", "WHEAT", "SNACK", "SNACKS",
    "NAMKEEN", "JUICE", "OIL", "GHEE", "MILK", "SPICE", "SPICES",
    "MASALA", "PULSES", "DAL", "SUGAR", "SALT", "BREAD", "BUTTER",
    "CHEESE", "PANEER", "YOGURT", "TOOTHPASTE", "LOTION", "CREAM",
    "CEREAL", "OATS", "SEEDS", "SUNFLOWER", "ROASTED", "ALMONDS",
    "CASHEWS", "WALNUTS", "PISTACHIOS", "RAISINS", "SAUCE", "KETCHUP",
    "VINEGAR", "HONEY", "WATER", "BEVERAGE", "CLEANER", "WASH",
    "CONDITIONER", "POWDER", "CORN FLAKES", "MAKHANA", "POHA", "CHIPS",
    "WAFERS", "BESAN", "SUJI", "RAVA", "SOJI", "MUSTARD OIL", "SOYBEAN OIL",
    "SUNFLOWER OIL", "COCONUT OIL", "OLIVE OIL", "GROUNDNUT OIL", "SESAME OIL",
    "JEERA", "TURMERIC", "HALDI", "PEPPER", "CARDAMOM", "CLOVE", "CINNAMON",
    "CORIANDER", "CUMIN", "RAJMA", "CHANA", "MOONG", "TOOR", "URAD", "MASOOR",
    "MAYONNAISE", "JAM", "PICKLE", "PAPAD", "GINGER GARLIC PASTE"
]

# Subset of food/perishable commodities for Proviso to Rule 6(1)
FOOD_COMMODITY_NAMES = {
    "SWEETENED CONDENSED MILK", "CONDENSED MILK", "SKIMMED MILK", "MILKMAID", "DAIRY",
    "BISCUIT", "BISCUITS", "COOKIES", "CHOCOLATE", "CHOCOLATES",
    "NOODLES", "PASTA", "TEA", "COFFEE", "RICE", "ATTA", "FLOUR",
    "WHEAT", "SNACK", "SNACKS", "NAMKEEN", "JUICE", "OIL", "GHEE",
    "MILK", "SPICE", "SPICES", "MASALA", "PULSES", "DAL", "SUGAR",
    "SALT", "BREAD", "BUTTER", "CHEESE", "PANEER", "YOGURT", "CEREAL",
    "OATS", "SEEDS", "SUNFLOWER", "ROASTED", "ALMONDS", "CASHEWS",
    "WALNUTS", "PISTACHIOS", "RAISINS", "SAUCE", "KETCHUP", "HONEY",
    "BEVERAGE", "CORN FLAKES", "MAKHANA", "POHA", "CHIPS", "WAFERS",
    "BESAN", "SUJI", "RAVA", "SOJI", "MUSTARD OIL", "SOYBEAN OIL",
    "SUNFLOWER OIL", "COCONUT OIL", "OLIVE OIL", "GROUNDNUT OIL", "SESAME OIL",
    "JEERA", "TURMERIC", "HALDI", "PEPPER", "CARDAMOM", "CLOVE", "CINNAMON",
    "CORIANDER", "CUMIN", "RAJMA", "CHANA", "MOONG", "TOOR", "URAD", "MASOOR",
    "MAYONNAISE", "JAM", "PICKLE", "PAPAD", "GINGER GARLIC PASTE"
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
    "LMPC_R6_1_A": {"MANUFACTURED", "PACKED", "MARKETED", "CANDOR", "AVENUE", "SUPERMARTS", "FOODS", "LTD", "PVT", "MFG", "MFD", "MFR", "PKD", "MKTD", "PRODUCED", "PACKAGED", "LLP", "CORP", "PLOT", "MIDC", "KHAIRNE", "POWAI", "MUMBAI", "NESTLE", "LIMITED", "MOGA", "NEW", "DELHI", "LUDHIANA", "FEROZEPUR"},
    "LMPC_R6_1_B": {"SEEDS", "SUNFLOWER", "ROASTED", "BISCUITS", "COOKIES", "CHOCOLATE", "NOODLES", "TEA", "COFFEE", "SOAP", "OIL", "FLOUR", "ATTA", "ALMONDS", "MILKMAID", "CONDENSED", "MILK", "SWEETENED", "DAIRY", "SKIMMED", "MAKHANA", "CORN", "FLAKES", "CHIPS", "COMMODITY", "PRODUCT"},
    "LMPC_R6_1_C": {"NET", "QUANTITY", "QTY", "WEIGHT", "WT", "CONTENTS", "200G", "200", "500G", "500", "1KG", "100G", "250G", "190G", "190", "G", "KG", "ML", "L", "N"},
    "LMPC_R6_1_D": {"DATE", "PACKAGING", "PACKING", "MFG", "MFD", "PKD", "PACKED", "2026", "2025", "2024", "2027", "08/07/26", "08/07", "61890451", "61890451YB", "LOT", "BATCH"},
    "LMPC_R6_1_E": {"MRP", "MIRP", "RP", "RS", "PRICE", "TAXES", "INCL", "100", "100.00", "190", "50", "84", "84.00", "PANEL", "SIDE", "MAXIMUM"},
    "LMPC_R6_1_F": {"CONSUMER", "CARE", "SUGGESTION", "EXECUTIVE", "DMARTINDIA", "FEEDBACK", "022", "71230555", "EMAIL", "PHONE", "WECARE", "HELPLINE", "TOLL", "FREE", "18001031947", "1800"},
    "LMPC_R6_1_G": {"INDIA", "ORIGIN", "MUMBAI", "MAHARASHTRA", "MADE", "DELHI", "PUNJAB", "MOGA", "PRODUCED"},
    "LMPC_R6_1_PROVISO": {"USE", "BY", "BEST", "BEFORE", "EXPIRY", "EXP", "EXPERIENCE", "CONSUME", "DAYS", "MONTHS", "15", "08/05/27", "08/05", "SIDE", "PANEL"},
    "LMPC_USP": {"UNIT", "SALE", "PRICE", "USP", "0.50", "0.44", "PER"},
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
    # Pattern 1: Explicit NET QUANTITY / QUANTITY / NET WT / NET CONTENTS followed by number and optional unit
    net_qty_match = re.search(
        r'\b(?:NET\s*(?:QTY|QUANTITY|WEIGHT|WT|CONTENTS?|MASS|VOL|VOLUME)?|QUANTITY|NET\b(?!\s*PRICE))\b[^\w\d\n]{0,25}[\s\n]*([0-9]+(?:[.,]\d+)?)\s*(G|KG|ML|L|N|UNITS?|GMS|GRMS|GMS\.|GM)?\b',
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
                m_after = re.match(r'^\s*([A-Z]{1,5})\b', after)
                if m_after and m_after.group(1) in ["G", "KG", "ML", "L", "N", "GM", "GMS", "GRMS", "UNITS"]:
                    extracted_qty_unit = m_after.group(1).rstrip('.').upper()
                else:
                    extracted_qty_unit = "G"
            clean_match_str = re.sub(r'\s+', ' ', net_qty_match.group(0)).strip()
            net_qty_display = clean_match_str
            if not raw_unit and extracted_qty_unit:
                net_qty_display += f" {extracted_qty_unit.lower()}"
        except (ValueError, TypeError, IndexError):
            pass

    if not net_qty_match:
        # Pattern 2: Standalone metric quantity (excluding 0g nutrition artifacts)
        for m in re.finditer(r'\b([0-9]+(?:[.,]\d+)?)\s*(G|KG|ML|L|N|UNITS?|GMS|GRMS|GMS\.|GM)\b', text):
            try:
                v = float(m.group(1).replace(",", "."))
                if v > 0:
                    prefix = text[max(0, m.start()-25):m.start()]
                    if any(n in prefix for n in ["FAT", "PROTEIN", "CARB", "SUGAR", "SODIUM", "CHOLESTEROL", "ENERGY", "CALORIES", "SATURATED"]):
                        continue
                    extracted_qty_val = v
                    extracted_qty_unit = m.group(2).rstrip('.').upper()
                    net_qty_match = m
                    net_qty_display = re.sub(r'\s+', ' ', m.group(0)).strip()
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
    mfg_match = re.search(
        r'\b(?:MANUFACTURED|PACKED|PACKAGED|MARKETED|PRODUCED|PROCESSED)\s*(?:AND\s+PACKED\s+)?(?:BY|AT|FOR)\s*[:\-]?\s*([^\n]{3,100})',
        text
    )
    if not mfg_match:
        mfg_match = re.search(
            r'\b(?:MFD|MFG|MFR|PKD|MKTD)\.?\s*(?:AND\s+PKD\.?\s+)?(?:BY|AT|FOR)\s*[:\-]?\s*([^\n]{3,100})',
            text
        )
    if not mfg_match:
        mfg_match = re.search(
            r'\b(?:MANUFACTURED|PACKED|PACKAGED|MARKETED|PRODUCED|PROCESSED)(?!\s*(?:DATE|DT\b|ON\b|IN\s*INDIA))\s*[:\-]?\s*([^\n]{3,100})',
            text
        )
    if not mfg_match:
        mfg_match = re.search(
            r'\b(?:CANDOR\s*FOODS|AVENUE\s*SUPERMARTS|[A-Z\s]{3,35}(?:PVT\.?|LTD\.?|LIMITED|CORP(?:ORATION)?|LLP|INDUSTRIES|ENTERPRISES))\b',
            text
        )

    if mfg_match:
        ev_mfg = re.sub(r'\s+', ' ', mfg_match.group(0)).strip()
        add_field({
            "rule_id": "LMPC_R6_1_A",
            "field": "Manufacturer / Packer Details",
            "verdict": "pass",
            "evidence": ev_mfg
        })
    else:
        add_field({
            "rule_id": "LMPC_R6_1_A",
            "field": "Manufacturer / Packer Details",
            "verdict": "fail",
            "evidence": "Missing manufacturer or packer declaration."
        })

    # 2. Common / Generic Name of Commodity (Rule 6(1)(b))
    commodity_header_match = re.search(
        r'\b(?:NAME\s*OF\s*(?:THE\s*)?COMMODITY|COMMODITY|PRODUCT\s*NAME|PRODUCT|GENERIC\s*NAME|ITEM\s*NAME|ITEM)\s*[:\-]\s*([^\n,;]{2,60})',
        text
    )
    generic_name_match = re.search(r'\b(?:' + '|'.join(re.escape(w) for w in COMMON_COMMODITY_NAMES) + r')\b', text)
    
    if commodity_header_match:
        matched_term = commodity_header_match.group(1).strip()
        add_field({
            "rule_id": "LMPC_R6_1_B",
            "field": "Common / Generic Name of Commodity",
            "verdict": "pass",
            "evidence": matched_term
        })
    elif generic_name_match:
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
    mfg_date_direct = re.search(
        r'\b(?:DATE\s*OF\s*(?:PACKAGING|PACKING|MFG|MANUFACTURE)|MFG\.?\s*DATE|MFD\.?\s*DATE|MFD\.?\s*ON|MFG\.?\s*ON|PACKED\s*ON|PKD\.?\s*ON|PACKED|MFD|MFG|PKD)\b'
        r'[:\s\-\.]*(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}|\d{1,2}[/.-]\d{2,4}|(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*\s*[\d]{2,4}|\d{1,2}\s+(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*\s+\d{2,4})\b',
        text
    )
    
    if mfg_date_direct:
        ev = re.sub(r'\s+', ' ', mfg_date_direct.group(0)).strip()
        add_field({
            "rule_id": "LMPC_R6_1_D",
            "field": "Date of Manufacture/Packing",
            "verdict": "pass",
            "evidence": ev
        })
    else:
        date_prefix_match = re.search(
            r'\b(?:DATE\s*OF\s*(?:PACKAGING|PACKING|MFG|MANUFACTURE)|MFG\.?\s*DATE|MFD\.?\s*DATE|MFD\.?\s*ON|MFG\.?\s*ON|PACKED\s*ON|PKD\.?\s*ON|PACKED|MFD|PKD)\b',
            text
        )
        candidates = []
        for m in re.finditer(r'\b(\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}|\d{1,2}[/.-]\d{2,4}|(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*\s*\d{2,4})\b', text):
            pre = text[max(0, m.start()-30):m.start()]
            if not re.search(r'(?:EXP|EXPIRY|BEST\s*BEFORE|USE\s*BY|CONSUME)', pre):
                candidates.append(m.group(0))
        
        if candidates and date_prefix_match:
            ev = f"{date_prefix_match.group(0)}: {candidates[0]}"
        elif candidates:
            ev = f"Date: {candidates[0]}"
        elif date_prefix_match:
            ev = date_prefix_match.group(0)
        else:
            ev = None

        if ev:
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
        r'\b(?:M\.?\s*R\.?\s*P\.?|MIRP|MAX(?:IMUM)?\.?\s*RETAIL\s*PRICE|RETAIL\s*PRICE)\b'
        r'(?:\s*\([^\)\n]{1,40}\))?[\s\n:\-\.]*(?:RS\.?|₹|INR)?[\s\n:\-\.]*'
        r'(\d{1,3}(?:,\d{3})*(?:\.\d{1,2})?|\d+(?:\.\d{1,2})?)'
        r'(?:\s*(?:/\-|\-|RS\.?|₹|INR))?',
        text
    )
    standalone_price = re.search(r'\b(?:RS\.?|₹|INR)\s*([1-9]\d{0,4}(?:,\d{3})*(?:\.\d{1,2})?)\b', text)
    if not standalone_price:
        standalone_price = re.search(r'\b([1-9]\d{0,4}(?:,\d{3})*(?:\.\d{1,2})?)\s*(?:RS\.?|₹|INR|/\-)\b', text)
    
    has_tax_phrase = bool(re.search(
        r'(?:INC?L?(?:USIVE)?\.?\s*(?:OF\s*)?(?:ALL\s*)?(?:TAXES?|TAX|GST)|INCL\.?OF\s*ALL\s*TAXES|IH\s*OF\s*AL\s*TAXES?|1G\s*OF\s*ALL\s*TAXES?|OF\s*ALL\s*TAXES|OF\s*AL\s*TAXES|OFALL|\bALL\s*TAXES\b|\bINCL\.?\s*TAXES\b|\bTAXES\s*INCL(?:UDED)?\b)',
        text
    ))
    has_side_ref = bool(re.search(r'\b(?:SEE\s+(?:SIDE|OTHER|BELOW|REVERSE|PANEL|CRIMP)|SIDE\s*PANEL)\b', text))

    if mrp_match:
        clean_mrp = re.sub(r'\s+', ' ', mrp_match.group(0)).strip()
        if has_tax_phrase or has_side_ref:
            add_field({
                "rule_id": "LMPC_R6_1_E",
                "field": "Maximum Retail Price (MRP)",
                "verdict": "pass",
                "evidence": f"{clean_mrp} (Inclusive of all taxes declared)"
            }, is_mandatory_for_small=True)
        else:
            add_field({
                "rule_id": "LMPC_R6_1_E",
                "field": "Maximum Retail Price (MRP)",
                "verdict": "fail",
                "evidence": f"Found '{clean_mrp}' but missing mandatory 'Inclusive of all taxes' statement."
            }, is_mandatory_for_small=True)
    elif standalone_price:
        price_text = re.sub(r'\s+', ' ', standalone_price.group(0)).strip()
        ref_text = " - Side Panel Reference" if has_side_ref else ""
        add_field({
            "rule_id": "LMPC_R6_1_E",
            "field": "Maximum Retail Price (MRP)",
            "verdict": "pass",
            "evidence": f"{price_text} (Retail Price declared{ref_text})"
        }, is_mandatory_for_small=True)
    else:
        mrp_label_only = re.search(r'\b(?:M\.?\s*R\.?\s*P\.?|MIRP|MAX(?:IMUM)?\.?\s*RETAIL\s*PRICE)\b', text)
        if mrp_label_only and (has_tax_phrase or has_side_ref):
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
    consumer_match = re.search(
        r'\b(?:CUSTOMER|CONSUMER)\s*(?:CARE|CELL|HELP|HELPLINE|SERVICE|SUPPORT|EXECUTIVE|FEEDBACK)\b[^\n]{0,50}'
        r'|\bTOLL\s*FREE(?:\s*HELPLINE|\s*NUMBER)?\s*[:\-]?\s*[\d\- ]{6,15}'
        r'|\bHELPLINE\s*[:\-]?\s*[\d\- ]{6,15}'
        r'|\bWECARE\b'
        r'|\b1800[- ]?\d{3}[- ]?\d{3,4}\b'
        r'|\b1800\d{6,8}\b'
        r'|\b0\d{2,4}[- ]?\d{6,8}\b'
        r'|\b\+?91[- ]?[6-9]\d{9}\b'
        r'|\b[6-9]\d{9}\b'
        r'|[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}',
        text
    )
    if consumer_match:
        ev_care = re.sub(r'\s+', ' ', consumer_match.group(0)).strip()
        add_field({
            "rule_id": "LMPC_R6_1_F",
            "field": "Consumer Care Contact",
            "verdict": "pass",
            "evidence": ev_care
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
    origin_match = re.search(
        r'\b(?:COUNTRY\s*OF\s*ORIGIN|MADE\s*IN|PRODUCT\s*OF|PRODUCED\s*IN|MANUFACTURED\s*IN|ORIGIN|COO)\s*[:\-]?\s*([^\n,;]{2,30})',
        text
    )
    domestic_address = re.search(
        r'\b(?:INDIA|MUMBAI|MAHARASHTRA|DELHI|NEW\s*DELHI|BANGALORE|BENGALURU|CHENNAI|KOLKATA|HYDERABAD|GUJARAT|PUNE|NAVI\s*MUMBAI|POWAI|PUNJAB|MOGA|HARYANA|GURGAON|GURUGRAM|NOIDA|UTTAR\s*PRADESH|UP|TAMIL\s*NADU|KARNATAKA|RAJASTHAN|KERALA|AHMEDABAD|SURAT|VADODARA|INDORE|MADHYA\s*PRADESH|MP|ANDHRA\s*PRADESH|AP|TELANGANA|GOA|HIMACHAL|BADDI|SOLAN|UTTARAKHAND|HARIDWAR|PANTNAGAR|ASSAM|KOLHAPUR|NAGPUR|THANE)\b',
        text
    )
    if origin_match:
        ev_origin = re.sub(r'\s+', ' ', origin_match.group(0)).strip()
        add_field({
            "rule_id": "LMPC_R6_1_G",
            "field": "Country of Origin",
            "verdict": "pass",
            "evidence": ev_origin
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
    exp_match = re.search(
        r'\b(?:BEST\s*BEFORE|USE\s*BY|USE\s*WITHIN|EXPIRY(?:\s*DATE)?|EXP\.?(?:\s*DATE)?|CONSUME\s*WITHIN|SHELF\s*LIFE|BEST\s*FOOD\s*EXPERIENCE)\b'
        r'[:\s\-\.]*([^\n,;]{2,40})',
        text
    )
    if not exp_match:
        dual_date = re.search(r'\b\d{2}[/.-]\d{2}[/.-]\d{2,4}\s*[-–/]\s*(\d{2}[/.-]\d{2}[/.-]\d{2,4})\b', text)
        if dual_date:
            exp_match = dual_date
    is_perishable = bool((commodity_header_match and commodity_header_match.group(1).strip() in FOOD_COMMODITY_NAMES) or (generic_name_match and generic_name_match.group(0).strip() in FOOD_COMMODITY_NAMES))
    if exp_match:
        ev_exp = re.sub(r'\s+', ' ', exp_match.group(0)).strip()
        add_field({
            "rule_id": "LMPC_R6_1_PROVISO",
            "field": "Best-Before / Use-By Date",
            "verdict": "pass",
            "evidence": ev_exp
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
    if not usp_match:
        usp_match = re.search(r'\b(?:RS\.?|₹)\s*(\d+(?:\.\d+)?\s*(?:PER|/)\s*(?:G|KG|ML|L|N))\b', text)
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

    fssai_info = extract_fssai_license(raw_ocr_text)
    eval_dict = {
        "score": score,
        "has_violation": has_violation,
        "fail_count": fail_count,
        "fields": fields,
        "fssai": fssai_info,
    }
    eval_dict["statutory_liability"] = calculate_statutory_penalty(eval_dict)
    return eval_dict


def extract_fssai_license(raw_text: str) -> Dict[str, Any]:
    """Extract and validate 14-digit FSSAI License Number under Food Safety & Standards Act."""
    text = raw_text.upper() if raw_text else ""
    m = re.search(r'\b(?:FSSAI|LIC\.?\s*(?:NO\.?)?|LICENCE\s*(?:NO\.?)?)\s*[:.-]?[^\d\n]{0,10}([12]\d{13})\b', text)
    if not m:
        m = re.search(r'\b([12]\d{13})\b', text)
    if not m:
        m_spaced = re.search(r'\b(?:FSSAI|LIC\.?\s*(?:NO\.?)?|LICENCE\s*(?:NO\.?)?)\s*[:.-]?[^\d\n]{0,10}([12](?:[\s-]?\d){13})\b', text)
        if m_spaced:
            digits_only = re.sub(r'[\s-]', '', m_spaced.group(1))
            if len(digits_only) == 14:
                lic_no = digits_only
                kind = "Central License" if lic_no.startswith("1") else "State / UT License"
                return {
                    "found": True,
                    "license_number": lic_no,
                    "kind": kind,
                    "verdict": "pass",
                    "evidence": f"FSSAI {kind}: {lic_no}"
                }
    if m:
        lic_no = m.group(1)
        kind = "Central License" if lic_no.startswith("1") else "State / UT License"
        return {
            "found": True,
            "license_number": lic_no,
            "kind": kind,
            "verdict": "pass",
            "evidence": f"FSSAI {kind}: {lic_no}"
        }
    return {
        "found": False,
        "license_number": None,
        "kind": None,
        "verdict": "review",
        "evidence": "No 14-digit FSSAI license detected (mandatory on food commodities)."
    }


# Statutory compounding penalty schedule per infraction type under Legal Metrology Act, 2009 & Rule 32 LMPC Rules:
INFRACTION_COMPOUNDING_FINES = {
    "LMPC_R6_1_E": 10000,       # MRP missing or without tax statement (Sec 36(2))
    "LMPC_R6_1_C": 10000,       # Net Quantity missing or non-standard pack (Sec 36(1) / Rule 5)
    "LMPC_R6_1_A": 5000,        # Manufacturer / Packer name and address missing
    "LMPC_R6_1_D": 5000,        # Month & Year of manufacture/packing missing
    "LMPC_R6_1_PROVISO": 5000,  # Best Before / Expiry missing
    "LMPC_R6_1_F": 2500,        # Consumer care details missing (phone/email)
    "LMPC_R6_1_G": 3000,        # Country of origin missing
    "LMPC_R6_1_B": 3000,        # Generic commodity name missing
    "LMPC_USP": 2000,           # Unit sale price missing
    "LMPC_RULE9": 5000,         # Rule 9 numeral height violation
}


def calculate_statutory_penalty(compliance_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate statutory legal liability under Section 36 of Legal Metrology Act, 2009.
    Allocates fines strictly when infractions are present; if no violations exist,
    returns ₹0 allocated penalty (Zero Liability).
    """
    fail_fields = [f for f in compliance_result.get("fields", []) if f.get("verdict") == "fail"]
    fail_count = len(fail_fields)

    if fail_count == 0:
        return {
            "has_liability": False,
            "fail_count": 0,
            "allocated_fine": 0,
            "penalty_first_offense": 0,
            "penalty_second_offense": 0,
            "first_offense_fine": 0,
            "second_offense_fine": 0,
            "penalty_display": "₹0 (No Fine Allocated)",
            "subsequent_action": "Statutory requirements satisfied. Zero legal liability.",
            "applicable_sections": [],
            "violation_details": [],
            "statutory_infractions": [],
            "compounding_eligible": True,
            "compounding_applicable": True
        }

    # Itemize and compute fine proportionate to specific infractions
    itemized_violations = []
    total_calculated = 0
    for f in fail_fields:
        rule_id = f.get("rule_id", "LMPC_RULE")
        fine = INFRACTION_COMPOUNDING_FINES.get(rule_id, 2500)
        total_calculated += fine
        itemized_violations.append({
            "rule_id": rule_id,
            "field": f.get("field", "Declaration"),
            "reason": f.get("evidence", "Mandatory statutory declaration missing or non-compliant."),
            "allocated_fine": fine,
            "fine_formatted": f"₹{fine:,}"
        })

    # Capped at statutory ceiling for first offense under Section 36(1)
    allocated_fine = min(25000, total_calculated)
    first_offense_fine = 25000  # Statutory limit for first offense
    second_offense_fine = 50000 # Statutory limit for second offense

    sections = ["Section 36(1) Legal Metrology Act, 2009 (Penalty for non-standard packages)"]
    has_mrp_violation = any(f.get("rule_id") == "LMPC_R6_1_E" for f in fail_fields)
    has_usp_violation = any(f.get("rule_id") == "LMPC_USP" for f in fail_fields)
    if has_mrp_violation or has_usp_violation:
        sections.append("Section 36(2) Legal Metrology Act, 2009 (Sale of pre-packaged commodities exceeding MRP / price rules)")

    subsequent_action = "Fine up to ₹1,00,000 and/or imprisonment for term up to 1 year under Section 36(1)"
    statutory_infractions = [
        f"{v['field']}: {v['reason']} (Allocated Fine: ₹{v['allocated_fine']:,})"
        for v in itemized_violations
    ]

    return {
        "has_liability": True,
        "fail_count": fail_count,
        "allocated_fine": allocated_fine,
        "penalty_first_offense": first_offense_fine,
        "penalty_second_offense": second_offense_fine,
        "first_offense_fine": allocated_fine,
        "second_offense_fine": min(50000, allocated_fine * 2),
        "statutory_max_fine": first_offense_fine,
        "penalty_display": f"₹{allocated_fine:,} Allocated Fine ({fail_count} infraction{'s' if fail_count > 1 else ''})",
        "subsequent_action": subsequent_action,
        "applicable_sections": sections,
        "violation_details": itemized_violations,
        "statutory_infractions": statutory_infractions,
        "compounding_eligible": True,
        "compounding_applicable": True,
        "compounding_provision": "Section 48 Legal Metrology Act, 2009 (Compounding of Offences before filing in Court)"
    }


def evaluate_manual_override(
    manual_data: Dict[str, Any],
    existing_fields: Optional[List[Dict[str, Any]]] = None,
    raw_ocr_text: str = ""
) -> Dict[str, Any]:
    """
    Evaluates or merges inspector's manual declaration entries with existing OCR findings.
    Allows manual override/entry when OCR is unable to read or misses package text.
    """
    standard_rules = [
        {"rule_id": "LMPC_R6_1_A", "field": "Manufacturer / Packer / Importer"},
        {"rule_id": "LMPC_R6_1_B", "field": "Common or Generic Commodity Name"},
        {"rule_id": "LMPC_R6_1_C", "field": "Net Quantity"},
        {"rule_id": "LMPC_R6_1_D", "field": "Month & Year of Manufacture / Packing / Import"},
        {"rule_id": "LMPC_R6_1_E", "field": "Maximum Retail Price (MRP)"},
        {"rule_id": "LMPC_R6_1_F", "field": "Consumer Care Details"},
        {"rule_id": "LMPC_R6_1_G", "field": "Country of Origin"},
        {"rule_id": "LMPC_R6_1_PROVISO", "field": "Best Before / Expiry Date"},
    ]

    field_map = {}
    if existing_fields:
        for f in existing_fields:
            field_map[f.get("rule_id")] = dict(f)
    else:
        for sr in standard_rules:
            field_map[sr["rule_id"]] = {
                "rule_id": sr["rule_id"],
                "field": sr["field"],
                "verdict": "fail",
                "evidence": "Declaration not entered."
            }

    # 1. Manufacturer / Packer
    mfr = manual_data.get("manufacturer")
    if mfr is not None and str(mfr).strip():
        mfr_val = str(mfr).strip()
        field_map["LMPC_R6_1_A"] = {
            "rule_id": "LMPC_R6_1_A",
            "field": "Manufacturer / Packer / Importer",
            "verdict": "pass",
            "evidence": f"Declared Mfr/Packer: {mfr_val} [Manually Verified]"
        }

    # 2. Commodity Name
    comm = manual_data.get("commodity_name") or manual_data.get("product_name")
    if comm is not None and str(comm).strip() and str(comm).strip().lower() not in ["untitled scan", "manual commodity inspection"]:
        comm_val = str(comm).strip()
        field_map["LMPC_R6_1_B"] = {
            "rule_id": "LMPC_R6_1_B",
            "field": "Common or Generic Commodity Name",
            "verdict": "pass",
            "evidence": f"Declared Commodity: {comm_val} [Manually Verified]"
        }

    # 3. Net Quantity
    net_qty = manual_data.get("net_quantity")
    if net_qty is not None and str(net_qty).strip():
        qty_val = str(net_qty).strip()
        has_metric = bool(re.search(r'\b(?:g|kg|ml|l|ltr|g\.|kg\.|gm|gms|units|n|count)\b', qty_val, re.IGNORECASE))
        evidence_text = f"Declared Net Qty: {qty_val} [Manually Verified]" if has_metric else f"Declared Net Qty: {qty_val} (Check standard metric units) [Manually Verified]"
        field_map["LMPC_R6_1_C"] = {
            "rule_id": "LMPC_R6_1_C",
            "field": "Net Quantity",
            "verdict": "pass",
            "evidence": evidence_text
        }

    # 4. Month & Year of Mfg / Packing
    mfg = manual_data.get("mfg_date")
    if mfg is not None and str(mfg).strip():
        mfg_val = str(mfg).strip()
        field_map["LMPC_R6_1_D"] = {
            "rule_id": "LMPC_R6_1_D",
            "field": "Month & Year of Manufacture / Packing / Import",
            "verdict": "pass",
            "evidence": f"Declared Mfg/Packing Date: {mfg_val} [Manually Verified]"
        }

    # 5. Maximum Retail Price (MRP)
    mrp = manual_data.get("mrp")
    if mrp is not None and str(mrp).strip():
        mrp_val = str(mrp).strip()
        incl_taxes = manual_data.get("mrp_inclusive_taxes", True)
        if incl_taxes or "tax" in mrp_val.lower() or "incl" in mrp_val.lower():
            tax_str = " (Inclusive of all taxes declared)"
            v = "pass"
        else:
            tax_str = " [Warning: Missing statutory 'inclusive of all taxes']"
            v = "fail"
        field_map["LMPC_R6_1_E"] = {
            "rule_id": "LMPC_R6_1_E",
            "field": "Maximum Retail Price (MRP)",
            "verdict": v,
            "evidence": f"Declared MRP: {mrp_val}{tax_str} [Manually Verified]"
        }

    # 6. Consumer Care
    care = manual_data.get("consumer_care")
    if care is not None and str(care).strip():
        care_val = str(care).strip()
        field_map["LMPC_R6_1_F"] = {
            "rule_id": "LMPC_R6_1_F",
            "field": "Consumer Care Details",
            "verdict": "pass",
            "evidence": f"Declared Consumer Care: {care_val} [Manually Verified]"
        }

    # 7. Country of Origin
    origin = manual_data.get("country_of_origin")
    if origin is not None and str(origin).strip():
        origin_val = str(origin).strip()
        field_map["LMPC_R6_1_G"] = {
            "rule_id": "LMPC_R6_1_G",
            "field": "Country of Origin",
            "verdict": "pass",
            "evidence": f"Declared Country of Origin: {origin_val} [Manually Verified]"
        }

    # 8. Best Before / Expiry
    exp = manual_data.get("expiry_date")
    if exp is not None and str(exp).strip():
        exp_val = str(exp).strip()
        field_map["LMPC_R6_1_PROVISO"] = {
            "rule_id": "LMPC_R6_1_PROVISO",
            "field": "Best Before / Expiry Date",
            "verdict": "pass",
            "evidence": f"Declared Expiry / Best Before: {exp_val} [Manually Verified]"
        }

    # 9. Optional Unit Sale Price (USP)
    usp = manual_data.get("unit_sale_price")
    if usp is not None and str(usp).strip():
        usp_val = str(usp).strip()
        field_map["LMPC_USP"] = {
            "rule_id": "LMPC_USP",
            "field": "Unit Sale Price (USP)",
            "verdict": "pass",
            "evidence": f"Declared USP: {usp_val} [Manually Verified]"
        }

    # Standard order
    final_fields = []
    for sr in standard_rules:
        if sr["rule_id"] in field_map:
            final_fields.append(field_map[sr["rule_id"]])
    for r_id, f_obj in field_map.items():
        if r_id not in [sr["rule_id"] for sr in standard_rules]:
            final_fields.append(f_obj)

    pass_count = sum(1 for f in final_fields if f["verdict"] == "pass")
    fail_count = sum(1 for f in final_fields if f["verdict"] == "fail")
    total_rules = len(final_fields)
    score = int((pass_count / total_rules) * 100) if total_rules > 0 else 0
    has_violation = fail_count > 0

    # FSSAI manual extraction/check
    fssai_lic = manual_data.get("fssai_license")
    if fssai_lic and str(fssai_lic).strip():
        lic_clean = re.sub(r'\D', '', str(fssai_lic).strip())
        if len(lic_clean) == 14:
            kind = "Central License" if lic_clean.startswith("1") else "State / UT License"
            fssai_info = {
                "found": True,
                "license_number": lic_clean,
                "kind": kind,
                "verdict": "pass",
                "evidence": f"FSSAI {kind}: {lic_clean} [Manually Verified]"
            }
        else:
            fssai_info = {
                "found": False,
                "license_number": lic_clean,
                "kind": None,
                "verdict": "fail",
                "evidence": f"Invalid FSSAI License: {lic_clean} (Must be exactly 14 numeric digits)"
            }
    else:
        fssai_info = extract_fssai_license(raw_ocr_text)

    eval_dict = {
        "score": score,
        "has_violation": has_violation,
        "fail_count": fail_count,
        "fields": final_fields,
        "fssai": fssai_info,
    }
    eval_dict["statutory_liability"] = calculate_statutory_penalty(eval_dict)
    return eval_dict


def run_rule_engine(ocr_text: str) -> Dict[str, Any]:
    """Alias for evaluate_label_rules."""
    return evaluate_label_rules(ocr_text)


def score_and_verdict(results: Dict[str, Any]):
    """Extract score, has_violation, and fail_count from evaluation results."""
    return results["score"], results["has_violation"], results["fail_count"]
