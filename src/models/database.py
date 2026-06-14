"""SQLAlchemy ORM models and engine/session factory."""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from src.config.settings import settings

engine = create_engine(settings.POSTGRES_URL, pool_pre_ping=True, pool_size=5)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a DB session and ensures cleanup."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── ORM Models ───────────────────────────────────────────────────────────────

class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(String(64), primary_key=True)
    name = Column(String(256), nullable=False)
    advertiser = Column(String(256), nullable=True)
    status = Column(String(32), default="active")
    budget = Column(Float, default=0.0)
    spend = Column(Float, default=0.0)
    impressions = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    conversions = Column(Integer, default=0)
    start_date = Column(DateTime, nullable=True)
    end_date = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DeliveryLog(Base):
    __tablename__ = "delivery_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    campaign_id = Column(String(64), nullable=False, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    impressions = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    spend = Column(Float, default=0.0)
    publisher = Column(String(256), nullable=True)
    domain = Column(String(512), nullable=True)
    geo = Column(String(64), nullable=True)
    device = Column(String(64), nullable=True)
    fraud_score = Column(Float, default=0.0)
    raw_payload = Column(Text, nullable=True)


class InventoryMetadata(Base):
    __tablename__ = "inventory_metadata"

    id = Column(String(64), primary_key=True)
    publisher = Column(String(256), nullable=False)
    domain = Column(String(512), nullable=True)
    ad_format = Column(String(64), default="display")
    floor_price = Column(Float, default=0.0)
    viewability_rate = Column(Float, default=0.0)
    brand_safety_score = Column(Float, default=0.0)
    available_impressions = Column(Integer, default=0)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


def init_db() -> None:
    """Create all tables (idempotent)."""
    Base.metadata.create_all(bind=engine)
