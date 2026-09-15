from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

SQLALCHEMY_DATABASE_URL = "sqlite:///./packsight.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def save_scan_result(result: dict) -> None:
    """Save a scan result dict to the SQLite database."""
    import json
    try:
        import models
        db = SessionLocal()
        try:
            prod_name = result.get("product") or result.get("brand_name") or "Product Scan"
            comp = result.get("compliance", {})
            score_val = int(round(comp.get("compliance_rate_percent", 0)))
            has_viol = comp.get("overall_status") != "COMPLIANT"
            fail_cnt = len(comp.get("missing_mandatory_fields", []))
            
            # Serialize fields for database
            fields_json = json.dumps(result.get("fields", {}))
            
            scan = models.Scan(
                product_name=prod_name,
                score=score_val,
                has_violation=has_viol,
                fail_count=fail_cnt,
                raw_ocr_text=json.dumps(result.get("fields", {})),
                fields_json=fields_json,
                brand_name=result.get("brand_name"),
            )
            db.add(scan)
            db.commit()
        finally:
            db.close()
    except Exception as err:
        # Graceful fallback or ignore if tables not yet migrated
        pass

