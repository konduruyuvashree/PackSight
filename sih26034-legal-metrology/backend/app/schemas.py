import datetime
from typing import Optional

from pydantic import BaseModel


class ViolationOut(BaseModel):
    rule_code: str
    declaration: str
    status: str
    detail: Optional[str] = None
    confidence: float

    class Config:
        from_attributes = True


class ScanResult(BaseModel):
    id: int
    product_name: Optional[str] = None
    overall_status: str
    scanned_at: datetime.datetime
    violations: list[ViolationOut] = []

    class Config:
        from_attributes = True


class ScanSummary(BaseModel):
    id: int
    product_name: Optional[str] = None
    overall_status: str
    scanned_at: datetime.datetime
    violation_count: int

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "officer"
