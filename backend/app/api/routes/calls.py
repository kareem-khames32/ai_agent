"""
Calls routes
"""
from typing import List, Optional
from uuid import UUID
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.models.call import Call
from app.models.user import User
from app.schemas.call import CallResponse, CallListResponse, OutboundCallRequest
from app.api.deps import get_current_user

router = APIRouter()


@router.get("", response_model=CallListResponse)
async def list_calls(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    assistant_id: Optional[UUID] = None,
    type: Optional[str] = None,
    status: Optional[str] = None,
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List calls with pagination and filters"""
    query = select(Call).where(Call.organization_id == current_user.organization_id)

    # Apply filters
    if assistant_id:
        query = query.where(Call.assistant_id == assistant_id)
    if type:
        query = query.where(Call.type == type)
    if status:
        query = query.where(Call.status == status)
    if from_date:
        query = query.where(Call.created_at >= from_date)
    if to_date:
        query = query.where(Call.created_at <= to_date)

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()

    # Paginate
    query = query.order_by(Call.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    result = await db.execute(query)
    calls = result.scalars().all()

    return CallListResponse(
        data=[CallResponse.model_validate(c) for c in calls],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=(total + page_size - 1) // page_size,
    )


@router.get("/{call_id}", response_model=CallResponse)
async def get_call(
    call_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get call details"""
    result = await db.execute(
        select(Call)
        .where(Call.id == call_id)
        .where(Call.organization_id == current_user.organization_id)
    )
    call = result.scalar_one_or_none()

    if not call:
        raise HTTPException(status_code=404, detail="Call not found")

    return CallResponse.model_validate(call)


@router.get("/{call_id}/transcript")
async def get_transcript(
    call_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get call transcript"""
    result = await db.execute(
        select(Call)
        .where(Call.id == call_id)
        .where(Call.organization_id == current_user.organization_id)
    )
    call = result.scalar_one_or_none()

    if not call:
        raise HTTPException(status_code=404, detail="Call not found")

    return {"transcript": call.transcript}


@router.get("/{call_id}/recording")
async def get_recording(
    call_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get call recording URL"""
    result = await db.execute(
        select(Call)
        .where(Call.id == call_id)
        .where(Call.organization_id == current_user.organization_id)
    )
    call = result.scalar_one_or_none()

    if not call:
        raise HTTPException(status_code=404, detail="Call not found")

    if not call.recording_url:
        raise HTTPException(status_code=404, detail="No recording available")

    return {"url": call.recording_url}


@router.post("/outbound", response_model=CallResponse, status_code=status.HTTP_201_CREATED)
async def create_outbound_call(
    data: OutboundCallRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create an outbound call"""
    # TODO: Implement actual call initiation
    call = Call(
        organization_id=current_user.organization_id,
        assistant_id=data.assistant_id,
        squad_id=data.squad_id,
        phone_number_id=data.phone_number_id,
        customer_phone_number=data.customer_phone_number,
        type="outbound",
        status="queued",
        call_metadata=data.metadata,
    )
    db.add(call)
    await db.commit()
    await db.refresh(call)

    return CallResponse.model_validate(call)


@router.delete("/{call_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_call(
    call_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete call data"""
    result = await db.execute(
        select(Call)
        .where(Call.id == call_id)
        .where(Call.organization_id == current_user.organization_id)
    )
    call = result.scalar_one_or_none()

    if not call:
        raise HTTPException(status_code=404, detail="Call not found")

    await db.delete(call)
    await db.commit()
