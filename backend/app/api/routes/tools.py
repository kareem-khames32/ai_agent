"""
Tools routes
"""
from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.models.tool import Tool
from app.models.user import User
from app.schemas.tool import ToolCreate, ToolUpdate, ToolResponse
from app.api.deps import get_current_user

router = APIRouter()


@router.get("", response_model=List[ToolResponse])
async def list_tools(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all tools for the organization"""
    result = await db.execute(
        select(Tool)
        .where(Tool.organization_id == current_user.organization_id)
        .order_by(Tool.created_at.desc())
    )
    tools = result.scalars().all()
    return [ToolResponse.model_validate(t) for t in tools]


@router.post("", response_model=ToolResponse, status_code=status.HTTP_201_CREATED)
async def create_tool(
    data: ToolCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new tool"""
    tool = Tool(
        organization_id=current_user.organization_id,
        name=data.name,
        type=data.type,
        description=data.description,
        parameters=[p.model_dump() for p in data.parameters],
        server_url=data.server_url,
        headers=data.headers or {},
        is_async=data.is_async,
        is_strict=data.is_strict,
    )
    db.add(tool)
    await db.commit()
    await db.refresh(tool)
    return ToolResponse.model_validate(tool)


@router.get("/{tool_id}", response_model=ToolResponse)
async def get_tool(
    tool_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a tool by ID"""
    result = await db.execute(
        select(Tool)
        .where(Tool.id == tool_id)
        .where(Tool.organization_id == current_user.organization_id)
    )
    tool = result.scalar_one_or_none()

    if not tool:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tool not found")

    return ToolResponse.model_validate(tool)


@router.patch("/{tool_id}", response_model=ToolResponse)
async def update_tool(
    tool_id: UUID,
    data: ToolUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a tool"""
    result = await db.execute(
        select(Tool)
        .where(Tool.id == tool_id)
        .where(Tool.organization_id == current_user.organization_id)
    )
    tool = result.scalar_one_or_none()

    if not tool:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tool not found")

    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "parameters" and value:
            value = [p.model_dump() if hasattr(p, "model_dump") else p for p in value]
        setattr(tool, field, value)

    await db.commit()
    await db.refresh(tool)
    return ToolResponse.model_validate(tool)


@router.delete("/{tool_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tool(
    tool_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a tool"""
    result = await db.execute(
        select(Tool)
        .where(Tool.id == tool_id)
        .where(Tool.organization_id == current_user.organization_id)
    )
    tool = result.scalar_one_or_none()

    if not tool:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tool not found")

    await db.delete(tool)
    await db.commit()
