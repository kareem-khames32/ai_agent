"""
Voice API routes - WebSocket for real-time audio streaming
"""
import asyncio
import base64
import json
import time
from typing import Optional, Dict, Any
from uuid import UUID, uuid4
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from loguru import logger

from app.core.database import get_db
from app.services.pipeline import VoicePipeline, PipelineConfig, pipeline_manager
from app.services.stt import STTService
from app.services.llm import LLMService
from app.services.tts import TTSService

router = APIRouter()


# Store active connections
active_connections: Dict[str, WebSocket] = {}


@router.websocket("/ws/{call_id}")
async def voice_websocket(
    websocket: WebSocket,
    call_id: str,
):
    """
    WebSocket endpoint for real-time voice conversation

    Protocol:
    Client sends:
    - {"type": "config", "data": {...}} - Configure pipeline
    - {"type": "audio", "data": "<base64_audio>"} - Audio chunk
    - {"type": "interrupt"} - Interrupt current response
    - {"type": "end"} - End conversation

    Server sends:
    - {"type": "ready"} - Pipeline ready
    - {"type": "transcript", "role": "user", "text": "..."} - User speech
    - {"type": "transcript", "role": "assistant", "text": "..."} - Assistant text
    - {"type": "audio", "data": "<base64_audio>"} - Audio response
    - {"type": "latency", "data": {...}} - Latency metrics
    - {"type": "error", "message": "..."} - Error message
    """
    await websocket.accept()
    active_connections[call_id] = websocket
    logger.info(f"WebSocket connected: {call_id}")

    pipeline: Optional[VoicePipeline] = None

    try:
        while True:
            # Receive message
            data = await websocket.receive_text()
            message = json.loads(data)
            msg_type = message.get("type")

            if msg_type == "config":
                # Configure pipeline
                config_data = message.get("data", {})
                config = PipelineConfig(
                    stt_provider=config_data.get("stt_provider", "deepgram"),
                    stt_api_key=config_data.get("stt_api_key"),
                    stt_region=config_data.get("stt_region"),
                    stt_language=config_data.get("language", "ar"),
                    llm_provider=config_data.get("llm_provider", "anthropic"),
                    llm_api_key=config_data.get("llm_api_key"),
                    llm_model=config_data.get("llm_model"),
                    tts_provider=config_data.get("tts_provider", "elevenlabs"),
                    tts_api_key=config_data.get("tts_api_key"),
                    tts_region=config_data.get("tts_region"),
                    tts_voice_id=config_data.get("tts_voice_id"),
                    system_prompt=config_data.get("system_prompt", "أنت مساعد صوتي ذكي. تتحدث العربية بطلاقة. كن مختصراً ومفيداً."),
                    max_tokens=config_data.get("max_tokens", 300),
                    temperature=config_data.get("temperature", 0.7),
                )

                pipeline = pipeline_manager.create_pipeline(call_id, config)
                await websocket.send_json({"type": "ready"})
                logger.info(f"Pipeline configured for {call_id}")

            elif msg_type == "audio":
                if not pipeline:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Pipeline not configured. Send config first."
                    })
                    continue

                # Decode audio
                audio_b64 = message.get("data", "")
                audio_data = base64.b64decode(audio_b64)

                sample_rate = message.get("sample_rate", 16000)
                encoding = message.get("encoding", "linear16")

                # Process audio through pipeline
                try:
                    result = await pipeline.process_audio(
                        audio_data,
                        sample_rate=sample_rate,
                        encoding=encoding,
                    )

                    # Send user transcript
                    if result.get("user_text"):
                        await websocket.send_json({
                            "type": "transcript",
                            "role": "user",
                            "text": result["user_text"],
                        })

                    # Send assistant transcript
                    if result.get("assistant_text"):
                        await websocket.send_json({
                            "type": "transcript",
                            "role": "assistant",
                            "text": result["assistant_text"],
                        })

                    # Send audio response
                    if result.get("audio"):
                        audio_b64 = base64.b64encode(result["audio"]).decode()
                        await websocket.send_json({
                            "type": "audio",
                            "data": audio_b64,
                        })

                    # Send latency metrics
                    if result.get("latency"):
                        await websocket.send_json({
                            "type": "latency",
                            "data": result["latency"],
                        })

                except Exception as e:
                    logger.error(f"Pipeline error: {e}")
                    await websocket.send_json({
                        "type": "error",
                        "message": str(e),
                    })

            elif msg_type == "audio_stream":
                # Streaming mode - process and stream response
                if not pipeline:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Pipeline not configured"
                    })
                    continue

                audio_b64 = message.get("data", "")
                audio_data = base64.b64decode(audio_b64)

                async for audio_chunk in pipeline.process_audio_stream(
                    audio_data,
                    on_text=lambda t: asyncio.create_task(
                        websocket.send_json({"type": "text_chunk", "data": t})
                    ),
                ):
                    chunk_b64 = base64.b64encode(audio_chunk).decode()
                    await websocket.send_json({
                        "type": "audio_chunk",
                        "data": chunk_b64,
                    })

                await websocket.send_json({"type": "stream_end"})

            elif msg_type == "interrupt":
                if pipeline:
                    pipeline.interrupt()
                    await websocket.send_json({"type": "interrupted"})

            elif msg_type == "reset":
                if pipeline:
                    pipeline.reset()
                    await websocket.send_json({"type": "reset_complete"})

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
        # Cleanup
        if call_id in active_connections:
            del active_connections[call_id]
        pipeline_manager.remove_pipeline(call_id)


@router.post("/test")
async def test_voice_pipeline(
    text: str = Query(..., description="Text to process"),
    stt_provider: str = Query("deepgram"),
    stt_api_key: Optional[str] = Query(None),
    llm_provider: str = Query("anthropic"),
    llm_api_key: Optional[str] = Query(None),
    tts_provider: str = Query("elevenlabs"),
    tts_api_key: Optional[str] = Query(None),
):
    """Test the voice pipeline with text input (for debugging)"""
    from app.services.llm import Message

    # Test LLM
    llm = LLMService(provider=llm_provider, api_key=llm_api_key)
    response = await llm.generate(
        messages=[Message(role="user", content=text)],
        system_prompt="أنت مساعد صوتي. كن مختصراً.",
    )

    # Test TTS
    tts = TTSService(provider=tts_provider, api_key=tts_api_key)
    audio = await tts.synthesize(response.text)

    return Response(
        content=audio,
        media_type="audio/mpeg",
        headers={"X-Assistant-Text": response.text},
    )


@router.post("/stt/test")
async def test_stt(
    audio_base64: str,
    provider: str = Query("deepgram"),
    api_key: Optional[str] = Query(None),
    language: str = Query("ar"),
):
    """Test Speech-to-Text"""
    audio_data = base64.b64decode(audio_base64)

    stt = STTService(provider=provider, api_key=api_key, language=language)
    result = await stt.transcribe(audio_data)

    return {
        "text": result.text,
        "confidence": result.confidence,
        "language": result.language,
    }


@router.post("/tts/test")
async def test_tts(
    text: str,
    provider: str = Query("elevenlabs"),
    api_key: Optional[str] = Query(None),
    voice_id: Optional[str] = Query(None),
):
    """Test Text-to-Speech"""
    tts = TTSService(provider=provider, api_key=api_key, voice_id=voice_id)
    audio = await tts.synthesize(text)

    return Response(
        content=audio,
        media_type="audio/mpeg",
    )


@router.get("/voices/{provider}")
async def list_voices(provider: str):
    """List available voices for a provider"""
    tts = TTSService(provider=provider)
    return {"voices": tts.list_voices()}
