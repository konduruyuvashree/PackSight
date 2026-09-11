import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.ocr.extractor import extract_fields, ExtractedFields
from app.rules.engine import check_compliance, overall_status


def test_complete_label_passes():
    text = (
        "Mfd by ABC Foods Pvt Ltd, 123 MG Road, Bengaluru 560001 "
        "Net Wt: 500g "
        "MRP: Rs.150 incl. of all taxes "
        "Mfg Date: 05/2026 "
        "Consumer Care: 1800-123-4567, care@abcfoods.com"
    )
    fields = extract_fields(text)
    violations = check_compliance(fields)
    assert overall_status(violations) == "PASS", [v.detail for v in violations]


def test_missing_mrp_fails():
    text = (
        "Mfd by ABC Foods Pvt Ltd, 123 MG Road, Bengaluru 560001 "
        "Net Wt: 500g "
        "Mfg Date: 05/2026 "
        "Consumer Care: 1800-123-4567"
    )
    fields = extract_fields(text)
    violations = check_compliance(fields)
    assert overall_status(violations) == "FAIL"
    assert any(v.rule_code == "R6_MRP" for v in violations)


def test_mrp_without_incl_tax_wording_flagged():
    text = (
        "Mfd by ABC Foods Pvt Ltd, 123 MG Road, Bengaluru 560001 "
        "Net Wt: 500g "
        "MRP: Rs.150 "
        "Mfg Date: 05/2026 "
        "Consumer Care: 1800-123-4567"
    )
    fields = extract_fields(text)
    violations = check_compliance(fields)
    assert any(v.rule_code == "R6_MRP" and v.status == "INVALID" for v in violations)


def test_empty_label_flags_everything_required():
    fields = ExtractedFields()
    violations = check_compliance(fields)
    required_codes = {"R6_MANUFACTURER_ADDRESS", "R6_NET_QUANTITY", "R6_MRP", "R6_MFG_DATE", "R6_CONSUMER_CARE"}
    flagged_codes = {v.rule_code for v in violations}
    assert required_codes.issubset(flagged_codes)


if __name__ == "__main__":
    test_complete_label_passes()
    test_missing_mrp_fails()
    test_mrp_without_incl_tax_wording_flagged()
    test_empty_label_flags_everything_required()
    print("All tests passed.")
