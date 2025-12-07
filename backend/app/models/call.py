"""
Call model
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Float, Text, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import enum

from app.core.database import Base


class CallType(str, enum.Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class CallStatus(str, enum.Enum):
    QUEUED = "queued"
    RINGING = "ringing"
    IN_PROGRESS = "in-progress"
    ENDED = "ended"
    FAILED = "failed"


class EndedReason(str, enum.Enum):
    CUSTOMER_ENDED = "customer-ended"
    ASSISTANT_ENDED = "assistant-ended"
    VOICEMAIL = "voicemail"
    TIMEOUT = "timeout"
    ERROR = "error"
    TRANSFER = "transfer"
    HANGUP = "hangup"
    SILENCE_TIMEOUT = "silence-timeout"
    MAX_DURATION = "max-duration"


class SuccessEvaluation(str, enum.Enum):
    SUCCESS = "success"
    FAILURE = "failure"
    UNKNOWN = "unknown"


class Call(Base):
    """Call model for tracking voice calls"""
    __tablename__ = "calls"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    assistant_id = Column(UUID(as_uuid=True), ForeignKey("assistants.id"), nullable=True)
    squad_id = Column(UUID(as_uuid=True), ForeignKey("squads.id"), nullable=True)

    # Call type and status
    type = Column(Enum(CallType), nullable=False)
    status = Column(Enum(CallStatus), nullable=False, default=CallStatus.QUEUED)

    # Phone numbers
    phone_number_id = Column(UUID(as_uuid=True), ForeignKey("phone_numbers.id"), nullable=True)
    customer_phone_number = Column(String(50))

    # Timing
    started_at = Column(DateTime)
    ended_at = Column(DateTime)
    duration_seconds = Column(Integer, default=0)

    # Outcome
    ended_reason = Column(Enum(EndedReason))
    success_evaluation = Column(Enum(SuccessEvaluation))
    score = Column(Float)

    # Content
    transcript = Column(JSONB, default=[])  # Array of {role, text, timestamp, duration_ms}
    messages = Column(JSONB, default=[])  # Full message history
    tool_calls = Column(JSONB, default=[])  # Tool call history
    recording_url = Column(String(500))

    # Cost tracking
    cost_breakdown = Column(JSONB, default={
        "llm": 0,
        "stt": 0,
        "tts": 0,
        "telephony": 0
    })
    total_cost = Column(Float, default=0)

    # Analysis results
    summary = Column(Text)
    structured_data = Column(JSONB)

    # Call metadata (named call_metadata to avoid SQLAlchemy reserved name conflict)
    call_metadata = Column(JSONB)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    organization = relationship("Organization", back_populates="calls")
    assistant = relationship("Assistant", back_populates="calls")
    squad = relationship("Squad", back_populates="calls")
    phone_number = relationship("PhoneNumber", back_populates="calls")
