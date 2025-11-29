"""
Voices routes
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from uuid import UUID

from app.core.database import get_db
from app.models.voice import Voice
from app.models.user import User
from app.api.deps import get_current_user

router = APIRouter()


class VoiceResponse(BaseModel):
    id: UUID
    provider: str
    voice_id: str
    name: str
    description: str = None
    preview_url: str = None
    accent: str = None
    gender: str = None
    language: str = None
    cost_per_minute: float
    latency_ms: int
    tags: list
    is_custom: bool

    class Config:
        from_attributes = True


# Mock voices data for different providers
MOCK_VOICES = [
    # ElevenLabs voices
    {"provider": "elevenlabs", "voice_id": "EXAVITQu4vr4xnSDxMaL", "name": "Sarah", "gender": "female", "language": "en-US", "accent": "American", "cost_per_minute": 0.18, "latency_ms": 350, "tags": ["conversational", "natural"]},
    {"provider": "elevenlabs", "voice_id": "pNInz6obpgDQGcFmaJgB", "name": "Adam", "gender": "male", "language": "en-US", "accent": "American", "cost_per_minute": 0.18, "latency_ms": 350, "tags": ["deep", "authoritative"]},
    {"provider": "elevenlabs", "voice_id": "yoZ06aMxZJJ28mfd3POQ", "name": "Sam", "gender": "male", "language": "ar-SA", "accent": "Arabic", "cost_per_minute": 0.18, "latency_ms": 380, "tags": ["arabic", "clear"]},
    # Azure voices
    {"provider": "azure", "voice_id": "ar-SA-HamedNeural", "name": "Hamed", "gender": "male", "language": "ar-SA", "accent": "Saudi", "cost_per_minute": 0.10, "latency_ms": 280, "tags": ["arabic", "professional"]},
    {"provider": "azure", "voice_id": "ar-SA-ZariyahNeural", "name": "Zariyah", "gender": "female", "language": "ar-SA", "accent": "Saudi", "cost_per_minute": 0.10, "latency_ms": 280, "tags": ["arabic", "warm"]},
    {"provider": "azure", "voice_id": "en-US-JennyNeural", "name": "Jenny", "gender": "female", "language": "en-US", "accent": "American", "cost_per_minute": 0.10, "latency_ms": 250, "tags": ["friendly", "clear"]},
    # Deepgram voices
    {"provider": "deepgram", "voice_id": "aura-asteria-en", "name": "Asteria", "gender": "female", "language": "en-US", "accent": "American", "cost_per_minute": 0.08, "latency_ms": 200, "tags": ["fast", "natural"]},
    {"provider": "deepgram", "voice_id": "aura-zeus-en", "name": "Zeus", "gender": "male", "language": "en-US", "accent": "American", "cost_per_minute": 0.08, "latency_ms": 200, "tags": ["fast", "deep"]},
]


@router.get("", response_model=List[VoiceResponse])
async def list_voices(
    provider: Optional[str] = None,
    language: Optional[str] = None,
    gender: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all available voices"""
    # Query database for custom voices
    query = select(Voice)
    if provider:
        query = query.where(Voice.provider == provider)
    if language:
        query = query.where(Voice.language == language)
    if gender:
        query = query.where(Voice.gender == gender)

    result = await db.execute(query)
    db_voices = result.scalars().all()

    # Combine with mock voices (filter mock voices)
    filtered_mocks = MOCK_VOICES
    if provider:
        filtered_mocks = [v for v in filtered_mocks if v["provider"] == provider]
    if language:
        filtered_mocks = [v for v in filtered_mocks if v["language"] == language]
    if gender:
        filtered_mocks = [v for v in filtered_mocks if v["gender"] == gender]

    # Convert mock voices to response format
    import uuid
    voices = []
    for v in filtered_mocks:
        voices.append(VoiceResponse(
            id=uuid.uuid5(uuid.NAMESPACE_DNS, f"{v['provider']}-{v['voice_id']}"),
            provider=v["provider"],
            voice_id=v["voice_id"],
            name=v["name"],
            gender=v["gender"],
            language=v["language"],
            accent=v.get("accent"),
            cost_per_minute=v["cost_per_minute"],
            latency_ms=v["latency_ms"],
            tags=v.get("tags", []),
            is_custom=False,
        ))

    # Add custom voices from DB
    for v in db_voices:
        voices.append(VoiceResponse.model_validate(v))

    return voices


@router.get("/{provider}", response_model=List[VoiceResponse])
async def list_voices_by_provider(
    provider: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List voices for a specific provider"""
    return await list_voices(provider=provider, current_user=current_user, db=db)


@router.post("/sync")
async def sync_voices(
    provider: str = Query(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Sync voices from a provider"""
    # TODO: Implement actual voice syncing from providers
    return {"count": 0, "message": f"Synced voices from {provider}"}
