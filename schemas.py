from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from datetime import datetime


class UserSignup(BaseModel):
    full_name: str
    user_id: str
    password: str


class UserLogin(BaseModel):
    user_id: str
    password: str


class AuthToken(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    full_name: str


class ScanField(BaseModel):
    rule_id: str
    field: str
    verdict: str
    evidence: str


class ScanResponse(BaseModel):
    id: int
    product_name: str
    score: int
    has_violation: bool
    fail_count: int
    raw_ocr_text: str
    created_at: datetime
    fields: List[ScanField]
    annotated_image: Optional[str] = None
    original_image: Optional[str] = None
    brand_name: Optional[str] = None
    image_quality: Optional[dict] = None
    extracted_entities: Optional[dict] = None
    barcode_data: Optional[list] = None
    veg_status: Optional[dict] = None
    fssai_info: Optional[dict] = None
    rule9_compliance: Optional[dict] = None
    legal_liability: Optional[dict] = None

    model_config = ConfigDict(from_attributes=True)


class StatSummary(BaseModel):
    total: int
    compliant: int
    violations: int
    avg_score: Optional[float] = None


class ManualScanRequest(BaseModel):
    product_name: str = "Manual Commodity Inspection"
    brand_name: Optional[str] = None
    net_quantity: Optional[str] = None
    mrp: Optional[str] = None
    mrp_inclusive_taxes: bool = True
    mfg_date: Optional[str] = None
    expiry_date: Optional[str] = None
    manufacturer: Optional[str] = None
    consumer_care: Optional[str] = None
    country_of_origin: Optional[str] = "India"
    unit_sale_price: Optional[str] = None
    fssai_license: Optional[str] = None
    veg_status: Optional[str] = None


class ManualScanOverride(BaseModel):
    product_name: Optional[str] = None
    brand_name: Optional[str] = None
    net_quantity: Optional[str] = None
    mrp: Optional[str] = None
    mrp_inclusive_taxes: Optional[bool] = True
    mfg_date: Optional[str] = None
    expiry_date: Optional[str] = None
    manufacturer: Optional[str] = None
    consumer_care: Optional[str] = None
    country_of_origin: Optional[str] = None
    unit_sale_price: Optional[str] = None
    fssai_license: Optional[str] = None
    veg_status: Optional[str] = None


# Aliases for backwards and alternative naming conventions
SignupRequest = UserSignup
LoginRequest = UserLogin
TokenResponse = AuthToken
FieldResult = ScanField
StatsResponse = StatSummary
