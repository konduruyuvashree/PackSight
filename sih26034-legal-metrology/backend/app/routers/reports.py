from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app import models
from app.report.generator import generate_pdf_report

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/{product_id}/pdf")
def download_report(product_id: int, db: Session = Depends(get_db)):
    product = db.query(models.ScannedProduct).filter(models.ScannedProduct.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Scan not found")

    path = generate_pdf_report(
        product_id=product.id,
        product_name=product.product_name,
        overall_status=product.overall_status,
        violations=product.violations,
    )
    return FileResponse(path, media_type="application/pdf", filename=f"compliance_report_{product_id}.pdf")


@router.get("/summary/stats")
def compliance_stats(db: Session = Depends(get_db)):
    total = db.query(models.ScannedProduct).count()
    passed = db.query(models.ScannedProduct).filter(models.ScannedProduct.overall_status == "PASS").count()
    failed = db.query(models.ScannedProduct).filter(models.ScannedProduct.overall_status == "FAIL").count()
    return {"total_scanned": total, "passed": passed, "failed": failed}
