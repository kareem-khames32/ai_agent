"""
Analytics routes
"""
from typing import Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel

from app.core.database import get_db
from app.models.call import Call
from app.models.user import User
from app.api.deps import get_current_user

router = APIRouter()


class MetricsSummary(BaseModel):
    total_call_minutes: float
    number_of_calls: int
    total_spent: float
    average_cost_per_call: float
    average_call_duration: float


class UsageDataPoint(BaseModel):
    date: str
    calls: int
    minutes: float
    cost: float


@router.get("/metrics", response_model=MetricsSummary)
async def get_metrics(
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    assistant_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get analytics metrics summary"""
    # Default to last 30 days
    if not from_date:
        from_date = datetime.utcnow() - timedelta(days=30)
    if not to_date:
        to_date = datetime.utcnow()

    query = select(Call).where(
        Call.organization_id == current_user.organization_id,
        Call.created_at >= from_date,
        Call.created_at <= to_date,
    )

    if assistant_id:
        query = query.where(Call.assistant_id == assistant_id)

    result = await db.execute(query)
    calls = result.scalars().all()

    # Calculate metrics
    total_duration = sum(c.duration_seconds or 0 for c in calls)
    total_cost = sum(c.total_cost or 0 for c in calls)
    num_calls = len(calls)

    return MetricsSummary(
        total_call_minutes=total_duration / 60,
        number_of_calls=num_calls,
        total_spent=total_cost,
        average_cost_per_call=total_cost / num_calls if num_calls > 0 else 0,
        average_call_duration=total_duration / num_calls if num_calls > 0 else 0,
    )


@router.get("/usage")
async def get_usage(
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    group_by: str = Query("day", pattern="^(day|hour|week|month)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get usage data over time"""
    if not from_date:
        from_date = datetime.utcnow() - timedelta(days=30)
    if not to_date:
        to_date = datetime.utcnow()

    query = select(Call).where(
        Call.organization_id == current_user.organization_id,
        Call.created_at >= from_date,
        Call.created_at <= to_date,
    )

    result = await db.execute(query)
    calls = result.scalars().all()

    # Group by date
    from collections import defaultdict
    grouped = defaultdict(lambda: {"calls": 0, "minutes": 0, "cost": 0})

    for call in calls:
        if group_by == "hour":
            key = call.created_at.strftime("%Y-%m-%d %H:00")
        elif group_by == "week":
            key = call.created_at.strftime("%Y-W%W")
        elif group_by == "month":
            key = call.created_at.strftime("%Y-%m")
        else:
            key = call.created_at.strftime("%Y-%m-%d")

        grouped[key]["calls"] += 1
        grouped[key]["minutes"] += (call.duration_seconds or 0) / 60
        grouped[key]["cost"] += call.total_cost or 0

    return [
        UsageDataPoint(date=k, calls=v["calls"], minutes=v["minutes"], cost=v["cost"])
        for k, v in sorted(grouped.items())
    ]


@router.get("/costs")
async def get_costs(
    from_date: Optional[datetime] = None,
    to_date: Optional[datetime] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get cost breakdown"""
    if not from_date:
        from_date = datetime.utcnow() - timedelta(days=30)
    if not to_date:
        to_date = datetime.utcnow()

    query = select(Call).where(
        Call.organization_id == current_user.organization_id,
        Call.created_at >= from_date,
        Call.created_at <= to_date,
    )

    result = await db.execute(query)
    calls = result.scalars().all()

    # Aggregate costs
    llm_cost = sum(c.cost_breakdown.get("llm", 0) for c in calls if c.cost_breakdown)
    stt_cost = sum(c.cost_breakdown.get("stt", 0) for c in calls if c.cost_breakdown)
    tts_cost = sum(c.cost_breakdown.get("tts", 0) for c in calls if c.cost_breakdown)
    telephony_cost = sum(c.cost_breakdown.get("telephony", 0) for c in calls if c.cost_breakdown)

    return {
        "llm": llm_cost,
        "stt": stt_cost,
        "tts": tts_cost,
        "telephony": telephony_cost,
        "total": llm_cost + stt_cost + tts_cost + telephony_cost,
    }
