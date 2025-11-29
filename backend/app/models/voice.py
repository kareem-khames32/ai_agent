"""
Voice model
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Float, Integer, Boolean, Text, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
import enum

from app.core.database import Base


class VoiceProvider(str, enum.Enum):
    ELEVENLABS = "elevenlabs"
    AZURE = "azure"
    GOOGLE = "google"
    OPENAI = "openai"
    DEEPGRAM = "deepgram"
    CARTESIA = "cartesia"
    LMNT = "lmnt"
    RIME = "rime"
    PLAYHT = "playht"
    NEUPHONIC = "neuphonic"


class VoiceGender(str, enum.Enum):
    MALE = "male"
    FEMALE = "female"
    NEUTRAL = "neutral"


class Voice(Base):
    """Voice model for TTS voices"""
    __tablename__ = "voices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider = Column(Enum(VoiceProvider), nullable=False)
    voice_id = Column(String(255), nullable=False)  # Provider's voice ID
    name = Column(String(255), nullable=False)
    description = Column(Text)
    preview_url = Column(String(500))

    # Voice characteristics
    accent = Column(String(100))
    gender = Column(Enum(VoiceGender))
    language = Column(String(20))

    # Metrics
    cost_per_minute = Column(Float, default=0)
    latency_ms = Column(Integer, default=0)

    # Tags for search
    tags = Column(JSONB, default=[])

    # Custom voice
    is_custom = Column(Boolean, default=False)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    # Unique constraint on provider + voice_id
    __table_args__ = (
        {"extend_existing": True},
    )
