"""
Provider Credentials model
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base


class ProviderCredential(Base):
    """Provider credentials model for storing API keys"""
    __tablename__ = "provider_credentials"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    provider = Column(String(50), nullable=False)  # openai, anthropic, elevenlabs, etc.
    credentials = Column(JSONB, nullable=False)  # Encrypted in service layer
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization = relationship("Organization", back_populates="credentials")

    # Unique constraint on organization + provider
    __table_args__ = (
        {"extend_existing": True},
    )
