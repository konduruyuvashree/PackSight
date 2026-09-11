import json
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app import models, schemas
from app.ocr.engine import extract_text, is_image_usable
from app.ocr.extractor import extract_fields
from app.rules.engine import check_compliance, overall_status

router = APIRouter(prefix="/scan", tags=["scan"])

UPLOAD_DIR = Path(__file__).parent.parent.parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)


@router.post("/", response_model=schemas.ScanResult)
async def scan_product(
    file: UploadFile = File(...),
    product_name: str = "",
    db: Session = Depends(get_db),
):
    # 1. Save upload
    ext = Path(file.filename).suffix or ".jpg"
    saved_path = UPLOAD_DIR / f"{uuid.uuid4().hex}{ext}"
    with open(saved_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # 2. Quality gate — reject unusable captures early
    usable, reason = is_image_usable(str(saved_path))
    if not usable:
        raise HTTPException(status_code=422, detail=f"Image rejected: {reason}")

    # 3. OCR
    raw_text, words = extract_text(str(saved_path))
    avg_conf = sum(w.confidence for w in words) / len(words) if words else 0.5

    # 4. Field extraction
    fields = extract_fields(raw_text)

    # 5. Rule check
    violations = check_compliance(fields, ocr_confidence=avg_conf)
    status_result = overall_status(violations)

    # 6. Persist
    product = models.ScannedProduct(
        image_path=str(saved_path),
        product_name=product_name or None,
        raw_ocr_text=raw_text,
        extracted_fields=json.dumps(fields.__dict__, default=str),
        overall_status=status_result,
    )
    db.add(product)
    db.flush()

    for v in violations:
        db.add(
            models.Violation(
                product_id=product.id,
                rule_code=v.rule_code,
                declaration=v.declaration,
                status=v.status,
                detail=v.detail,
                confidence=v.confidence,
            )
        )
    db.commit()
    db.refresh(product)

    return product


@router.get("/{product_id}", response_model=schemas.ScanResult)
def get_scan(product_id: int, db: Session = Depends(get_db)):
    product = db.query(models.ScannedProduct).filter(models.ScannedProduct.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Scan not found")
    return product


@router.get("/", response_model=list[schemas.ScanSummary])
def list_scans(skip: int = 0, limit: int = 50, status_filter: str | None = None, db: Session = Depends(get_db)):
    query = db.query(models.ScannedProduct)
    if status_filter:
        query = query.filter(models.ScannedProduct.overall_status == status_filter)
    products = query.order_by(models.ScannedProduct.scanned_at.desc()).offset(skip).limit(limit).all()
    return [
        schemas.ScanSummary(
            id=p.id,
            product_name=p.product_name,
            overall_status=p.overall_status,
            scanned_at=p.scanned_at,
            violation_count=len(p.violations),
        )
        for p in products
    ]
