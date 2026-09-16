import os
import sys
import io
import json
import numpy as np
import cv2
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import app
from database import Base, engine
import models
import scanner
import ocr_rules
import report_generator

client = TestClient(app)

def create_synthetic_label_image(text: str = "SAMPLE PACK") -> bytes:
    img = np.ones((600, 600, 3), dtype=np.uint8) * 255
    cv2.rectangle(img, (50, 50), (110, 110), (34, 139, 34), 3)
    cv2.circle(img, (80, 80), 18, (34, 139, 34), -1)
    
    y = 160
    for line in text.split("\n"):
        cv2.putText(img, line, (40, y), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
        y += 40
        
    _, buf = cv2.imencode(".png", img)
    return buf.tobytes()

def test_fssai_extractor():
    text = "Mfd by Acme Foods Lic No. 10012063000064 New Delhi"
    res = ocr_rules.extract_fssai_license(text)
    assert res["found"] is True
    assert res["license_number"] == "10012063000064"
    assert "Central" in res["kind"]
    assert res["verdict"] == "pass"

def test_statutory_penalty_calculator():
    clean_eval = {
        "fields": [
            {"field": "MRP", "verdict": "pass"},
            {"field": "Net Qty", "verdict": "pass"},
        ]
    }
    clean_pen = ocr_rules.calculate_statutory_penalty(clean_eval)
    assert clean_pen["has_liability"] is False
    assert clean_pen["penalty_first_offense"] == 0

    viol_eval = {
        "fields": [
            {"rule_id": "LMPC_R6_1_E", "field": "MRP", "verdict": "fail", "evidence": "Missing MRP"},
            {"rule_id": "LMPC_R6_1_A", "field": "Manufacturer", "verdict": "fail", "evidence": "Missing MFR"},
        ]
    }
    viol_pen = ocr_rules.calculate_statutory_penalty(viol_eval)
    assert viol_pen["has_liability"] is True
    assert viol_pen["penalty_first_offense"] == 25000
    assert viol_pen["penalty_second_offense"] == 50000
    assert len(viol_pen["applicable_sections"]) >= 2
    assert "Section 36(1)" in viol_pen["applicable_sections"][0]

def test_veg_symbol_detector():
    img_bytes = create_synthetic_label_image("SAMPLE VEG PRODUCT")
    img = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)
    res = scanner.detect_veg_nonveg_symbol(img)
    assert res["status"] == "detected"
    assert res["symbol"] == "Vegetarian"
    assert res["color"] == "Green"

def test_rule9_numeral_height():
    img = np.ones((800, 600, 3), dtype=np.uint8) * 255
    ocr_box_data = {
        "text": ["NET", "WT", "500", "G", "MRP", "120"],
        "height": [20, 20, 32, 20, 20, 30]
    }
    res = scanner.verify_rule9_numeral_height(img, ocr_box_data)
    assert "pdp_area_cm2" in res
    assert "required_min_height_mm" in res
    assert "measured_numeral_height_mm" in res
    assert res["measured_numeral_height_mm"] > 0

def test_legal_show_cause_notice_pdf():
    violations = [
        {"rule_id": "LMPC_R6_1_E", "field": "MRP", "reason": "Missing MRP declaration"},
        {"rule_id": "LMPC_R6_1_C", "field": "Net Quantity", "reason": "Non-standard quantity"}
    ]
    liability = {
        "penalty_first_offense": 25000,
        "penalty_second_offense": 50000,
        "applicable_sections": ["Section 36(1)", "Section 36(2)"]
    }
    buf = report_generator.generate_legal_show_cause_notice_pdf(
        scan_id=42,
        product_name="Test Non-Compliant SKU",
        brand_name="Test Brand",
        violations=violations,
        liability_info=liability,
    )
    assert buf is not None
    pdf_bytes = buf.getvalue()
    assert len(pdf_bytes) > 2000
    assert pdf_bytes.startswith(b"%PDF")

def test_api_advancements_endpoints():
    user_id = f"adv_user_{os.getpid()}"
    signup_resp = client.post("/auth/signup", json={"full_name": "Adv Inspector", "user_id": user_id, "password": "securepassword123"})
    assert signup_resp.status_code == 200
    token = signup_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    img_bytes = create_synthetic_label_image("ACME BISCUITS 200g\nMRP RS 50 INCL ALL TAXES\nLIC NO. 10012063000064")
    scan_resp = client.post("/scans", headers=headers, files={"image": ("biscuit.png", img_bytes, "image/png")}, data={"product_name": "Acme Veg Biscuits"})
    assert scan_resp.status_code == 200
    scan_data = scan_resp.json()
    scan_id = scan_data["id"]
    assert "veg_status" in scan_data
    assert "fssai_info" in scan_data
    assert "legal_liability" in scan_data
    assert "rule9_compliance" in scan_data

    notice_resp = client.get(f"/scans/{scan_id}/legal-notice", headers=headers)
    assert notice_resp.status_code == 200
    assert notice_resp.headers["content-type"] == "application/pdf"
    assert len(notice_resp.content) > 2000

    csv_resp = client.get("/scans/export-csv", headers=headers)
    assert csv_resp.status_code == 200
    assert "text/csv" in csv_resp.headers["content-type"]
    csv_content = csv_resp.content.decode("utf-8")
    assert "Scan ID,Product Name,Brand" in csv_content
    assert "Acme Veg Biscuits" in csv_content

    batch_files = [
        ("images", ("sku1.png", img_bytes, "image/png")),
        ("images", ("sku2.png", img_bytes, "image/png")),
    ]
    batch_resp = client.post("/scans/batch", headers=headers, files=batch_files)
    assert batch_resp.status_code == 200
    batch_data = batch_resp.json()
    assert len(batch_data) == 2
    assert batch_data[0]["product_name"] == "Sku1"
    assert batch_data[1]["product_name"] == "Sku2"


