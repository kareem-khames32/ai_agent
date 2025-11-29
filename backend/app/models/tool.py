"""
Tool model
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean, Text, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import enum

from app.core.database import Base


class ToolType(str, enum.Enum):
    API_REQUEST = "api_request"
    FUNCTION = "function"
    HANDOFF = "handoff"
    END_CALL = "end_call"
    TRANSFER = "transfer"


class Tool(Base):
    """Tool model for assistant capabilities"""
    __tablename__ = "tools"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    name = Column(String(255), nullable=False)
    type = Column(Enum(ToolType), nullable=False)
    description = Column(Text)

    # Tool parameters schema (JSON Schema format)
    parameters = Column(JSONB, default=[])

    # For API request tools
    server_url = Column(String(500))
    headers = Column(JSONB, default={})

    # Options
    is_async = Column(Boolean, default=False)
    is_strict = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    organization = relationship("Organization", back_populates="tools")
