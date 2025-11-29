"""
Assistants routes
"""
from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.assistant import Assistant
from app.models.user import User
from app.schemas.assistant import AssistantCreate, AssistantUpdate, AssistantResponse
from app.api.deps import get_current_user

router = APIRouter()


@router.get("", response_model=List[AssistantResponse])
async def list_assistants(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all assistants for the organization"""
    result = await db.execute(
        select(Assistant)
        .where(Assistant.organization_id == current_user.organization_id)
        .order_by(Assistant.created_at.desc())
    )
    assistants = result.scalars().all()
    return [AssistantResponse.model_validate(a) for a in assistants]


@router.post("", response_model=AssistantResponse, status_code=status.HTTP_201_CREATED)
async def create_assistant(
    data: AssistantCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new assistant"""
    assistant = Assistant(
        organization_id=current_user.organization_id,
        name=data.name,
        model_provider=data.model_provider,
        model_name=data.model_name,
        system_prompt=data.system_prompt,
        first_message=data.first_message,
        first_message_mode=data.first_message_mode,
        temperature=data.temperature,
        max_tokens=data.max_tokens,
        voice_provider=data.voice_provider,
        voice_id=data.voice_id,
        voice_settings=data.voice_settings.model_dump() if data.voice_settings else {},
        transcriber_provider=data.transcriber_provider,
        transcriber_language=data.transcriber_language,
        transcriber_settings=data.transcriber_settings.model_dump() if data.transcriber_settings else {},
        tools=data.tools,
        summary_prompt=data.summary_prompt,
        success_evaluation_prompt=data.success_evaluation_prompt,
        structured_data_schema=data.structured_data_schema or {},
        advanced_settings=data.advanced_settings.model_dump() if data.advanced_settings else {},
    )
    db.add(assistant)
    await db.commit()
    await db.refresh(assistant)
    return AssistantResponse.model_validate(assistant)


@router.get("/{assistant_id}", response_model=AssistantResponse)
async def get_assistant(
    assistant_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get an assistant by ID"""
    result = await db.execute(
        select(Assistant)
        .where(Assistant.id == assistant_id)
        .where(Assistant.organization_id == current_user.organization_id)
    )
    assistant = result.scalar_one_or_none()

    if not assistant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assistant not found",
        )

    return AssistantResponse.model_validate(assistant)


@router.patch("/{assistant_id}", response_model=AssistantResponse)
async def update_assistant(
    assistant_id: UUID,
    data: AssistantUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update an assistant"""
    result = await db.execute(
        select(Assistant)
        .where(Assistant.id == assistant_id)
        .where(Assistant.organization_id == current_user.organization_id)
    )
    assistant = result.scalar_one_or_none()

    if not assistant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assistant not found",
        )

    # Update fields
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if hasattr(assistant, field):
            if field in ["voice_settings", "transcriber_settings", "advanced_settings"] and value:
                value = value.model_dump() if hasattr(value, "model_dump") else value
            setattr(assistant, field, value)

    await db.commit()
    await db.refresh(assistant)
    return AssistantResponse.model_validate(assistant)


@router.delete("/{assistant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_assistant(
    assistant_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete an assistant"""
    result = await db.execute(
        select(Assistant)
        .where(Assistant.id == assistant_id)
        .where(Assistant.organization_id == current_user.organization_id)
    )
    assistant = result.scalar_one_or_none()

    if not assistant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assistant not found",
        )

    await db.delete(assistant)
    await db.commit()


@router.post("/{assistant_id}/test")
async def test_assistant(
    assistant_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Start a test call with the assistant"""
    result = await db.execute(
        select(Assistant)
        .where(Assistant.id == assistant_id)
        .where(Assistant.organization_id == current_user.organization_id)
    )
    assistant = result.scalar_one_or_none()

    if not assistant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assistant not found",
        )

    # TODO: Implement WebRTC test call
    return {"call_id": "test-call-id", "status": "connecting"}
