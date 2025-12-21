"""
Standalone Voice Agent Server
Run with: cd backend && python -m app.voice_server
"""
import asyncio
import base64
import json
from typing import Optional, Dict
from uuid import uuid4

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from starlette.websockets import WebSocketState
from loguru import logger

from app.voice_agent import VoiceAgent, VoiceAgentConfig, get_config, AgentState


# Create minimal FastAPI app
app = FastAPI(
    title="Voice AI Agent",
    version="1.0.0",
    description="Voice AI Agent - Real-time voice conversation",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store active connections
active_connections: Dict[str, WebSocket] = {}


@app.websocket("/api/voice/ws")
async def voice_websocket(
    websocket: WebSocket,
    assistant_id: Optional[str] = Query(None)
):
    """
    WebSocket endpoint for real-time voice conversation

    Protocol:
    Client sends:
    - {"type": "config", "system_prompt": "...", "assistant_id": "..."}
    - {"type": "audio", "data": "<base64 PCM 16kHz mono>"}
    - {"type": "stop"} - End conversation

    Server sends:
    - {"type": "ready", "call_id": "..."} - Agent ready
    - {"type": "audio", "data": "<base64 PCM 24kHz mono>"} - Audio output
    - {"type": "transcript", "text": "...", "is_final": true/false} - User speech
    - {"type": "response", "text": "..."} - AI response text
    - {"type": "state", "state": "listening|processing|speaking"}
    """
    await websocket.accept()
    call_id = str(uuid4())[:8]
    active_connections[call_id] = websocket
    logger.info(f"🔌 Voice WebSocket connected: {call_id}")

    config = get_config()
    agent: Optional[VoiceAgent] = None
    is_connected = True

    async def send_audio(audio_chunk: bytes):
        if not is_connected:
            return
        try:
            audio_b64 = base64.b64encode(audio_chunk).decode('utf-8')
            await websocket.send_json({"type": "audio", "data": audio_b64})
        except Exception as e:
            logger.error(f"Send audio error: {e}")

    async def send_transcript(text: str, is_final: bool):
        if not is_connected:
            return
        try:
            await websocket.send_json({"type": "transcript", "text": text, "is_final": is_final})
        except Exception as e:
            logger.error(f"Send transcript error: {e}")

    async def send_response(text: str):
        if not is_connected:
            return
        try:
            await websocket.send_json({"type": "response", "text": text})
        except Exception as e:
            logger.error(f"Send response error: {e}")

    async def send_state(state: AgentState):
        if not is_connected:
            return
        try:
            await websocket.send_json({"type": "state", "state": state.value})
        except Exception as e:
            logger.error(f"Send state error: {e}")

    try:
        # Create agent
        agent = VoiceAgent(config, call_id)

        # Set up callbacks
        agent.on_audio_output = send_audio
        agent.on_transcript = send_transcript
        agent.on_response = send_response
        agent.on_state_change = send_state

        # Wait for config message
        config_received = False
        system_prompt = "أنت مساعد صوتي ذكي. تتحدث العربية بطلاقة. كن مختصراً ومفيداً."

        while not config_received and is_connected:
            try:
                data = await asyncio.wait_for(websocket.receive_json(), timeout=30.0)

                if data.get("type") == "config":
                    system_prompt = data.get("system_prompt", system_prompt)
                    assistant_id = data.get("assistant_id")
                    logger.info(f"📋 Config received (assistant_id={assistant_id})")
                    config_received = True
                elif data.get("type") == "audio":
                    config_received = True
            except asyncio.TimeoutError:
                logger.warning("Config timeout, using defaults")
                config_received = True

        # Start agent
        await agent.start(system_prompt)

        # Send ready message
        await websocket.send_json({"type": "ready", "call_id": call_id})

        # Main message loop
        while is_connected and websocket.client_state == WebSocketState.CONNECTED:
            try:
                data = await asyncio.wait_for(websocket.receive_json(), timeout=60.0)
                msg_type = data.get("type")

                if msg_type == "audio":
                    audio_b64 = data.get("data")
                    if audio_b64:
                        audio_bytes = base64.b64decode(audio_b64)
                        await agent.process_audio(audio_bytes)
                elif msg_type == "stop":
                    logger.info(f"Stop requested: {call_id}")
                    break
                elif msg_type == "ping":
                    await websocket.send_json({"type": "pong"})

            except asyncio.TimeoutError:
                await websocket.send_json({"type": "ping"})
            except WebSocketDisconnect:
                raise
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {e}")
            except Exception as e:
                logger.error(f"Message loop error: {e}")
                break

    except WebSocketDisconnect:
        logger.info(f"🔌 WebSocket disconnected: {call_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        is_connected = False
        if agent:
            await agent.stop()
        if call_id in active_connections:
            del active_connections[call_id]
        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.close()
        except:
            pass
        logger.info(f"🔌 Voice WebSocket cleanup: {call_id}")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "Voice AI Agent",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "websocket": "ws://localhost:8000/api/voice/ws",
            "health": "/api/voice/health",
        }
    }


@app.get("/api/voice/health")
async def voice_health():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "voice_agent",
        "active_calls": len(active_connections)
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    logger.info("🎙️ Starting Voice AI Agent Server...")
    uvicorn.run(
        "app.voice_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
