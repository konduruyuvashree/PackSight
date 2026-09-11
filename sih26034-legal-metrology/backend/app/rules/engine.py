"""
Deterministic compliance rule engine.

Deliberately NOT ML-based: for an enforcement/legal tool, every PASS/FAIL
must be traceable to a specific rule and a specific piece of extracted text.
This is what makes the tool defensible in front of evaluators (and, in a
real deployment, defensible as evidence).
"""
import json
import re
from dataclasses import dataclass
from pathlib import Path

from app.ocr.extractor import ExtractedFields

RULESET_PATH = Path(__file__).parent / "ruleset.json"


@dataclass
class RuleViolation:
    rule_code: str
    declaration: str
    status: str  # MISSING | INVALID | FONT_TOO_SMALL | INFO
    detail: str
    confidence: float


def load_ruleset() -> dict:
    with open(RULESET_PATH) as f:
        return json.load(f)


def check_compliance(fields: ExtractedFields, ocr_confidence: float = 0.8) -> list[RuleViolation]:
    ruleset = load_ruleset()
    violations: list[RuleViolation] = []

    for decl in ruleset["declarations"]:
        field_value = getattr(fields, decl["field"], None)

        if not field_value:
            if decl["required"]:
                violations.append(
                    RuleViolation(
                        rule_code=decl["code"],
                        declaration=decl["name"],
                        status="MISSING",
                        detail=f"'{decl['name']}' was not detected on the label.",
                        confidence=ocr_confidence,
                    )
                )
            continue

        if decl.get("min_length") and len(field_value) < decl["min_length"]:
            violations.append(
                RuleViolation(
                    rule_code=decl["code"],
                    declaration=decl["name"],
                    status="INVALID",
                    detail=f"'{decl['name']}' detected but too short/incomplete: '{field_value}'.",
                    confidence=ocr_confidence,
                )
            )

        if decl["code"] == "R6_NET_QUANTITY":
            unit_ok = any(u in field_value.lower() for u in decl["valid_units"])
            if not unit_ok:
                violations.append(
                    RuleViolation(
                        rule_code=decl["code"],
                        declaration=decl["name"],
                        status="INVALID",
                        detail=f"Net quantity unit not recognized: '{field_value}'.",
                        confidence=ocr_confidence,
                    )
                )

        if decl["code"] == "R6_MRP" and decl.get("require_incl_tax_wording"):
            if "incl" not in field_value.lower():
                violations.append(
                    RuleViolation(
                        rule_code=decl["code"],
                        declaration=decl["name"],
                        status="INVALID",
                        detail="MRP found but missing required 'inclusive of all taxes' wording.",
                        confidence=ocr_confidence,
                    )
                )

    return violations


def check_font_size(word_heights_px: list[float], dpi: float, net_qty_value: float, ruleset: dict | None = None) -> RuleViolation | None:
    """
    Approximate font-size compliance check.

    Converts detected text bounding-box heights (pixels) to millimetres using
    an estimated DPI, then compares against the slab thresholds in
    ruleset.json. DPI must be estimated (e.g. via a reference object in
    frame, or a fixed calibration assumption for a phone camera at a known
    distance) — this is flagged as an approximation, not a certified
    measurement, and should be presented to users as such.
    """
    if not word_heights_px:
        return None

    ruleset = ruleset or load_ruleset()
    slabs = ruleset["font_size_slabs_mm"]

    applicable_slab = next(
        (s for s in slabs if s["max_net_qty_g_or_ml"] is None or net_qty_value <= s["max_net_qty_g_or_ml"]),
        slabs[-1],
    )
    required_mm = applicable_slab["min_height_mm"]

    mm_per_px = 25.4 / dpi
    max_height_mm = max(word_heights_px) * mm_per_px

    if max_height_mm < required_mm:
        return RuleViolation(
            rule_code="R6_FONT_SIZE",
            declaration="Font Size / Readability",
            status="FONT_TOO_SMALL",
            detail=(
                f"Estimated max text height {max_height_mm:.2f}mm is below the "
                f"required {required_mm}mm for this pack-size slab (approximate, DPI-estimated)."
            ),
            confidence=0.5,  # inherently lower confidence — DPI is estimated, not measured
        )
    return None


def overall_status(violations: list[RuleViolation]) -> str:
    hard_fail_statuses = {"MISSING", "INVALID", "FONT_TOO_SMALL"}
    if any(v.status in hard_fail_statuses for v in violations):
        return "FAIL"
    return "PASS"
