from sqlalchemy import Column, String, Text, DateTime, Boolean, Integer, JSON, ForeignKey, Float
from sqlalchemy.sql import func
from app.database import Base

class EventRecord(Base):
    """Stores the fully sanitized, masked event payload."""
    __tablename__ = "events"

    id = Column(String(64), primary_key=True)  # Event ID or raw body SHA-256
    source = Column(String(50), nullable=False, default="webhook")
    event_type = Column(String(50), nullable=False, default="generic")
    payload_masked = Column(JSON, nullable=False)
    synced_to_erp = Column(Boolean, default=False)
    erp_sync_attempts = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class PIIVault(Base):
    """
    Isolated vault table storing the cryptographic reversible mapping.
    Access to this table should be restricted by strict DB-level roles in production.
    """
    __tablename__ = "pii_vault"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(64), ForeignKey("events.id", ondelete="CASCADE"), index=True, nullable=False)
    pii_token = Column(String(64), unique=True, index=True, nullable=False)  # e.g., [PII_PHONE_3a8f1b2c]
    pii_type = Column(String(20), nullable=False)  # 'EMAIL' or 'PHONE'
    encrypted_value = Column(Text, nullable=False)  # Fernet AES-128-CBC + HMAC-SHA256
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class DeadLetterQueue(Base):
    """
    Stores events that failed terminal delivery (e.g. ERP outages after retries).
    Provides visibility and operational replay capability.
    """
    __tablename__ = "dead_letter_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(64), index=True, nullable=False)
    destination = Column(String(50), nullable=False)  # e.g. "ERP_SYNC"
    error_reason = Column(Text, nullable=False)
    attempts = Column(Integer, nullable=False, default=0)
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class AIReviewQueue(Base):
    """
    Stores AI-generated intent classifications and suggested replies.
    Requires human supervisor approval before any communication is dispatched.
    """
    __tablename__ = "ai_reviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(64), ForeignKey("events.id", ondelete="CASCADE"), index=True, nullable=False)
    intent = Column(String(50), nullable=False)  # booking_request, complaint, status_query, other
    suggested_reply = Column(Text, nullable=False)
    model_name = Column(String(50), nullable=False)
    latency_ms = Column(Float, nullable=False)
    tokens_used = Column(Integer, nullable=False, default=0)
    status = Column(String(30), nullable=False, default="PENDING_HUMAN_REVIEW")
    created_at = Column(DateTime(timezone=True), server_default=func.now())