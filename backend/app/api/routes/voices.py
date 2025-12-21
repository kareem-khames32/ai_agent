"""
Voices routes
"""
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from uuid import UUID
import httpx

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


class VoicePreviewRequest(BaseModel):
    text: str
    provider: str
    voice_id: str
    api_key: str
    region: Optional[str] = None


@router.post("/preview")
async def preview_voice(request: VoicePreviewRequest):
    """
    Preview a voice by synthesizing text to speech
    Returns audio/mpeg for playback
    """
    provider = request.provider.lower()

    try:
        if provider == "openai":
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.openai.com/v1/audio/speech",
                    headers={
                        "Authorization": f"Bearer {request.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "tts-1",
                        "input": request.text,
                        "voice": request.voice_id or "alloy",
                        "response_format": "mp3"
                    },
                    timeout=30.0
                )
                if response.status_code == 200:
                    return Response(content=response.content, media_type="audio/mpeg")
                else:
                    raise HTTPException(status_code=response.status_code, detail=response.text)

        elif provider == "elevenlabs":
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"https://api.elevenlabs.io/v1/text-to-speech/{request.voice_id}",
                    headers={
                        "xi-api-key": request.api_key,
                        "Content-Type": "application/json"
                    },
                    json={
                        "text": request.text,
                        "model_id": "eleven_multilingual_v2",
                        "voice_settings": {
                            "stability": 0.5,
                            "similarity_boost": 0.75
                        }
                    },
                    timeout=30.0
                )
                if response.status_code == 200:
                    return Response(content=response.content, media_type="audio/mpeg")
                else:
                    raise HTTPException(status_code=response.status_code, detail=response.text)

        elif provider == "azure":
            if not request.region:
                raise HTTPException(status_code=400, detail="Azure TTS requires region")

            # Get access token
            async with httpx.AsyncClient() as client:
                token_response = await client.post(
                    f"https://{request.region}.api.cognitive.microsoft.com/sts/v1.0/issueToken",
                    headers={"Ocp-Apim-Subscription-Key": request.api_key},
                    timeout=10.0
                )
                if token_response.status_code != 200:
                    raise HTTPException(status_code=401, detail="Failed to get Azure token")

                access_token = token_response.text

                # Synthesize speech
                ssml = f"""
                <speak version='1.0' xml:lang='ar-SA'>
                    <voice name='{request.voice_id}'>{request.text}</voice>
                </speak>
                """

                tts_response = await client.post(
                    f"https://{request.region}.tts.speech.microsoft.com/cognitiveservices/v1",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/ssml+xml",
                        "X-Microsoft-OutputFormat": "audio-16khz-128kbitrate-mono-mp3"
                    },
                    content=ssml,
                    timeout=30.0
                )

                if tts_response.status_code == 200:
                    return Response(content=tts_response.content, media_type="audio/mpeg")
                else:
                    raise HTTPException(status_code=tts_response.status_code, detail="Azure TTS failed")

        elif provider == "deepgram":
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.deepgram.com/v1/speak",
                    headers={
                        "Authorization": f"Token {request.api_key}",
                        "Content-Type": "application/json"
                    },
                    params={"model": request.voice_id or "aura-asteria-en"},
                    json={"text": request.text},
                    timeout=30.0
                )
                if response.status_code == 200:
                    return Response(content=response.content, media_type="audio/mpeg")
                else:
                    raise HTTPException(status_code=response.status_code, detail=response.text)

        else:
            raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")

    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="TTS request timed out")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
