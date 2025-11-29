"""
Assistant schemas
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field


class VoiceSettings(BaseModel):
    """Voice settings schema"""
    stability: Optional[float] = None
    similarity_boost: Optional[float] = None
    style: Optional[float] = None
    speed: Optional[float] = 1.0
    pitch: Optional[float] = 1.0


class TranscriberSettings(BaseModel):
    """Transcriber settings schema"""
    timeout_ms: Optional[int] = None
    endpointing_ms: Optional[int] = 500
    segmentation_strategy: Optional[str] = "default"
    smart_format: Optional[bool] = True
    vad_enabled: Optional[bool] = True


class AdvancedSettings(BaseModel):
    """Advanced assistant settings"""
    privacy_enabled: Optional[bool] = False
    hipaa_enabled: Optional[bool] = False
    pci_enabled: Optional[bool] = False
    voicemail_detection_enabled: Optional[bool] = True
    voicemail_message: Optional[str] = None
    call_timeout_seconds: Optional[int] = None
    silence_timeout_seconds: Optional[int] = 30
    max_duration_seconds: Optional[int] = 1800
    keypad_input_enabled: Optional[bool] = False
    background_sound: Optional[str] = None
    background_denoising_enabled: Optional[bool] = False


class AssistantBase(BaseModel):
    """Base assistant schema"""
    name: str = Field(..., min_length=1, max_length=255)

    # Model config
    model_provider: str = "anthropic"
    model_name: str = "claude-sonnet-4-20250514"
    system_prompt: Optional[str] = None
    first_message: Optional[str] = None
    first_message_mode: str = "assistant-speaks-first"
    temperature: float = Field(0.7, ge=0, le=2)
    max_tokens: int = Field(1024, ge=1, le=128000)

    # Voice config
    voice_provider: Optional[str] = "elevenlabs"
    voice_id: Optional[str] = None
    voice_settings: Optional[VoiceSettings] = None

    # Transcriber config
    transcriber_provider: str = "deepgram"
    transcriber_language: str = "ar-SA"
    transcriber_settings: Optional[TranscriberSettings] = None

    # Tools
    tools: List[str] = Field(default_factory=list)

    # Analysis
    summary_prompt: Optional[str] = None
    success_evaluation_prompt: Optional[str] = None
    structured_data_schema: Optional[Dict[str, Any]] = None

    # Advanced
    advanced_settings: Optional[AdvancedSettings] = None


class AssistantCreate(AssistantBase):
    """Create assistant schema"""
    pass


class AssistantUpdate(BaseModel):
    """Update assistant schema"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    model_provider: Optional[str] = None
    model_name: Optional[str] = None
    system_prompt: Optional[str] = None
    first_message: Optional[str] = None
    first_message_mode: Optional[str] = None
    temperature: Optional[float] = Field(None, ge=0, le=2)
    max_tokens: Optional[int] = Field(None, ge=1, le=128000)
    voice_provider: Optional[str] = None
    voice_id: Optional[str] = None
    voice_settings: Optional[VoiceSettings] = None
    transcriber_provider: Optional[str] = None
    transcriber_language: Optional[str] = None
    transcriber_settings: Optional[TranscriberSettings] = None
    tools: Optional[List[str]] = None
    summary_prompt: Optional[str] = None
    success_evaluation_prompt: Optional[str] = None
    structured_data_schema: Optional[Dict[str, Any]] = None
    advanced_settings: Optional[AdvancedSettings] = None


class AssistantResponse(AssistantBase):
    """Assistant response schema"""
    id: UUID
    organization_id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
