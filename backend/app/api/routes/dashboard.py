"""
Dashboard Statistics API Routes
Provides analytics and metrics for the voice AI platform
"""
from typing import Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Query

from app.voice_agent.call_recorder import call_log_storage
from app.storage import assistants_store

router = APIRouter()


@router.get("/stats")
async def get_dashboard_stats():
    """
    Get overall platform statistics

    Returns:
        - Total calls, assistants, cost
        - Average call duration and latency
        - Provider usage breakdown
    """
    # Get all call logs
    all_calls_data = call_log_storage.list_calls(limit=10000, include_details=True)
    calls = all_calls_data.get("calls", [])

    # Get all assistants
    assistants_data = assistants_store.list(limit=1000)
    assistants = assistants_data.get("assistants", [])

    if not calls:
        return {
            "total_calls": 0,
            "total_assistants": len(assistants),
            "total_duration_sec": 0,
            "total_cost": 0,
            "avg_duration_sec": 0,
            "avg_latency_ms": 0,
            "avg_cost_per_call": 0,
            "calls_today": 0,
            "calls_this_week": 0,
            "calls_this_month": 0,
        }

    # Calculate metrics
    total_duration = sum(c.get("duration_sec", 0) for c in calls)
    total_cost = sum(c.get("cost", {}).get("total_cost", 0) for c in calls)

    latencies = [
        c.get("metrics", {}).get("avg_response_latency_ms", 0)
        for c in calls
        if c.get("metrics", {}).get("avg_response_latency_ms", 0) > 0
    ]
    avg_latency = sum(latencies) / len(latencies) if latencies else 0

    # Time-based stats
    now = datetime.utcnow()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    calls_today = 0
    calls_this_week = 0
    calls_this_month = 0

    for call in calls:
        try:
            started = datetime.fromisoformat(call.get("started_at", "").replace("Z", ""))
            if started >= today:
                calls_today += 1
            if started >= week_ago:
                calls_this_week += 1
            if started >= month_ago:
                calls_this_month += 1
        except (ValueError, TypeError):
            pass

    return {
        "total_calls": len(calls),
        "total_assistants": len(assistants),
        "total_duration_sec": round(total_duration, 1),
        "total_cost": round(total_cost, 4),
        "avg_duration_sec": round(total_duration / len(calls), 1),
        "avg_latency_ms": round(avg_latency, 0),
        "avg_cost_per_call": round(total_cost / len(calls), 4),
        "calls_today": calls_today,
        "calls_this_week": calls_this_week,
        "calls_this_month": calls_this_month,
    }


@router.get("/provider-usage")
async def get_provider_usage():
    """
    Get usage breakdown by provider

    Returns usage stats for STT, LLM, and TTS providers.
    """
    all_calls_data = call_log_storage.list_calls(limit=10000, include_details=True)
    calls = all_calls_data.get("calls", [])

    # Initialize counters
    stt_usage = {}
    llm_usage = {}
    tts_usage = {}
    mode_usage = {"pipeline": 0, "realtime": 0}

    for call in calls:
        # Mode
        mode = call.get("voice_mode", "pipeline")
        mode_usage[mode] = mode_usage.get(mode, 0) + 1

        # STT provider
        stt = call.get("stt_provider", "unknown")
        stt_usage[stt] = stt_usage.get(stt, 0) + 1

        # LLM provider
        llm = call.get("llm_provider", "unknown")
        llm_usage[llm] = llm_usage.get(llm, 0) + 1

        # TTS provider
        tts = call.get("tts_provider", "unknown")
        tts_usage[tts] = tts_usage.get(tts, 0) + 1

    return {
        "mode_usage": mode_usage,
        "stt_usage": stt_usage,
        "llm_usage": llm_usage,
        "tts_usage": tts_usage,
    }


@router.get("/cost-breakdown")
async def get_cost_breakdown(
    days: int = Query(30, ge=1, le=365, description="Number of days to include")
):
    """
    Get cost breakdown by component

    Returns cost breakdown for STT, LLM, and TTS.
    """
    all_calls_data = call_log_storage.list_calls(limit=10000, include_details=True)
    calls = all_calls_data.get("calls", [])

    # Filter by date
    cutoff = datetime.utcnow() - timedelta(days=days)
    filtered_calls = []

    for call in calls:
        try:
            started = datetime.fromisoformat(call.get("started_at", "").replace("Z", ""))
            if started >= cutoff:
                filtered_calls.append(call)
        except (ValueError, TypeError):
            pass

    # Calculate costs
    total_stt = sum(c.get("cost", {}).get("stt_cost", 0) for c in filtered_calls)
    total_llm = sum(c.get("cost", {}).get("llm_cost", 0) for c in filtered_calls)
    total_tts = sum(c.get("cost", {}).get("tts_cost", 0) for c in filtered_calls)
    total = total_stt + total_llm + total_tts

    return {
        "period_days": days,
        "call_count": len(filtered_calls),
        "stt_cost": round(total_stt, 4),
        "llm_cost": round(total_llm, 4),
        "tts_cost": round(total_tts, 4),
        "total_cost": round(total, 4),
        "breakdown_percentage": {
            "stt": round(total_stt / total * 100, 1) if total > 0 else 0,
            "llm": round(total_llm / total * 100, 1) if total > 0 else 0,
            "tts": round(total_tts / total * 100, 1) if total > 0 else 0,
        }
    }


