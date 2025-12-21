"""
Voice API routes - WebSocket for real-time audio streaming
Using new VoiceAgent pipeline with smart turn detection
"""
import asyncio
import base64
import json
import time
import os
from typing import Optional, Dict, Any
from uuid import uuid4
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends, Query
from fastapi.responses import Response
from starlette.websockets import WebSocketState
from loguru import logger

from app.voice_agent import VoiceAgent, VoiceAgentConfig, get_config, AgentState

router = APIRouter()


# Store active connections
active_connections: Dict[str, WebSocket] = {}


@router.websocket("/ws")
async def voice_agent_websocket(
    websocket: WebSocket,
    assistant_id: Optional[str] = Query(None)
):
    """
    WebSocket endpoint for real-time voice conversation using VoiceAgent

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
    - {"type": "error", "message": "..."} - Error message
    """
    await websocket.accept()
    call_id = str(uuid4())[:8]
    active_connections[call_id] = websocket
    logger.info(f"🔌 Voice WebSocket connected: {call_id}")

    config = get_config()
    agent: Optional[VoiceAgent] = None
    is_connected = True

    async def send_audio(audio_chunk: bytes):
        """Send audio to client"""
        if not is_connected:
            return
        try:
            audio_b64 = base64.b64encode(audio_chunk).decode('utf-8')
            await websocket.send_json({
                "type": "audio",
                "data": audio_b64
            })
        except Exception as e:
            logger.error(f"Send audio error: {e}")

    async def send_transcript(text: str, is_final: bool):
        """Send transcript to client"""
        if not is_connected:
            return
        try:
            await websocket.send_json({
                "type": "transcript",
                "text": text,
                "is_final": is_final
            })
        except Exception as e:
            logger.error(f"Send transcript error: {e}")

    async def send_response(text: str):
        """Send AI response to client"""
        if not is_connected:
            return
        try:
            await websocket.send_json({
                "type": "response",
                "text": text
            })
        except Exception as e:
            logger.error(f"Send response error: {e}")

    async def send_state(state: AgentState):
        """Send state change to client"""
        if not is_connected:
            return
        try:
            await websocket.send_json({
                "type": "state",
                "state": state.value
            })
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
        system_prompt = ""

        while not config_received and is_connected:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_json(),
                    timeout=30.0
                )

                if data.get("type") == "config":
                    system_prompt = data.get("system_prompt", "أنت مساعد صوتي ذكي. تتحدث العربية بطلاقة. كن مختصراً ومفيداً.")
                    assistant_id = data.get("assistant_id")
                    logger.info(f"📋 Config received (assistant_id={assistant_id})")
                    config_received = True

                elif data.get("type") == "audio":
                    # Audio before config, start with default
                    config_received = True
                    # Process this audio chunk after starting

            except asyncio.TimeoutError:
                logger.warning("Config timeout, using defaults")
                config_received = True

        # Start agent
        await agent.start(system_prompt)

        # Send ready message
        await websocket.send_json({
            "type": "ready",
            "call_id": call_id
        })

        # Main message loop
        while is_connected and websocket.client_state == WebSocketState.CONNECTED:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_json(),
                    timeout=60.0
                )

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
                # Send keepalive
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
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e)
            })
        except:
            pass
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

        logger.info(f"🔌 Voice WebSocket cleanup complete: {call_id}")


@router.websocket("/ws/{call_id}")
async def voice_websocket_legacy(
    websocket: WebSocket,
    call_id: str,
):
    """
    Legacy WebSocket endpoint - redirects to new endpoint
    Kept for backward compatibility
    """
    # Just use the new voice agent
    await websocket.accept()
    active_connections[call_id] = websocket
    logger.info(f"WebSocket connected (legacy): {call_id}")

    config = get_config()
    agent: Optional[VoiceAgent] = None
    is_connected = True

    async def send_audio(audio_chunk: bytes):
        if not is_connected:
            return
        try:
            audio_b64 = base64.b64encode(audio_chunk).decode('utf-8')
            await websocket.send_json({
                "type": "audio",
                "data": audio_b64
            })
        except Exception as e:
            logger.error(f"Send audio error: {e}")

    async def send_transcript(text: str, is_final: bool):
        if not is_connected:
            return
        try:
            await websocket.send_json({
                "type": "transcript",
                "role": "user",
                "text": text,
                "is_final": is_final
            })
        except Exception as e:
            logger.error(f"Send transcript error: {e}")

    async def send_response(text: str):
        if not is_connected:
            return
        try:
            await websocket.send_json({
                "type": "transcript",
                "role": "assistant",
                "text": text
            })
        except Exception as e:
            logger.error(f"Send response error: {e}")

    async def send_state(state: AgentState):
        pass  # Not used in legacy protocol

    try:
        agent = VoiceAgent(config, call_id)
        agent.on_audio_output = send_audio
        agent.on_transcript = send_transcript
        agent.on_response = send_response
        agent.on_state_change = send_state

        while is_connected:
            data = await websocket.receive_text()
            message = json.loads(data)
            msg_type = message.get("type")

            if msg_type == "config":
                config_data = message.get("data", {})
                system_prompt = config_data.get("system_prompt", "أنت مساعد صوتي ذكي.")
                await agent.start(system_prompt)
                await websocket.send_json({"type": "ready"})
                logger.info(f"Agent started for {call_id}")

            elif msg_type == "audio":
                if not agent.is_running:
                    await agent.start()
                audio_b64 = message.get("data", "")
                audio_data = base64.b64decode(audio_b64)
                await agent.process_audio(audio_data)

            elif msg_type == "interrupt":
                if agent:
                    agent.llm.cancel()
                    agent.tts.cancel()
                    await websocket.send_json({"type": "interrupted"})

            elif msg_type == "end":
                logger.info(f"Call ended: {call_id}")
                break

            elif msg_type == "ping":
                await websocket.send_json({"type": "pong"})

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {call_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        is_connected = False
        if agent:
            await agent.stop()
        if call_id in active_connections:
            del active_connections[call_id]


@router.get("/health")
async def voice_health():
    """Health check for voice service"""
    return {
        "status": "ok",
        "service": "voice_agent",
        "active_calls": len(active_connections)
    }


@router.get("/active-calls")
async def get_active_calls():
    """Get list of active call IDs"""
    return {
        "calls": list(active_connections.keys()),
        "count": len(active_connections)
    }
