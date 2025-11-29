"""
Call schemas
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field


class TranscriptMessage(BaseModel):
    """Transcript message schema"""
    role: str  # user, assistant
    text: str
    timestamp: datetime
    duration_ms: int


class ToolCallRecord(BaseModel):
    """Tool call record schema"""
    id: str
    tool_id: str
    tool_name: str
    arguments: Dict[str, Any]
    result: Optional[Any] = None
    status: str  # pending, success, error
    timestamp: datetime
    duration_ms: int


class CostBreakdown(BaseModel):
    """Cost breakdown schema"""
    llm: float = 0
    stt: float = 0
    tts: float = 0
    telephony: float = 0


class CallBase(BaseModel):
    """Base call schema"""
    type: str  # inbound, outbound
    customer_phone_number: str


class OutboundCallRequest(BaseModel):
    """Outbound call request schema"""
    assistant_id: Optional[UUID] = None
    squad_id: Optional[UUID] = None
    phone_number_id: UUID
    customer_phone_number: str
    metadata: Optional[Dict[str, Any]] = None


class CallResponse(BaseModel):
    """Call response schema"""
    id: UUID
    organization_id: UUID
    assistant_id: Optional[UUID]
    squad_id: Optional[UUID]

    type: str
    status: str

    phone_number_id: Optional[UUID]
    customer_phone_number: Optional[str]

    started_at: Optional[datetime]
    ended_at: Optional[datetime]
    duration_seconds: int

    ended_reason: Optional[str]
    success_evaluation: Optional[str]
    score: Optional[float]

    transcript: List[TranscriptMessage] = Field(default_factory=list)
    tool_calls: List[ToolCallRecord] = Field(default_factory=list)
    recording_url: Optional[str]

    cost_breakdown: CostBreakdown
    total_cost: float

    summary: Optional[str]
    structured_data: Optional[Dict[str, Any]]

    metadata: Optional[Dict[str, Any]]
    created_at: datetime

    class Config:
        from_attributes = True


class CallListResponse(BaseModel):
    """Paginated call list response"""
    data: List[CallResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
