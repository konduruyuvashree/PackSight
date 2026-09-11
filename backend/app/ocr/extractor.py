"""
Extracts structured declaration fields from raw OCR text.

Strategy: regex/keyword-anchor first (fast, deterministic, explainable —
important for an enforcement tool). An LLM-based fallback (e.g. Gemini)
can be plugged into `llm_fallback_extract` for messy/unstructured labels
where regex finds nothing.
"""
import re
from dataclasses import dataclass, field


@dataclass
class ExtractedFields:
    manufacturer_address: str | None = None
    net_quantity: str | None = None
    mrp: str | None = None
    mfg_date: str | None = None
    consumer_care: str | None = None
    country_of_origin: str | None = None
    raw_matches: dict = field(default_factory=dict)


NET_QTY_PATTERN = re.compile(
    r"(net\s*(?:qty|quantity|wt|weight)?\s*[:\-]?\s*)?(\d+(?:\.\d+)?)\s*(g|gm|kg|ml|l|litre|liter|pcs|piece|units?)\b",
    re.IGNORECASE,
)

MRP_PATTERN = re.compile(
    r"(mrp|maximum\s+retail\s+price)\s*[:\-]?\s*(?:rs\.?|₹|inr)?\s*(\d+(?:[.,]\d{1,2})?)",
    re.IGNORECASE,
)

MRP_INCL_TAX_PATTERN = re.compile(r"incl(?:usive|\.)?\s*of\s*all\s*tax", re.IGNORECASE)

DATE_PATTERN = re.compile(
    r"(?:mfg|manufactur(?:e|ed|ing)|pack(?:ed|ing)?|import(?:ed)?)\.?\s*(?:date|dt|on)?\s*[:\-]?\s*"
    r"(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}"  # DD/MM/YYYY
    r"|\d{1,2}[/\-.]\d{2,4}"               # MM/YYYY (month/year only — valid per Rules, 2011)
    r"|[A-Za-z]{3,9}\s*[’'`]?\s*\d{2,4}"   # "May 2026" / "May'26"
    r"|\d{1,2}\s*[A-Za-z]{3,9}\s*\d{2,4})",  # "05 May 2026"
    re.IGNORECASE,
)

CONSUMER_CARE_PATTERN = re.compile(
    r"(consumer\s*care|customer\s*care|for\s*complaints?)\s*[:\-]?\s*([\w\s,.\-@]+)",
    re.IGNORECASE,
)

ADDRESS_ANCHOR_PATTERN = re.compile(
    r"(mfd|manufactured|marketed|packed)\s*by\s*[:\-]?\s*([\w\s,.\-]+)",
    re.IGNORECASE,
)

COUNTRY_OF_ORIGIN_PATTERN = re.compile(
    r"country\s*of\s*origin\s*[:\-]?\s*([\w\s]+)", re.IGNORECASE
)


def extract_fields(raw_text: str) -> ExtractedFields:
    result = ExtractedFields()

    if m := NET_QTY_PATTERN.search(raw_text):
        result.net_quantity = f"{m.group(2)} {m.group(3)}"
        result.raw_matches["net_quantity"] = m.group(0)

    if m := MRP_PATTERN.search(raw_text):
        mrp_value = m.group(2)
        incl_tax = bool(MRP_INCL_TAX_PATTERN.search(raw_text))
        result.mrp = f"₹{mrp_value}" + (" (incl. of all taxes)" if incl_tax else "")
        result.raw_matches["mrp"] = m.group(0)
        result.raw_matches["mrp_incl_tax_wording_found"] = incl_tax

    if m := DATE_PATTERN.search(raw_text):
        result.mfg_date = m.group(1)
        result.raw_matches["mfg_date"] = m.group(0)

    if m := CONSUMER_CARE_PATTERN.search(raw_text):
        result.consumer_care = m.group(2).strip()[:150]
        result.raw_matches["consumer_care"] = m.group(0)

    if m := ADDRESS_ANCHOR_PATTERN.search(raw_text):
        result.manufacturer_address = m.group(2).strip()[:200]
        result.raw_matches["manufacturer_address"] = m.group(0)

    if m := COUNTRY_OF_ORIGIN_PATTERN.search(raw_text):
        result.country_of_origin = m.group(1).strip()[:60]
        result.raw_matches["country_of_origin"] = m.group(0)

    return result


def llm_fallback_extract(raw_text: str) -> ExtractedFields:
    """
    Placeholder for an LLM-based extraction fallback (e.g. Gemini structured
    JSON output) for labels where the regex pass finds too little.

    Wire this up to your chosen LLM API — prompt it to return the same
    fields as ExtractedFields in JSON, then parse into this dataclass.
    Left unimplemented here to avoid embedding API keys / vendor lock-in
    in the scaffold.
    """
    raise NotImplementedError(
        "Plug in your LLM extraction call here (e.g. Gemini/OpenAI structured output)."
    )
