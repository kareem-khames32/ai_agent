"""
API Keys routes
"""
from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.core.database import get_db
from app.core.security import generate_api_key, get_key_prefix
from app.models.api_key import ApiKey
from app.models.user import User
from app.api.deps import get_current_user

router = APIRouter()


class ApiKeyCreate(BaseModel):
    name: str
    permissions: List[str] = []


class ApiKeyResponse(BaseModel):
    id: UUID
    name: str
    key_prefix: str
    permissions: list
    last_used_at: str = None
    created_at: str

    class Config:
        from_attributes = True


class ApiKeyCreateResponse(BaseModel):
    key: str  # Full key (only shown once)
    api_key: ApiKeyResponse


@router.get("", response_model=List[ApiKeyResponse])
async def list_api_keys(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all API keys"""
    result = await db.execute(
        select(ApiKey)
        .where(ApiKey.organization_id == current_user.organization_id)
        .order_by(ApiKey.created_at.desc())
    )
    return result.scalars().all()


@router.post("", response_model=ApiKeyCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    data: ApiKeyCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new API key"""
    # Generate key
    plain_key, hashed_key = generate_api_key()
    key_prefix = get_key_prefix(plain_key)

    api_key = ApiKey(
        organization_id=current_user.organization_id,
        name=data.name,
        key_hash=hashed_key,
        key_prefix=key_prefix,
        permissions=data.permissions,
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)

    return ApiKeyCreateResponse(
        key=plain_key,
        api_key=ApiKeyResponse.model_validate(api_key),
    )


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    key_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Revoke an API key"""
    result = await db.execute(
        select(ApiKey)
        .where(ApiKey.id == key_id)
        .where(ApiKey.organization_id == current_user.organization_id)
    )
    api_key = result.scalar_one_or_none()

    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    await db.delete(api_key)
    await db.commit()
