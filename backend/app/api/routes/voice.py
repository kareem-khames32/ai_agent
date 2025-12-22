"""
Voice API routes - WebSocket for real-time audio streaming
Supports both Pipeline mode (STT→LLM→TTS) and Realtime API mode
"""
import asyncio
import base64
import json
import time
import os
from typing import Optional, Dict, Any, Union
from uuid import uuid4
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends, Query
from fastapi.responses import Response
from starlette.websockets import WebSocketState
from loguru import logger

from app.voice_agent import VoiceAgent, VoiceAgentConfig, get_config, create_config_from_assistant, AgentState
from app.voice_agent.realtime import OpenAIRealtimeAgent, GoogleGeminiLiveAgent, GroqFastAgent

router = APIRouter()


# Store active connections
active_connections: Dict[str, WebSocket] = {}


@router.websocket("/ws")
async def voice_agent_websocket(
    websocket: WebSocket,
    assistant_id: Optional[str] = Query(None)
):
    """
    WebSocket endpoint for real-time voice conversation

    Supports two modes:
    1. Pipeline mode (default): STT → LLM → TTS with smart turn detection
    2. Realtime mode: Native speech-to-speech APIs (OpenAI, Google, Groq)

    Protocol:
    Client sends:
    - {"type": "config", "voice_mode": "pipeline|realtime", "realtime_provider": "openai|google|groq", ...}
    - {"type": "audio", "data": "<base64 PCM 16kHz mono>"}
    - {"type": "stop"} - End conversation

    Server sends:
    - {"type": "ready", "call_id": "...", "mode": "pipeline|realtime"} - Agent ready
    - {"type": "audio", "data": "<base64 PCM>"} - Audio output
    - {"type": "transcript", "text": "...", "role": "user|assistant"} - Transcripts
    - {"type": "state", "state": "listening|processing|speaking"}
    - {"type": "error", "message": "..."} - Error message
    """
    await websocket.accept()
    call_id = str(uuid4())[:8]
    active_connections[call_id] = websocket
    logger.info(f"🔌 Voice WebSocket connected: {call_id}")

    is_connected = True
    voice_mode = "pipeline"
    agent: Optional[Union[VoiceAgent, OpenAIRealtimeAgent, GoogleGeminiLiveAgent, GroqFastAgent]] = None

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

    async def send_transcript_pipeline(text: str, is_final: bool):
        """Send transcript to client (pipeline mode)"""
        if not is_connected:
            return
        try:
            await websocket.send_json({
                "type": "transcript",
                "text": text,
                "is_final": is_final,
                "role": "user"
            })
        except Exception as e:
            logger.error(f"Send transcript error: {e}")

    async def send_transcript_realtime(text: str, role: str):
        """Send transcript to client (realtime mode)"""
        if not is_connected:
            return
        try:
            await websocket.send_json({
                "type": "transcript",
                "text": text,
                "role": role,
                "is_final": True
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

    async def send_state(state):
        """Send state change to client"""
        if not is_connected:
            return
        try:
            state_value = state.value if hasattr(state, 'value') else str(state)
            await websocket.send_json({
                "type": "state",
                "state": state_value
            })
        except Exception as e:
            logger.error(f"Send state error: {e}")

    try:
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
                    assistant_data = data.get("assistant")
                    credentials = data.get("credentials", {})

                    # Check voice mode
                    voice_mode = data.get("voice_mode", "pipeline")
                    if assistant_data:
                        voice_mode = assistant_data.get("voice_mode", "pipeline")

                    logger.info(f"📋 Voice mode: {voice_mode}")

                    if voice_mode == "realtime":
                        # Realtime mode - use native APIs
                        realtime_provider = assistant_data.get("realtime_provider", "openai") if assistant_data else "openai"
                        realtime_model = assistant_data.get("realtime_model", "") if assistant_data else ""
                        realtime_voice = assistant_data.get("realtime_voice", "alloy") if assistant_data else "alloy"

                        agent = await _create_realtime_agent(
                            provider=realtime_provider,
                            model=realtime_model,
                            voice=realtime_voice,
                            system_prompt=system_prompt,
                            credentials=credentials,
                            call_id=call_id
                        )

                        if agent:
                            # Set up realtime callbacks
                            agent.on_audio_output = send_audio
                            agent.on_transcript = send_transcript_realtime
                            agent.on_state_change = send_state
                            agent.on_error = lambda msg: websocket.send_json({"type": "error", "message": msg})

                            # Connect to realtime API
                            connected = await agent.connect()
                            if not connected:
                                raise Exception(f"Failed to connect to {realtime_provider} Realtime API")

                            logger.info(f"🎙️ Realtime agent ready: {realtime_provider}")
                        else:
                            raise Exception(f"Failed to create realtime agent for {realtime_provider}")

                    else:
                        # Pipeline mode - use VoiceAgent
                        if assistant_data:
                            config = create_config_from_assistant(assistant_data, credentials)
                            logger.info(f"📋 Config from assistant: LLM={config.llm_provider}/{config.llm_model}, TTS={config.tts_provider}, STT={config.stt_provider}")
                        else:
                            config = get_config()
                            logger.info(f"📋 Using default config")

                        agent = VoiceAgent(config, call_id)
                        agent.on_audio_output = send_audio
                        agent.on_transcript = send_transcript_pipeline
                        agent.on_response = send_response
                        agent.on_state_change = send_state

                        await agent.start(system_prompt)

                    config_received = True

                elif data.get("type") == "audio":
                    # Audio before config, start with default pipeline
                    config = get_config()
                    agent = VoiceAgent(config, call_id)
                    agent.on_audio_output = send_audio
                    agent.on_transcript = send_transcript_pipeline
                    agent.on_response = send_response
                    agent.on_state_change = send_state
                    await agent.start()
                    config_received = True

            except asyncio.TimeoutError:
                logger.warning("Config timeout, using default pipeline")
                config = get_config()
                agent = VoiceAgent(config, call_id)
                agent.on_audio_output = send_audio
                agent.on_transcript = send_transcript_pipeline
                agent.on_response = send_response
                agent.on_state_change = send_state
                await agent.start()
                config_received = True

        # Send ready message
        await websocket.send_json({
            "type": "ready",
            "call_id": call_id,
            "mode": voice_mode
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
                    if audio_b64 and agent:
                        audio_bytes = base64.b64decode(audio_b64)
                        if voice_mode == "realtime":
                            await agent.send_audio(audio_bytes)
                        else:
                            await agent.process_audio(audio_bytes)

                elif msg_type == "interrupt":
                    # Barge-in / interrupt
                    if agent and hasattr(agent, 'interrupt'):
                        await agent.interrupt()

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
            if hasattr(agent, 'stop'):
                await agent.stop()
            elif hasattr(agent, 'close'):
                await agent.close()

        if call_id in active_connections:
            del active_connections[call_id]

        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.close()
        except:
            pass

        logger.info(f"🔌 Voice WebSocket cleanup complete: {call_id}")


async def _create_realtime_agent(
    provider: str,
    model: str,
    voice: str,
    system_prompt: str,
    credentials: Dict[str, Any],
    call_id: str
) -> Optional[Union[OpenAIRealtimeAgent, GoogleGeminiLiveAgent, GroqFastAgent]]:
    """Create the appropriate realtime agent based on provider"""

    if provider == "openai":
        api_key = credentials.get("openai_api_key") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.error("OpenAI API key not found")
            return None

        return OpenAIRealtimeAgent(
            api_key=api_key,
            model=model or "gpt-4o-realtime-preview-2024-12-17",
            voice=voice or "alloy",
            system_prompt=system_prompt,
            call_id=call_id
        )

    elif provider == "google":
        api_key = credentials.get("google_api_key") or os.getenv("GOOGLE_API_KEY")
        if not api_key:
            logger.error("Google API key not found")
            return None

        return GoogleGeminiLiveAgent(
            api_key=api_key,
            model=model or "gemini-2.0-flash-exp",
            voice=voice or "Aoede",
            system_prompt=system_prompt,
            call_id=call_id
        )

    elif provider == "groq":
        api_key = credentials.get("groq_api_key") or os.getenv("GROQ_API_KEY")
        if not api_key:
            logger.error("Groq API key not found")
            return None

        # Groq needs a TTS provider for audio output
        tts_api_key = credentials.get("openai_api_key") or os.getenv("OPENAI_API_KEY")

        return GroqFastAgent(
            api_key=api_key,
            model=model or "llama-3.3-70b-versatile",
            voice=voice or "alloy",
            system_prompt=system_prompt,
            call_id=call_id,
            tts_provider="openai",
            tts_api_key=tts_api_key
        )

    else:
        logger.error(f"Unknown realtime provider: {provider}")
        return None


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
