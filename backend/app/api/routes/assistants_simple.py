"""
Simple Assistants API Routes
Uses SQLite storage - no PostgreSQL needed
"""
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.storage import assistants_store

router = APIRouter()


# === Pydantic Models ===

class VoiceSettings(BaseModel):
    """Voice configuration settings"""
    speed: Optional[float] = 1.0
    stability: Optional[float] = 0.5
    similarity_boost: Optional[float] = 0.75


class TranscriberSettings(BaseModel):
    """Transcriber configuration settings"""
    endpointing_ms: Optional[int] = 500
    punctuate: Optional[bool] = True
    interim_results: Optional[bool] = True


class StopSpeakingPlan(BaseModel):
    """Interruption/barge-in settings"""
    enable_interruption: Optional[bool] = True
    interruption_words: Optional[int] = 2
    cooldown_ms: Optional[int] = 150


class AssistantCreate(BaseModel):
    """Request model for creating an assistant"""
    name: str = Field(..., min_length=1, max_length=255)
    mode: Optional[str] = "pipeline"  # pipeline or realtime
    model_provider: Optional[str] = "openai"
    model_name: Optional[str] = "gpt-4o-mini"
    system_prompt: Optional[str] = ""
    first_message: Optional[str] = ""
    first_message_mode: Optional[str] = "assistant-speaks-first"
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 200
    voice_provider: Optional[str] = "openai"
    voice_id: Optional[str] = "alloy"
    voice_settings: Optional[VoiceSettings] = None
    transcriber_provider: Optional[str] = "deepgram"
    transcriber_language: Optional[str] = "ar"
    transcriber_settings: Optional[TranscriberSettings] = None
    stop_speaking_plan: Optional[StopSpeakingPlan] = None
    tools: Optional[List[str]] = []
    metadata: Optional[Dict[str, Any]] = {}


class AssistantUpdate(BaseModel):
    """Request model for updating an assistant"""
    name: Optional[str] = None
    mode: Optional[str] = None
    model_provider: Optional[str] = None
    model_name: Optional[str] = None
    system_prompt: Optional[str] = None
    first_message: Optional[str] = None
    first_message_mode: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    voice_provider: Optional[str] = None
    voice_id: Optional[str] = None
    voice_settings: Optional[VoiceSettings] = None
    transcriber_provider: Optional[str] = None
    transcriber_language: Optional[str] = None
    transcriber_settings: Optional[TranscriberSettings] = None
    stop_speaking_plan: Optional[StopSpeakingPlan] = None
    tools: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


# === API Endpoints ===

@router.get("")
async def list_assistants(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """
    List all assistants with pagination

    - **limit**: Maximum number of results (1-100, default 50)
    - **offset**: Number of results to skip (default 0)
    """
    return assistants_store.list(limit=limit, offset=offset)


@router.post("", status_code=201)
async def create_assistant(data: AssistantCreate):
    """
    Create a new voice AI assistant

    Configure the assistant with:
    - **name**: Display name
    - **mode**: "pipeline" (STT→LLM→TTS) or "realtime" (native speech API)
    - **model_provider**: openai, anthropic, google, groq, together
    - **model_name**: Model ID (e.g., gpt-4o-mini, claude-sonnet)
    - **voice_provider**: elevenlabs, openai, azure, google, cartesia
    - **voice_id**: Voice ID from the provider
    - **transcriber_provider**: deepgram, azure, openai, groq
    - **transcriber_language**: Language code (ar, en, etc.)
    """
    assistant_data = data.model_dump(exclude_none=True)

    # Convert nested models to dicts
    if data.voice_settings:
        assistant_data["voice_settings"] = data.voice_settings.model_dump()
    if data.transcriber_settings:
        assistant_data["transcriber_settings"] = data.transcriber_settings.model_dump()
    if data.stop_speaking_plan:
        assistant_data["stop_speaking_plan"] = data.stop_speaking_plan.model_dump()

    return assistants_store.create(assistant_data)


@router.get("/{assistant_id}")
async def get_assistant(assistant_id: str):
    """
    Get an assistant by ID

    Returns full assistant configuration including all settings.
    """
    assistant = assistants_store.get(assistant_id)
    if not assistant:
        raise HTTPException(status_code=404, detail="Assistant not found")
    return assistant


@router.patch("/{assistant_id}")
async def update_assistant(assistant_id: str, data: AssistantUpdate):
    """
    Update an existing assistant

    Only fields provided will be updated. All fields are optional.
    """
    update_data = data.model_dump(exclude_none=True)

    # Convert nested models to dicts
    if data.voice_settings:
        update_data["voice_settings"] = data.voice_settings.model_dump()
    if data.transcriber_settings:
        update_data["transcriber_settings"] = data.transcriber_settings.model_dump()
    if data.stop_speaking_plan:
        update_data["stop_speaking_plan"] = data.stop_speaking_plan.model_dump()

    assistant = assistants_store.update(assistant_id, update_data)
    if not assistant:
        raise HTTPException(status_code=404, detail="Assistant not found")
    return assistant


@router.put("/{assistant_id}")
async def replace_assistant(assistant_id: str, data: AssistantCreate):
    """
    Replace an assistant (full update)

    All fields will be replaced with the new values.
    """
    # Check if exists
    existing = assistants_store.get(assistant_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Assistant not found")

    # Delete and recreate
    assistants_store.delete(assistant_id)

    assistant_data = data.model_dump()
    assistant_data["id"] = assistant_id

    # Convert nested models to dicts
    if data.voice_settings:
        assistant_data["voice_settings"] = data.voice_settings.model_dump()
    if data.transcriber_settings:
        assistant_data["transcriber_settings"] = data.transcriber_settings.model_dump()
    if data.stop_speaking_plan:
        assistant_data["stop_speaking_plan"] = data.stop_speaking_plan.model_dump()

    return assistants_store.create(assistant_data)


@router.delete("/{assistant_id}", status_code=204)
async def delete_assistant(assistant_id: str):
    """
    Delete an assistant

    This action cannot be undone.
    """
    if not assistants_store.delete(assistant_id):
        raise HTTPException(status_code=404, detail="Assistant not found")


@router.post("/{assistant_id}/duplicate")
async def duplicate_assistant(assistant_id: str, new_name: Optional[str] = None):
    """
    Duplicate an existing assistant

    Creates a copy with a new ID. Optionally provide a new name.
    """
    original = assistants_store.get(assistant_id)
    if not original:
        raise HTTPException(status_code=404, detail="Assistant not found")

    # Create copy without ID
    copy_data = {k: v for k, v in original.items() if k not in ["id", "created_at", "updated_at"]}
    copy_data["name"] = new_name or f"{original['name']} (Copy)"

    return assistants_store.create(copy_data)
