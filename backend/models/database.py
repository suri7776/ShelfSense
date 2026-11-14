# backend/models/database.py
# Database setup using SQLite. Stores alerts, shelf history, and config.

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

DATABASE_URL = "sqlite:///./shelfsense.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Alert(Base):
    """Every alert fired by the system."""
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)
    product_class = Column(String, index=True)
    shelf_slot = Column(Integer, default=0)
    severity = Column(String)          # full / low / critical / empty
    facings_detected = Column(Integer)
    facings_expected = Column(Integer, default=0)
    estimated_total = Column(Integer, default=0)
    camera_id = Column(String, default="cam_001")
    timestamp = Column(DateTime, default=datetime.utcnow)
    resolved = Column(Boolean, default=False)


class ShelfState(Base):
    """A snapshot of detection results, saved every time /api/detect runs."""
    __tablename__ = "shelf_states"

    id = Column(Integer, primary_key=True, index=True)
    camera_id = Column(String, default="cam_001")
    product_detected = Column(String, index=True)
    facings_count = Column(Integer)
    fill_percentage = Column(Float)
    timestamp = Column(DateTime, default=datetime.utcnow)


class UploadRecord(Base):
    """
    One row per upload batch (one or more files processed together).
    `files` is a JSON-encoded list of
        {"filename": ..., "path": ..., "kind": "image"|"video", "class_counts": {...}}
    `batch_totals` is the JSON-encoded combined class_counts across all
    files in this batch (per-file totals summed for images, per-file max
    across sampled frames for videos).
    `mode` is "add" or "replace" - how this batch was merged into the
    current-stock snapshot (see services/stock_state.py).
    """
    __tablename__ = "upload_records"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    mode = Column(String, default="add")
    file_count = Column(Integer, default=0)
    files = Column(String, default="[]")          # JSON
    batch_totals = Column(String, default="{}")    # JSON


def create_tables():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
