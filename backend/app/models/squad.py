"""
Squad model
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


class Squad(Base):
    """Squad model for multi-assistant workflows"""
    __tablename__ = "squads"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    name = Column(String(255), nullable=False)

    # Members configuration
    # Array of {assistant_id, handoff_tools, position, is_start_node, overrides}
    members = Column(JSONB, nullable=False, default=[])

    # Member overrides (per-member settings)
    member_overrides = Column(JSONB, default={})

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization = relationship("Organization", back_populates="squads")
    calls = relationship("Call", back_populates="squad")
