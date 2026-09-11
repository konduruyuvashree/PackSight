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

    model_config = ConfigDict(from_attributes=True)


class StatSummary(BaseModel):
    total: int
    compliant: int
    violations: int
    avg_score: Optional[float] = None


# Aliases for backwards and alternative naming conventions
SignupRequest = UserSignup
LoginRequest = UserLogin
TokenResponse = AuthToken
FieldResult = ScanField
StatsResponse = StatSummary