def test_manual_entry_and_fine_allocation():
    user_id = f"manual_user_{os.getpid()}"
    signup_resp = client.post("/auth/signup", json={"full_name": "Manual Inspector", "user_id": user_id, "password": "securepassword123"})
    assert signup_resp.status_code == 200
    token = signup_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Image with missing fields (only shows brand name)
    img_bytes = create_synthetic_label_image("JUST A LOGO")
    scan_resp = client.post("/scans", headers=headers, files={"image": ("logo.png", img_bytes, "image/png")}, data={"product_name": "Unknown Product"})
    assert scan_resp.status_code == 200
    scan_data = scan_resp.json()
    scan_id = scan_data["id"]
    assert scan_data["has_violation"] is True
    assert scan_data["legal_liability"]["allocated_fine"] > 0
    assert scan_data["legal_liability"]["has_liability"] is True

    # 2. Manual override: Inspector enters all mandatory details
    override_payload = {
        "product_name": "Premium Almonds 250g",
        "brand_name": "NutriTreat",
        "net_quantity": "250 g",
        "mrp": "Rs. 250 (incl. of all taxes)",
        "mrp_inclusive_taxes": True,
        "mfg_date": "04/2026",
        "expiry_date": "12 Months from packing",
        "manufacturer": "NutriTreat Foods Pvt Ltd, GIDC Mumbai",
        "consumer_care": "care@nutritreat.com / 1800-11-2233",
        "country_of_origin": "India",
        "unit_sale_price": "Rs. 1.00 / g",
        "fssai_license": "10012063000064",
        "veg_status": "veg"
    }
    override_resp = client.put(f"/scans/{scan_id}/manual-override", headers=headers, json=override_payload)
    assert override_resp.status_code == 200
    updated_data = override_resp.json()
    assert updated_data["score"] == 100
    assert updated_data["has_violation"] is False
    assert updated_data["fail_count"] == 0
    # Crucial assertion: ZERO FINE ALLOCATED when all declarations satisfied
    assert updated_data["legal_liability"]["has_liability"] is False
    assert updated_data["legal_liability"]["allocated_fine"] == 0
    assert "No Fine Allocated" in updated_data["legal_liability"]["penalty_display"]

    # 3. Direct manual scan endpoint (no image required)
    manual_scan_payload = {
        "product_name": "Direct Manual Tea 500g",
        "brand_name": "Tata Tea",
        "net_quantity": "500 g",
        "mrp": "Rs. 180",
        "mrp_inclusive_taxes": True,
        "mfg_date": "01/2026",
        "expiry_date": "12 Months",
        "manufacturer": "Tata Consumer Products Ltd, Kolkata",
        "consumer_care": "1800-345-1720",
        "country_of_origin": "India",
        "unit_sale_price": "Rs. 0.36 / g",
        "fssai_license": "10014031001025",
        "veg_status": "veg"
    }
    direct_resp = client.post("/scans/manual", headers=headers, json=manual_scan_payload)
    assert direct_resp.status_code == 200
    direct_data = direct_resp.json()
    assert direct_data["score"] == 100
    assert direct_data["has_violation"] is False
    assert direct_data["legal_liability"]["allocated_fine"] == 0
    assert direct_data["legal_liability"]["has_liability"] is False

    print("\n[ALL ADVANCEMENTS & MANUAL ENTRY TESTS PASSED!]")

if __name__ == "__main__":
    test_fssai_extractor()
    print("[PASS] FSSAI Extractor test")
    test_statutory_penalty_calculator()
    print("[PASS] Statutory Penalty Calculator test")
    test_veg_symbol_detector()
    print("[PASS] Veg Symbol Detector test")
    test_rule9_numeral_height()
    print("[PASS] Rule 9 Numeral Height test")
    test_legal_show_cause_notice_pdf()
    print("[PASS] Legal Show-Cause Notice PDF Generator test")
    test_api_advancements_endpoints()
    print("[PASS] API Advancements Endpoints test")
    test_manual_entry_and_fine_allocation()
    print("[PASS] Manual Entry & Fine Allocation test")