@router.get("/call-volume")
async def get_call_volume(
    days: int = Query(7, ge=1, le=90, description="Number of days to include"),
    granularity: str = Query("day", description="Granularity: hour, day, week")
):
    """
    Get call volume over time

    Returns call counts grouped by time period.
    """
    all_calls_data = call_log_storage.list_calls(limit=10000, include_details=True)
    calls = all_calls_data.get("calls", [])

    # Filter by date
    cutoff = datetime.utcnow() - timedelta(days=days)
    filtered_calls = []

    for call in calls:
        try:
            started = datetime.fromisoformat(call.get("started_at", "").replace("Z", ""))
            if started >= cutoff:
                filtered_calls.append({"started_at": started, "call": call})
        except (ValueError, TypeError):
            pass

    # Group by period
    volume = {}

    for item in filtered_calls:
        started = item["started_at"]

        if granularity == "hour":
            key = started.strftime("%Y-%m-%d %H:00")
        elif granularity == "week":
            # Get start of week
            week_start = started - timedelta(days=started.weekday())
            key = week_start.strftime("%Y-%m-%d")
        else:  # day
            key = started.strftime("%Y-%m-%d")

        if key not in volume:
            volume[key] = {"count": 0, "duration": 0, "cost": 0}

        volume[key]["count"] += 1
        volume[key]["duration"] += item["call"].get("duration_sec", 0)
        volume[key]["cost"] += item["call"].get("cost", {}).get("total_cost", 0)

    # Convert to list and sort
    volume_list = [
        {
            "period": k,
            "count": v["count"],
            "duration_sec": round(v["duration"], 1),
            "cost": round(v["cost"], 4)
        }
        for k, v in sorted(volume.items())
    ]

    return {
        "period_days": days,
        "granularity": granularity,
        "data": volume_list
    }


@router.get("/top-assistants")
async def get_top_assistants(limit: int = Query(10, ge=1, le=50)):
    """
    Get top assistants by usage

    Returns assistants ranked by call count.
    """
    all_calls_data = call_log_storage.list_calls(limit=10000, include_details=True)
    calls = all_calls_data.get("calls", [])

    # Count by assistant
    assistant_stats = {}

    for call in calls:
        assistant_id = call.get("assistant_id") or "unknown"
        assistant_name = call.get("assistant_name") or "Unknown Assistant"

        if assistant_id not in assistant_stats:
            assistant_stats[assistant_id] = {
                "id": assistant_id,
                "name": assistant_name,
                "call_count": 0,
                "total_duration": 0,
                "total_cost": 0,
            }

        assistant_stats[assistant_id]["call_count"] += 1
        assistant_stats[assistant_id]["total_duration"] += call.get("duration_sec", 0)
        assistant_stats[assistant_id]["total_cost"] += call.get("cost", {}).get("total_cost", 0)

    # Sort by call count and limit
    sorted_assistants = sorted(
        assistant_stats.values(),
        key=lambda x: x["call_count"],
        reverse=True
    )[:limit]

    # Round values
    for a in sorted_assistants:
        a["total_duration"] = round(a["total_duration"], 1)
        a["total_cost"] = round(a["total_cost"], 4)
        a["avg_duration"] = round(a["total_duration"] / a["call_count"], 1) if a["call_count"] > 0 else 0

    return sorted_assistants


@router.get("/latency-stats")
async def get_latency_stats():
    """
    Get latency statistics

    Returns average latency by component and percentiles.
    """
    all_calls_data = call_log_storage.list_calls(limit=10000, include_details=True)
    calls = all_calls_data.get("calls", [])

    # Collect latency values
    response_latencies = []
    stt_latencies = []
    llm_latencies = []
    tts_latencies = []

    for call in calls:
        metrics = call.get("metrics", {})

        if metrics.get("avg_response_latency_ms", 0) > 0:
            response_latencies.append(metrics["avg_response_latency_ms"])
        if metrics.get("stt_latency_ms", 0) > 0:
            stt_latencies.append(metrics["stt_latency_ms"])
        if metrics.get("llm_latency_ms", 0) > 0:
            llm_latencies.append(metrics["llm_latency_ms"])
        if metrics.get("tts_latency_ms", 0) > 0:
            tts_latencies.append(metrics["tts_latency_ms"])

    def calc_stats(values):
        if not values:
            return {"avg": 0, "min": 0, "max": 0, "p50": 0, "p95": 0}

        sorted_vals = sorted(values)
        n = len(sorted_vals)

        return {
            "avg": round(sum(values) / n, 0),
            "min": round(min(values), 0),
            "max": round(max(values), 0),
            "p50": round(sorted_vals[int(n * 0.5)], 0),
            "p95": round(sorted_vals[int(n * 0.95)] if n > 20 else sorted_vals[-1], 0),
        }

    return {
        "response_latency": calc_stats(response_latencies),
        "stt_latency": calc_stats(stt_latencies),
        "llm_latency": calc_stats(llm_latencies),
        "tts_latency": calc_stats(tts_latencies),
        "sample_count": len(response_latencies),
    }
