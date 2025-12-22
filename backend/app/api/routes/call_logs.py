"""
Call Logs API routes
"""
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse
from pathlib import Path

from app.voice_agent.call_recorder import call_log_storage

router = APIRouter()


@router.get("")
async def list_call_logs(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """List all call logs with pagination"""
    return call_log_storage.list_calls(limit=limit, offset=offset)


@router.get("/{call_id}")
async def get_call_log(call_id: str):
    """Get a specific call log"""
    call_log = call_log_storage.get(call_id)
    if not call_log:
        raise HTTPException(status_code=404, detail="Call log not found")
    return call_log


@router.delete("/{call_id}")
async def delete_call_log(call_id: str):
    """Delete a call log"""
    if call_log_storage.delete(call_id):
        return {"message": "Call log deleted"}
    raise HTTPException(status_code=404, detail="Call log not found")


@router.get("/{call_id}/recording")
async def get_recording(call_id: str):
    """Get call recording audio file"""
    call_log = call_log_storage.get(call_id)
    if not call_log:
        raise HTTPException(status_code=404, detail="Call log not found")

    recording_path = call_log.get("recording_path")
    if not recording_path or not Path(recording_path).exists():
        raise HTTPException(status_code=404, detail="Recording not found")

    return FileResponse(
        recording_path,
        media_type="audio/wav",
        filename=f"call_{call_id}.wav"
    )


@router.get("/{call_id}/transcript")
async def get_transcript(call_id: str):
    """Get call transcript"""
    call_log = call_log_storage.get(call_id)
    if not call_log:
        raise HTTPException(status_code=404, detail="Call log not found")

    return {
        "call_id": call_id,
        "transcripts": call_log.get("transcripts", [])
    }


@router.get("/stats/summary")
async def get_stats_summary():
    """Get overall call statistics"""
    all_calls = call_log_storage.list_calls(limit=1000)
    calls = all_calls.get("calls", [])

    if not calls:
        return {
            "total_calls": 0,
            "total_duration_sec": 0,
            "total_cost": 0,
            "avg_duration_sec": 0,
            "avg_cost": 0,
        }

    total_duration = sum(c.get("duration_sec", 0) for c in calls)
    total_cost = sum(c.get("total_cost", 0) for c in calls)

    return {
        "total_calls": len(calls),
        "total_duration_sec": total_duration,
        "total_cost": round(total_cost, 4),
        "avg_duration_sec": round(total_duration / len(calls), 2),
        "avg_cost": round(total_cost / len(calls), 4),
    }
