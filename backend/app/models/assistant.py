"""
Assistant model
"""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Float, Integer, Text, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import enum

from app.core.database import Base


class ModelProvider(str, enum.Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"
    AZURE = "azure"
    GROQ = "groq"
    TOGETHER = "together"


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


class TranscriberProvider(str, enum.Enum):
    DEEPGRAM = "deepgram"
    AZURE = "azure"
    GOOGLE = "google"
    ASSEMBLYAI = "assemblyai"
    OPENAI = "openai"


class FirstMessageMode(str, enum.Enum):
    ASSISTANT_SPEAKS_FIRST = "assistant-speaks-first"
    USER_SPEAKS_FIRST = "user-speaks-first"
    ASSISTANT_WAITS = "assistant-waits"


class Assistant(Base):
    """Assistant model for voice AI agents"""
    __tablename__ = "assistants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False)
    name = Column(String(255), nullable=False)

    # Model Configuration
    model_provider = Column(Enum(ModelProvider), nullable=False, default=ModelProvider.ANTHROPIC)
    model_name = Column(String(100), nullable=False, default="claude-sonnet-4-20250514")
    system_prompt = Column(Text)
    first_message = Column(Text)
    first_message_mode = Column(Enum(FirstMessageMode), default=FirstMessageMode.ASSISTANT_SPEAKS_FIRST)
    temperature = Column(Float, default=0.7)
    max_tokens = Column(Integer, default=1024)

    # Voice Configuration
    voice_provider = Column(Enum(VoiceProvider), default=VoiceProvider.ELEVENLABS)
    voice_id = Column(String(255))
    voice_settings = Column(JSONB, default={})

    # Transcriber Configuration
    transcriber_provider = Column(Enum(TranscriberProvider), default=TranscriberProvider.DEEPGRAM)
    transcriber_language = Column(String(20), default="ar-SA")
    transcriber_settings = Column(JSONB, default={})

    # Tools - array of tool IDs
    tools = Column(JSONB, default=[])

    # Analysis
    summary_prompt = Column(Text)
    success_evaluation_prompt = Column(Text)
    structured_data_schema = Column(JSONB, default={})

    # Advanced Settings
    advanced_settings = Column(JSONB, default={})

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    organization = relationship("Organization", back_populates="assistants")
    calls = relationship("Call", back_populates="assistant")
