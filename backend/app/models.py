import datetime

from sqlalchemy import Column, Integer, String, DateTime, Text, Float, Boolean, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default="officer")  # officer | admin
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class ScannedProduct(Base):
    __tablename__ = "scanned_products"

    id = Column(Integer, primary_key=True, index=True)
    image_path = Column(String, nullable=False)
    product_name = Column(String, nullable=True)
    raw_ocr_text = Column(Text, nullable=True)
    extracted_fields = Column(Text, nullable=True)  # JSON string
    overall_status = Column(String, default="PENDING")  # PASS | FAIL | PENDING
    scanned_by = Column(String, nullable=True)
    scanned_at = Column(DateTime, default=datetime.datetime.utcnow)

    violations = relationship("Violation", back_populates="product", cascade="all, delete-orphan")


class Violation(Base):
    __tablename__ = "violations"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("scanned_products.id"))
    rule_code = Column(String, nullable=False)
    declaration = Column(String, nullable=False)
    status = Column(String, nullable=False)  # MISSING | INVALID | FONT_TOO_SMALL
    detail = Column(Text, nullable=True)
    confidence = Column(Float, default=0.0)

    product = relationship("ScannedProduct", back_populates="violations")
