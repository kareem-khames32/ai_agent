"""
API routes initialization
"""
from fastapi import APIRouter
from loguru import logger

# Import required routes
from app.api.routes import auth, assistants, tools, phone_numbers, calls, voices, analytics, api_keys, settings, call_logs

api_router = APIRouter()

# Include all required routes
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(assistants.router, prefix="/assistants", tags=["Assistants"])
api_router.include_router(tools.router, prefix="/tools", tags=["Tools"])
api_router.include_router(phone_numbers.router, prefix="/phone-numbers", tags=["Phone Numbers"])
api_router.include_router(calls.router, prefix="/calls", tags=["Calls"])
api_router.include_router(voices.router, prefix="/voices", tags=["Voices"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
api_router.include_router(api_keys.router, prefix="/api-keys", tags=["API Keys"])
api_router.include_router(settings.router, prefix="/settings", tags=["Settings"])
api_router.include_router(call_logs.router, prefix="/call-logs", tags=["Call Logs"])

# Try to import voice route (optional - requires numpy, deepgram)
try:
    from app.api.routes import voice
    api_router.include_router(voice.router, prefix="/voice", tags=["Voice Agent"])
    logger.info("Voice Agent routes loaded successfully")
except ImportError as e:
    # Create a fallback router with error message
    from fastapi import WebSocket
    from fastapi.responses import JSONResponse

    voice_fallback = APIRouter()
    missing_dep = str(e).replace("No module named ", "").strip("'")

    @voice_fallback.get("/health")
    async def voice_health_fallback():
        return JSONResponse(
            status_code=503,
            content={
                "status": "unavailable",
                "error": f"Voice Agent requires: {missing_dep}",
                "fix": f"Run: pip install {missing_dep}"
            }
        )

    @voice_fallback.websocket("/ws")
    async def voice_ws_fallback(websocket: WebSocket):
        await websocket.accept()
        await websocket.send_json({
            "type": "error",
            "message": f"Voice Agent unavailable. Missing: {missing_dep}. Run: pip install {missing_dep}"
        })
        await websocket.close()

    api_router.include_router(voice_fallback, prefix="/voice", tags=["Voice Agent"])
    logger.warning(f"Voice Agent not available - missing: {missing_dep}")
