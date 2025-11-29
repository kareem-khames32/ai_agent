"""
Phone Number model
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import enum

from app.core.database import Base


class TelephonyProvider(str, enum.Enum):
    TWILIO = "twilio"
    VONAGE = "vonage"
    SIP = "sip"
    TELNYX = "telnyx"


class PhoneNumber(Base):
    """Phone number model for telephony"""
    __tablename__ = "phone_numbers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)

    number = Column(String(50), nullable=False)
    label = Column(String(255))
    provider = Column(Enum(TelephonyProvider), default=TelephonyProvider.TWILIO)

    # SIP configuration
    server_url = Column(String(500))
    timeout_seconds = Column(Integer, default=20)
    credentials = Column(JSONB, default={})  # Encrypted in service layer

    # Assignment
    assigned_assistant_id = Column(UUID(as_uuid=True), ForeignKey("assistants.id"), nullable=True)
    assigned_squad_id = Column(UUID(as_uuid=True), ForeignKey("squads.id"), nullable=True)

    # Settings
    settings = Column(JSONB, default={
        "inbound_enabled": True,
        "outbound_enabled": True,
        "recording_enabled": True
    })

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    organization = relationship("Organization", back_populates="phone_numbers")
    assigned_assistant = relationship("Assistant", foreign_keys=[assigned_assistant_id])
    assigned_squad = relationship("Squad", foreign_keys=[assigned_squad_id])
    calls = relationship("Call", back_populates="phone_number")
