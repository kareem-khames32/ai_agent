"""
Phone Numbers routes
"""
from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.core.database import get_db
from app.models.phone_number import PhoneNumber
from app.models.user import User
from app.api.deps import get_current_user

router = APIRouter()


class PhoneNumberCreate(BaseModel):
    number: str
    label: str = None
    provider: str = "twilio"
    server_url: str = None
    timeout_seconds: int = 20
    assigned_assistant_id: UUID = None
    assigned_squad_id: UUID = None


class PhoneNumberResponse(BaseModel):
    id: UUID
    number: str
    label: str = None
    provider: str
    server_url: str = None
    timeout_seconds: int
    assigned_assistant_id: UUID = None
    assigned_squad_id: UUID = None
    settings: dict

    class Config:
        from_attributes = True


@router.get("", response_model=List[PhoneNumberResponse])
async def list_phone_numbers(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all phone numbers"""
    result = await db.execute(
        select(PhoneNumber)
        .where(PhoneNumber.organization_id == current_user.organization_id)
    )
    return result.scalars().all()


@router.post("", response_model=PhoneNumberResponse, status_code=status.HTTP_201_CREATED)
async def create_phone_number(
    data: PhoneNumberCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add a phone number"""
    phone = PhoneNumber(
        organization_id=current_user.organization_id,
        number=data.number,
        label=data.label,
        provider=data.provider,
        server_url=data.server_url,
        timeout_seconds=data.timeout_seconds,
        assigned_assistant_id=data.assigned_assistant_id,
        assigned_squad_id=data.assigned_squad_id,
    )
    db.add(phone)
    await db.commit()
    await db.refresh(phone)
    return phone


@router.get("/{phone_id}", response_model=PhoneNumberResponse)
async def get_phone_number(
    phone_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a phone number"""
    result = await db.execute(
        select(PhoneNumber)
        .where(PhoneNumber.id == phone_id)
        .where(PhoneNumber.organization_id == current_user.organization_id)
    )
    phone = result.scalar_one_or_none()
    if not phone:
        raise HTTPException(status_code=404, detail="Phone number not found")
    return phone


@router.delete("/{phone_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_phone_number(
    phone_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a phone number"""
    result = await db.execute(
        select(PhoneNumber)
        .where(PhoneNumber.id == phone_id)
        .where(PhoneNumber.organization_id == current_user.organization_id)
    )
    phone = result.scalar_one_or_none()
    if not phone:
        raise HTTPException(status_code=404, detail="Phone number not found")
    await db.delete(phone)
    await db.commit()
