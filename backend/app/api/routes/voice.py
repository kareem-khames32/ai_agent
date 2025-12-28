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
from app.voice_agent.call_recorder import CallRecorder, call_log_storage

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

    # Initialize call recorder
    recorder = CallRecorder(call_id)

    async def send_audio(audio_chunk: bytes):
        """Send audio to client and record"""
        if not is_connected:
            return
        try:
            # Record assistant audio
            recorder.record_assistant_audio(audio_chunk)

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
            # Record transcript
            if is_final:
                recorder.add_transcript(text, "user", is_final)
                recorder.mark_user_speech_end()

            await websocket.send_json({
                "type": "transcript",
                "text": text,
                "is_final": is_final,
                "role": "user",
                "timestamp": time.time() - recorder._start_time
            })
        except Exception as e:
            logger.error(f"Send transcript error: {e}")

    async def send_transcript_realtime(text: str, role: str):
        """Send transcript to client (realtime mode)"""
        if not is_connected:
            return
        try:
            # Record transcript
            recorder.add_transcript(text, role, True)
            if role == "user":
                recorder.mark_user_speech_end()
            elif role == "assistant":
                recorder.mark_response_start()

            await websocket.send_json({
                "type": "transcript",
                "text": text,
                "role": role,
                "is_final": True,
                "timestamp": time.time() - recorder._start_time
            })

            # Send updated metrics after each transcript
            await send_live_metrics()
        except Exception as e:
            logger.error(f"Send transcript error: {e}")

    async def send_live_metrics():
        """Send live metrics to client"""
        if not is_connected:
            return
        try:
            # Calculate current metrics
            duration = time.time() - recorder._start_time
            avg_latency = sum(recorder._latencies) / len(recorder._latencies) if recorder._latencies else 0
            last_latency = recorder._latencies[-1] if recorder._latencies else 0

            # Calculate live cost estimate
            recorder._calculate_cost()

            await websocket.send_json({
                "type": "metrics",
                "duration_sec": round(duration, 1),
                "response_count": recorder._metrics.response_count,
                "avg_latency_ms": round(avg_latency, 0),
                "last_latency_ms": round(last_latency, 0),
                "cost": {
                    "total": round(recorder._cost.total_cost, 4),
                    "stt": round(recorder._cost.stt_cost, 4),
                    "llm": round(recorder._cost.llm_cost, 4),
                    "tts": round(recorder._cost.tts_cost, 4),
                },
                "tokens": {
                    "input": recorder._metrics.input_tokens,
                    "output": recorder._metrics.output_tokens,
                }
            })
        except Exception as e:
            logger.error(f"Send metrics error: {e}")

    async def send_response(text: str):
        """Send AI response to client"""
        if not is_connected:
            return
        try:
            # Record assistant response
            recorder.add_transcript(text, "assistant", True)
            recorder.mark_response_start()

            await websocket.send_json({
                "type": "response",
                "text": text,
                "timestamp": time.time() - recorder._start_time
            })

            # Send updated metrics
            await send_live_metrics()
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

                        # Get language and max_tokens from assistant data
                        language = assistant_data.get("transcriber_language", "ar") if assistant_data else "ar"
                        max_tokens = assistant_data.get("max_tokens", 200) if assistant_data else 200

                        # Configure recorder for realtime mode
                        recorder.set_config(
                            voice_mode="realtime",
                            realtime_provider=realtime_provider,
                            llm_model=realtime_model,
                            voice_id=realtime_voice,
                            language=language,
                            assistant_id=assistant_data.get("id") if assistant_data else None,
                            assistant_name=assistant_data.get("name") if assistant_data else None,
                        )

                        agent = await _create_realtime_agent(
                            provider=realtime_provider,
                            model=realtime_model,
                            voice=realtime_voice,
                            system_prompt=system_prompt,
                            credentials=credentials,
                            call_id=call_id,
                            language=language,
                            max_tokens=max_tokens,
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

                            # Configure recorder for pipeline mode
                            recorder.set_config(
                                voice_mode="pipeline",
                                llm_provider=config.llm_provider,
                                llm_model=config.llm_model,
                                stt_provider=config.stt_provider,
                                tts_provider=config.tts_provider,
                                voice_id=config.tts_voice,
                                language=config.language,
                                assistant_id=assistant_data.get("id"),
                                assistant_name=assistant_data.get("name"),
                            )
                        else:
                            config = get_config()
                            logger.info(f"📋 Using default config")
                            recorder.set_config(voice_mode="pipeline")

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

                        # Record user audio
                        recorder.record_user_audio(audio_bytes)

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

        # Save call log
        try:
            call_log = recorder.finish(end_reason="user_hangup")
            call_log_storage.save(call_log)
            logger.info(f"💾 Call log saved: {call_id}")
        except Exception as e:
            logger.error(f"Failed to save call log: {e}")

        if call_id in active_connections:
            del active_connections[call_id]

        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.close()
        except:
            pass

        logger.info(f"🔌 Voice WebSocket cleanup complete: {call_id}")


def _get_api_key(credentials: Dict[str, Any], provider: str, env_var: str) -> Optional[str]:
    """Get API key from nested credentials structure or environment"""
    # Try nested structure: {"google": {"api_key": "..."}}
    if provider in credentials:
        provider_creds = credentials[provider]
        if isinstance(provider_creds, dict):
            return provider_creds.get("api_key") or provider_creds.get("key")

    # Try flat structure: {"google_api_key": "..."}
    flat_key = f"{provider}_api_key"
    if flat_key in credentials:
        return credentials[flat_key]

    # Fall back to environment variable
    return os.getenv(env_var)


async def _create_realtime_agent(
    provider: str,
    model: str,
    voice: str,
    system_prompt: str,
    credentials: Dict[str, Any],
    call_id: str,
    language: str = "ar",
    max_tokens: int = 200,
) -> Optional[Union[OpenAIRealtimeAgent, GoogleGeminiLiveAgent, GroqFastAgent]]:
    """Create the appropriate realtime agent based on provider"""

    logger.debug(f"Creating realtime agent: provider={provider}, language={language}, max_tokens={max_tokens}")

    if provider == "openai":
        api_key = _get_api_key(credentials, "openai", "OPENAI_API_KEY")
        if not api_key:
            logger.error("OpenAI API key not found")
            return None

        return OpenAIRealtimeAgent(
            api_key=api_key,
            model=model or "gpt-4o-realtime-preview-2024-12-17",
            voice=voice or "alloy",
            system_prompt=system_prompt,
            call_id=call_id,
            language=language,
            max_tokens=max_tokens,
        )

    elif provider == "google":
        api_key = _get_api_key(credentials, "google", "GOOGLE_API_KEY")
        if not api_key:
            logger.error("Google API key not found")
            return None

        logger.info(f"🔗 Creating Google Gemini Live agent with key: {api_key[:10]}...")
        return GoogleGeminiLiveAgent(
            api_key=api_key,
            model=model or "gemini-2.0-flash-exp",
            voice=voice or "Aoede",
            system_prompt=system_prompt,
            call_id=call_id,
            language=language,
            max_tokens=max_tokens,
        )

    elif provider == "groq":
        api_key = _get_api_key(credentials, "groq", "GROQ_API_KEY")
        if not api_key:
            logger.error("Groq API key not found")
            return None

        # Groq needs a TTS provider for audio output
        tts_api_key = _get_api_key(credentials, "openai", "OPENAI_API_KEY")

        return GroqFastAgent(
            api_key=api_key,
            model=model or "llama-3.3-70b-versatile",
            voice=voice or "alloy",
            system_prompt=system_prompt,
            call_id=call_id,
            tts_provider="openai",
            tts_api_key=tts_api_key,
            language=language,
            max_tokens=max_tokens,
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
