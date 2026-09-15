import io
import json
import base64
from datetime import timedelta
from typing import List

from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from reportlab.lib.pagesizes import letter
from sqlalchemy.orm import Session

import models
import schemas
from database import engine, get_db
from auth_utils import (
    hash_password, verify_password, create_access_token, get_current_user,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)
from ocr_rules import (
    evaluate_label_rules, run_tesseract_ocr, extract_text_with_boxes,
    annotate_image, extract_text, run_rule_engine, score_and_verdict,
)
from report_generator import generate_compliance_pdf_report, generate_legal_show_cause_notice_pdf
from scanner import run_advanced_scan, assess_image_quality

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="PackSight API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"status": "ok", "service": "PackSight API"}


@app.get("/app", response_class=FileResponse)
def serve_webapp():
    return FileResponse("index.html")


# ---------------------------------------------------------------- auth ----

@app.post("/auth/signup", response_model=schemas.TokenResponse)
def signup(payload: schemas.SignupRequest, db: Session = Depends(get_db)):
    normalized_id = payload.user_id.strip().lower()
    if not normalized_id or not payload.full_name.strip() or not payload.password:
        raise HTTPException(status_code=400, detail="All fields are required.")
    if len(payload.password) < 4:
        raise HTTPException(status_code=400, detail="Password must be at least 4 characters.")

    existing = db.query(models.User).filter(models.User.user_id == normalized_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="That User ID is already taken.")

    user = models.User(
        user_id=normalized_id,
        full_name=payload.full_name.strip(),
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(
        {"sub": user.user_id}, expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return schemas.TokenResponse(
        access_token=token,
        token_type="bearer",
        full_name=user.full_name,
        user_id=user.user_id,
    )


@app.post("/auth/login", response_model=schemas.TokenResponse)
def login(payload: schemas.LoginRequest, db: Session = Depends(get_db)):
    normalized_id = payload.user_id.strip().lower()
    user = db.query(models.User).filter(models.User.user_id == normalized_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="No account found with that User ID.")
    if not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect password.")

    token = create_access_token(
        {"sub": user.user_id}, expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return schemas.TokenResponse(
        access_token=token,
        token_type="bearer",
        full_name=user.full_name,
        user_id=user.user_id,
    )


# ---------------------------------------------------------------- scans ----

def _scan_to_response(scan: models.Scan) -> schemas.ScanResponse:
    raw = json.loads(scan.fields_json) if scan.fields_json else []
    fields_list = raw["fields"] if isinstance(raw, dict) and "fields" in raw else raw
    quality = json.loads(scan.image_quality_json) if getattr(scan, "image_quality_json", None) else None
    adv_data = json.loads(scan.advancements_json) if getattr(scan, "advancements_json", None) else {}
    return schemas.ScanResponse(
        id=scan.id,
        product_name=scan.product_name,
        created_at=scan.created_at,
        score=scan.score,
        has_violation=scan.has_violation,
        fail_count=scan.fail_count,
        raw_ocr_text=scan.raw_ocr_text or "",
        fields=[schemas.FieldResult(**f) for f in fields_list],
        annotated_image=getattr(scan, "annotated_image", None),
        original_image=getattr(scan, "original_image", None),
        brand_name=getattr(scan, "brand_name", None),
        image_quality=quality,
        barcode_data=adv_data.get("barcode_data"),
        veg_status=adv_data.get("veg_status"),
        fssai_info=adv_data.get("fssai_info"),
        rule9_compliance=adv_data.get("rule9_compliance"),
        legal_liability=adv_data.get("legal_liability"),
    )


@app.post("/scans", response_model=schemas.ScanResponse)
async def create_scan(
    image: UploadFile = File(...),
    product_name: str = Form("Untitled scan"),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    image_bytes = await image.read()

    # 1. Advanced CV pipeline: Quality assessment, auto-orientation, multi-channel OCR
    barcode_data = []
    veg_status = None
    rule9_compliance = None
    try:
        scan_cv = run_advanced_scan(image_bytes)
        oriented_bytes = scan_cv["oriented_image_bytes"]
        ocr_text = scan_cv["raw_ocr_text"]
        box_data = scan_cv["ocr_box_data"]
        brand_name = scan_cv["brand_name"]
        quality_data = scan_cv["quality"]
        barcode_data = scan_cv.get("barcode_data", [])
        veg_status = scan_cv.get("veg_status")
        rule9_compliance = scan_cv.get("rule9_compliance")
    except Exception as cv_err:
        print(f"Advanced scanner fallback: {cv_err}")
        try:
            ocr_text, box_data = extract_text_with_boxes(image_bytes)
        except Exception:
            ocr_text = run_tesseract_ocr(image_bytes)
            box_data = {}
        oriented_bytes = image_bytes
        brand_name = "Packaged Commodity"
        quality_data = {"acceptable": True, "status": "Standard", "recommendations": []}

    # 2. Statutory Legal Metrology (LMPC 2011) compliance evaluation
    eval_result = evaluate_label_rules(ocr_text)
    fssai_info = eval_result.get("fssai")
    legal_liability = eval_result.get("statutory_liability")

    # 3. Generate annotated image with bounding boxes & rule tags
    annotated_base64 = None
    try:
        annotated_bytes = annotate_image(oriented_bytes, box_data, eval_result["fields"])
        if annotated_bytes:
            annotated_base64 = base64.b64encode(annotated_bytes).decode("utf-8")
    except Exception as e:
        print(f"Annotation failed: {e}")

    # Refine product name if default and brand detected
    final_product_name = product_name
    if (not product_name or product_name == "Untitled scan") and brand_name and brand_name != "Packaged Commodity":
        final_product_name = f"{brand_name} Package"

    original_base64 = None
    if oriented_bytes:
        try:
            original_base64 = base64.b64encode(oriented_bytes).decode("utf-8")
        except Exception:
            pass

    adv_json = json.dumps({
        "barcode_data": barcode_data,
        "veg_status": veg_status,
        "fssai_info": fssai_info,
        "rule9_compliance": rule9_compliance,
        "legal_liability": legal_liability,
    })

    scan = models.Scan(
        user_id=current_user.id,
        owner_id=current_user.id,
        product_name=final_product_name or "Untitled scan",
        score=eval_result["score"],
        has_violation=eval_result["has_violation"],
        fail_count=eval_result["fail_count"],
        raw_ocr_text=ocr_text,
        fields_json=json.dumps(eval_result["fields"]),
        annotated_image=annotated_base64,
        original_image=original_base64,
        brand_name=brand_name,
        image_quality_json=json.dumps(quality_data),
        advancements_json=adv_json,
    )
    db.add(scan)
    db.commit()
    db.refresh(scan)

    return _scan_to_response(scan)


@app.get("/scans", response_model=List[schemas.ScanResponse])
def list_scans(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    scans = (
        db.query(models.Scan)
        .filter((models.Scan.user_id == current_user.id) | (models.Scan.owner_id == current_user.id))
        .order_by(models.Scan.created_at.desc())
        .all()
    )
    return [_scan_to_response(s) for s in scans]


@app.get("/stats", response_model=schemas.StatsResponse)
def get_stats(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    scans = db.query(models.Scan).filter(
        (models.Scan.user_id == current_user.id) | (models.Scan.owner_id == current_user.id)
    ).all()
    total = len(scans)
    compliant = sum(1 for s in scans if not s.has_violation)
    violations = total - compliant
    avg_score = round(sum(s.score for s in scans) / total, 1) if total else None
    return schemas.StatsResponse(total=total, compliant=compliant, violations=violations, avg_score=avg_score)


@app.post("/scans/multi", response_model=schemas.ScanResponse)
async def create_multi_scan(
    product_name: str = Form("Untitled Product"),
    images: List[UploadFile] = File(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    combined_ocr_text = ""
    first_image_bytes = None
    first_box_data = {}

    brand_name = "Packaged Commodity"
    best_quality = {"acceptable": True, "status": "Standard", "recommendations": []}
    for i, img in enumerate(images):
        contents = await img.read()
        try:
            panel_cv = run_advanced_scan(contents)
            panel_text = panel_cv["raw_ocr_text"]
            if i == 0:
                first_image_bytes = panel_cv["oriented_image_bytes"]
                first_box_data = panel_cv["ocr_box_data"]
                best_quality = panel_cv["quality"]
                if panel_cv["brand_name"] != "Packaged Commodity":
                    brand_name = panel_cv["brand_name"]
            elif brand_name == "Packaged Commodity" and panel_cv["brand_name"] != "Packaged Commodity":
                brand_name = panel_cv["brand_name"]
        except Exception:
            if i == 0:
                first_image_bytes = contents
                try:
                    panel_text, first_box_data = extract_text_with_boxes(contents)
                except Exception:
                    panel_text = run_tesseract_ocr(contents)
            else:
                panel_text = run_tesseract_ocr(contents)

        combined_ocr_text += f"\n--- Panel ({img.filename}) ---\n" + panel_text

    eval_result = evaluate_label_rules(combined_ocr_text)

    annotated_base64 = None
    if first_image_bytes and first_box_data:
        try:
            annotated_bytes = annotate_image(first_image_bytes, first_box_data, eval_result["fields"])
            if annotated_bytes:
                annotated_base64 = base64.b64encode(annotated_bytes).decode("utf-8")
        except Exception as e:
            print(f"Multi annotation failed: {e}")

    final_product_name = product_name
    if (not product_name or product_name == "Untitled Product") and brand_name != "Packaged Commodity":
        final_product_name = f"{brand_name} Multi-Panel Package"

    original_base64 = None
    if first_image_bytes:
        try:
            original_base64 = base64.b64encode(first_image_bytes).decode("utf-8")
        except Exception:
            pass

    adv_json = json.dumps({
        "barcode_data": [],
        "veg_status": None,
        "fssai_info": eval_result.get("fssai"),
        "rule9_compliance": None,
        "legal_liability": eval_result.get("statutory_liability"),
    })

    db_scan = models.Scan(
        user_id=current_user.id,
        owner_id=current_user.id,
        product_name=final_product_name,
        score=eval_result["score"],
        has_violation=eval_result["has_violation"],
        fail_count=eval_result["fail_count"],
        raw_ocr_text=combined_ocr_text,
        fields_json=json.dumps(eval_result["fields"]),
        annotated_image=annotated_base64,
        original_image=original_base64,
        brand_name=brand_name,
        image_quality_json=json.dumps(best_quality),
        advancements_json=adv_json,
    )
    db.add(db_scan)
    db.commit()
    db.refresh(db_scan)

    return _scan_to_response(db_scan)


@app.get("/scans/{scan_id}/pdf")
async def download_scan_pdf(
    scan_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    scan = db.query(models.Scan).filter(
        models.Scan.id == scan_id,
        (models.Scan.user_id == current_user.id) | (models.Scan.owner_id == current_user.id),
    ).first()

    if not scan:
        raise HTTPException(status_code=404, detail="Scan record not found.")

    raw = json.loads(scan.fields_json) if scan.fields_json else []
    fields = raw["fields"] if isinstance(raw, dict) and "fields" in raw else raw

    buffer = generate_compliance_pdf_report(
        scan_id=scan.id,
        product_name=scan.product_name or "Packaged Commodity",
        score=scan.score,
        has_violation=scan.has_violation,
        fields=fields,
        created_at=scan.created_at,
        user_name=current_user.full_name or current_user.user_id,
        annotated_image_b64=getattr(scan, "annotated_image", None),
        brand_name=getattr(scan, "brand_name", None),
    )

    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=packsight_report_{scan_id}.pdf"},
    )


@app.get("/scans/{scan_id}/legal-notice")
def download_legal_notice(
    scan_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Download formal Legal Metrology Show-Cause Notice / Inspection Memorandum (PDF)."""
    scan = (
        db.query(models.Scan)
        .filter(models.Scan.id == scan_id)
        .filter((models.Scan.user_id == current_user.id) | (models.Scan.owner_id == current_user.id))
        .first()
    )
    if not scan:
        raise HTTPException(status_code=404, detail="Scan not found")

    adv_data = json.loads(scan.advancements_json) if getattr(scan, "advancements_json", None) else {}
    liability = adv_data.get("legal_liability") or {}
    violations = liability.get("violation_details", [])

    pdf_buffer = generate_legal_show_cause_notice_pdf(
        scan_id=scan.id,
        product_name=scan.product_name,
        brand_name=scan.brand_name,
        violations=violations,
        liability_info=liability,
        inspecting_officer=f"Inspector {current_user.full_name or current_user.user_id}",
        created_at=scan.created_at,
    )

    clean_filename = f"Legal_Notice_{scan.product_name.replace(' ', '_')}_{scan.id}.pdf"
    return StreamingResponse(
        pdf_buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{clean_filename}"'},
    )


@app.post("/scans/batch", response_model=List[schemas.ScanResponse])
async def create_batch_scans(
    images: List[UploadFile] = File(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Enterprise SKU Batch Inspection: Audits multiple packaging photos concurrently."""
    results = []
    for file in images:
        content = await file.read()
        if not content:
            continue
        p_name = file.filename.rsplit(".", 1)[0].replace("_", " ").title()

        barcode_data = []
        veg_status = None
        rule9_compliance = None
        try:
            scan_cv = run_advanced_scan(content)
            oriented_bytes = scan_cv["oriented_image_bytes"]
            ocr_text = scan_cv["raw_ocr_text"]
            box_data = scan_cv["ocr_box_data"]
            brand_name = scan_cv["brand_name"]
            quality_data = scan_cv["quality"]
            barcode_data = scan_cv.get("barcode_data", [])
            veg_status = scan_cv.get("veg_status")
            rule9_compliance = scan_cv.get("rule9_compliance")
        except Exception:
            ocr_text = run_tesseract_ocr(content)
            box_data = {}
            oriented_bytes = content
            brand_name = "Packaged Commodity"
            quality_data = {"acceptable": True, "status": "Standard", "recommendations": []}

        eval_result = evaluate_label_rules(ocr_text)
        fssai_info = eval_result.get("fssai")
        legal_liability = eval_result.get("statutory_liability")

        annotated_base64 = None
        try:
            annotated_bytes = annotate_image(oriented_bytes, box_data, eval_result["fields"])
            if annotated_bytes:
                annotated_base64 = base64.b64encode(annotated_bytes).decode("utf-8")
        except Exception:
            pass

        original_base64 = None
        try:
            original_base64 = base64.b64encode(oriented_bytes).decode("utf-8")
        except Exception:
            pass

        adv_json = json.dumps({
            "barcode_data": barcode_data,
            "veg_status": veg_status,
            "fssai_info": fssai_info,
            "rule9_compliance": rule9_compliance,
            "legal_liability": legal_liability,
        })

        scan = models.Scan(
            user_id=current_user.id,
            owner_id=current_user.id,
            product_name=p_name,
            score=eval_result["score"],
            has_violation=eval_result["has_violation"],
            fail_count=eval_result["fail_count"],
            raw_ocr_text=ocr_text,
            fields_json=json.dumps(eval_result["fields"]),
            annotated_image=annotated_base64,
            original_image=original_base64,
            brand_name=brand_name,
            image_quality_json=json.dumps(quality_data),
            advancements_json=adv_json,
        )
        db.add(scan)
        db.commit()
        db.refresh(scan)
        results.append(_scan_to_response(scan))

    return results


@app.get("/scans/export-csv")
def export_scans_csv(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Export comprehensive Legal Metrology compliance audit report as CSV."""
    import csv
    scans = (
        db.query(models.Scan)
        .filter((models.Scan.user_id == current_user.id) | (models.Scan.owner_id == current_user.id))
        .order_by(models.Scan.created_at.desc())
        .all()
    )
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Scan ID", "Product Name", "Brand", "Score", "Status",
        "Violations Count", "FSSAI License", "Barcode / GTIN", "Veg / Non-Veg",
        "Rule 9 Font Height", "Statutory Penalty Liability", "Date"
    ])
    for s in scans:
        adv = json.loads(s.advancements_json) if getattr(s, "advancements_json", None) else {}
        fssai_no = adv.get("fssai_info", {}).get("license_number") or "N/A"
        b_codes = ", ".join(b.get("code", "") for b in adv.get("barcode_data", [])) or "N/A"
        veg_sym = adv.get("veg_status", {}).get("symbol") or "N/A"
        rule9_h = f"{adv.get('rule9_compliance', {}).get('measured_numeral_height_mm', 'N/A')}mm"
        penalty = adv.get("legal_liability", {}).get("penalty_display") or "₹0"
        status_str = "COMPLIANT" if not s.has_violation else "NON-COMPLIANT"

        writer.writerow([
            s.id, s.product_name, s.brand_name or "N/A", f"{s.score}%",
            status_str, s.fail_count, fssai_no, b_codes, veg_sym,
            rule9_h, penalty, s.created_at.strftime("%Y-%m-%d %H:%M")
        ])

    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="PackSight_Audit_Report.csv"'}
    )
