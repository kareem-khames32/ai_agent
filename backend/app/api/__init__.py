"""
API routes initialization
"""
from fastapi import APIRouter
from app.api.routes import auth, assistants, tools, phone_numbers, calls, voices, analytics, api_keys, settings, realtime

api_router = APIRouter()

# Include all routes
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(assistants.router, prefix="/assistants", tags=["Assistants"])
api_router.include_router(tools.router, prefix="/tools", tags=["Tools"])
api_router.include_router(phone_numbers.router, prefix="/phone-numbers", tags=["Phone Numbers"])
api_router.include_router(calls.router, prefix="/calls", tags=["Calls"])
api_router.include_router(voices.router, prefix="/voices", tags=["Voices"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])
api_router.include_router(api_keys.router, prefix="/api-keys", tags=["API Keys"])
api_router.include_router(settings.router, prefix="/settings", tags=["Settings"])
api_router.include_router(realtime.router, prefix="/realtime", tags=["Realtime Voice"])
