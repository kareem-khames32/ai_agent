"""
Tool schemas
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field


class ToolParameter(BaseModel):
    """Tool parameter schema"""
    name: str
    type: str  # string, number, boolean, object, array
    description: str
    required: bool = False
    enum: Optional[List[str]] = None
    default: Optional[Any] = None


class ToolBase(BaseModel):
    """Base tool schema"""
    name: str = Field(..., min_length=1, max_length=255)
    type: str  # api_request, function, handoff, end_call, transfer
    description: Optional[str] = None
    parameters: List[ToolParameter] = Field(default_factory=list)
    server_url: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    is_async: bool = False
    is_strict: bool = False


class ToolCreate(ToolBase):
    """Create tool schema"""
    pass


class ToolUpdate(BaseModel):
    """Update tool schema"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    type: Optional[str] = None
    description: Optional[str] = None
    parameters: Optional[List[ToolParameter]] = None
    server_url: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    is_async: Optional[bool] = None
    is_strict: Optional[bool] = None


class ToolResponse(ToolBase):
    """Tool response schema"""
    id: UUID
    organization_id: UUID
    created_at: datetime

    class Config:
        from_attributes = True
