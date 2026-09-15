from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(String, unique=True, index=True, nullable=False)
    full_name = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    scans = relationship("Scan", back_populates="user", cascade="all, delete-orphan", foreign_keys="Scan.user_id")


class Scan(Base):
    __tablename__ = "scans"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    product_name = Column(String, default="Untitled scan")
    score = Column(Integer, default=0)
    has_violation = Column(Boolean, default=False)
    fail_count = Column(Integer, default=0)
    raw_ocr_text = Column(Text, default="")
    fields_json = Column(Text, default="[]")
    annotated_image = Column(Text, nullable=True, default=None)
    original_image = Column(Text, nullable=True, default=None)
    brand_name = Column(String, nullable=True, default=None)
    image_quality_json = Column(Text, nullable=True, default=None)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="scans", foreign_keys=[user_id])
