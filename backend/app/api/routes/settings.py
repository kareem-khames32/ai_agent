"""
Settings routes
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel

from app.core.database import get_db
from app.core.security import encrypt_value, decrypt_value
from app.models.credentials import ProviderCredential
from app.models.user import User, Organization
from app.api.deps import get_current_user

router = APIRouter()


class ProviderCredentialsResponse(BaseModel):
    provider: str
    is_configured: bool
    last_updated: str = None


class CredentialsInput(BaseModel):
    provider: str
    api_key: str = None
    api_secret: str = None
    region: str = None
    project_id: str = None


class OrganizationSettings(BaseModel):
    name: str
    default_language: str = "ar-SA"
    default_model_provider: str = "anthropic"
    default_voice_provider: str = "elevenlabs"


@router.get("")
async def get_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get organization settings"""
    result = await db.execute(
        select(Organization).where(Organization.id == current_user.organization_id)
    )
    org = result.scalar_one_or_none()

    return {
        "organization": {
            "id": str(org.id),
            "name": org.name,
        },
        "user": {
            "id": str(current_user.id),
            "email": current_user.email,
            "name": current_user.name,
            "role": current_user.role.value,
        },
    }


@router.patch("")
async def update_settings(
    data: OrganizationSettings,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update organization settings"""
    result = await db.execute(
        select(Organization).where(Organization.id == current_user.organization_id)
    )
    org = result.scalar_one_or_none()

    org.name = data.name
    await db.commit()

    return {"message": "Settings updated"}


@router.get("/credentials", response_model=List[ProviderCredentialsResponse])
async def get_credentials(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get configured provider credentials (without secrets)"""
    result = await db.execute(
        select(ProviderCredential)
        .where(ProviderCredential.organization_id == current_user.organization_id)
    )
    creds = result.scalars().all()

    # List all supported providers
    providers = [
        "openai", "anthropic", "google", "azure",
        "elevenlabs", "deepgram", "twilio", "vonage"
    ]

    configured = {c.provider: c for c in creds}

    return [
        ProviderCredentialsResponse(
            provider=p,
            is_configured=p in configured,
            last_updated=str(configured[p].updated_at) if p in configured else None,
        )
        for p in providers
    ]


@router.patch("/credentials")
async def update_credentials(
    data: CredentialsInput,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update provider credentials"""
    # Find existing credential
    result = await db.execute(
        select(ProviderCredential)
        .where(ProviderCredential.organization_id == current_user.organization_id)
        .where(ProviderCredential.provider == data.provider)
    )
    cred = result.scalar_one_or_none()

    # Build credentials object
    credentials = {}
    if data.api_key:
        credentials["api_key"] = encrypt_value(data.api_key)
    if data.api_secret:
        credentials["api_secret"] = encrypt_value(data.api_secret)
    if data.region:
        credentials["region"] = data.region
    if data.project_id:
        credentials["project_id"] = data.project_id

    if cred:
        cred.credentials = credentials
    else:
        cred = ProviderCredential(
            organization_id=current_user.organization_id,
            provider=data.provider,
            credentials=credentials,
        )
        db.add(cred)

    await db.commit()

    return {"message": f"Credentials for {data.provider} updated"}
