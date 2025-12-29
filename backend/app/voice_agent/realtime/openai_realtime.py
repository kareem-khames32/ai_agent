"""
OpenAI Realtime API Agent
Native speech-to-speech with GPT-4o Realtime
"""
import asyncio
import json
import base64
import websockets
from typing import Optional, Callable, Awaitable
from enum import Enum

from ..utils.logger import get_logger
from ..prompts import build_system_prompt

logger = get_logger(__name__)


class RealtimeState(Enum):
    """OpenAI Realtime connection states"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    LISTENING = "listening"
    SPEAKING = "speaking"


class OpenAIRealtimeAgent:
    """
    OpenAI Realtime API Agent

    Direct speech-to-speech using GPT-4o Realtime API.
    Features:
    - Native audio input/output (no separate STT/TTS)
    - ~300ms end-to-end latency
    - Function calling support
    - Automatic turn detection
    """

    REALTIME_URL = "wss://api.openai.com/v1/realtime"

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-realtime-preview-2024-12-17",
        voice: str = "alloy",
        system_prompt: str = "",
        call_id: Optional[str] = None,
        language: str = "ar",
        max_tokens: int = 200,
    ):
        self.api_key = api_key
        self.model = model
        self.voice = voice
        self.call_id = call_id or "realtime"
        self.language = language
        self.max_tokens = max_tokens

        # Build system prompt with internal voice call instructions
        self.system_prompt = build_system_prompt(system_prompt, language=language)

        self.state = RealtimeState.DISCONNECTED
        self._ws: Optional[websockets.WebSocketClientProtocol] = None
        self._is_running = False
        self._receive_task: Optional[asyncio.Task] = None

        # Callbacks
        self.on_audio_output: Optional[Callable[[bytes], Awaitable[None]]] = None
        self.on_transcript: Optional[Callable[[str, str], Awaitable[None]]] = None  # text, role
        self.on_state_change: Optional[Callable[[RealtimeState], Awaitable[None]]] = None
        self.on_error: Optional[Callable[[str], Awaitable[None]]] = None

        # Audio settings
        self.input_audio_format = "pcm16"  # 24kHz 16-bit PCM
        self.output_audio_format = "pcm16"

        logger.info(f"🎙️ OpenAI Realtime Agent created (model={model}, voice={voice})")

    async def connect(self) -> bool:
        """Connect to OpenAI Realtime API"""
        try:
            self.state = RealtimeState.CONNECTING

            url = f"{self.REALTIME_URL}?model={self.model}"
            headers = [
                ("Authorization", f"Bearer {self.api_key}"),
                ("OpenAI-Beta", "realtime=v1"),
            ]

            logger.info(f"🔌 Connecting to OpenAI Realtime API...")

            # Use additional_headers for newer websockets, fallback to older syntax
            try:
                self._ws = await websockets.connect(url, additional_headers=headers)
            except TypeError:
                # Older websockets version
                self._ws = await websockets.connect(url, extra_headers=dict(headers))

            # Configure the session
            await self._configure_session()

            # Start receiving messages
            self._is_running = True
            self._receive_task = asyncio.create_task(self._receive_loop())

            self.state = RealtimeState.CONNECTED
            logger.info(f"✅ Connected to OpenAI Realtime API")

            return True

        except Exception as e:
            logger.error(f"Failed to connect to OpenAI Realtime: {e}")
            self.state = RealtimeState.DISCONNECTED
            return False

    async def _configure_session(self):
        """Configure the realtime session"""
        config = {
            "type": "session.update",
            "session": {
                "modalities": ["text", "audio"],
                "instructions": self.system_prompt,
                "voice": self.voice,
                "input_audio_format": self.input_audio_format,
                "output_audio_format": self.output_audio_format,
                "input_audio_transcription": {
                    "model": "whisper-1"
                },
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.5,
                    "prefix_padding_ms": 300,
                    "silence_duration_ms": 500,
                },
                "max_response_output_tokens": self.max_tokens,
            }
        }

        await self._ws.send(json.dumps(config))
        logger.info(f"📋 Session configured (voice={self.voice}, max_tokens={self.max_tokens})")

    async def _receive_loop(self):
        """Receive and process messages from OpenAI"""
        try:
            async for message in self._ws:
                if not self._is_running:
                    break

                try:
                    event = json.loads(message)
                    await self._handle_event(event)
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON from OpenAI: {message[:100]}")

        except websockets.exceptions.ConnectionClosed:
            logger.info("OpenAI Realtime connection closed")
        except Exception as e:
            logger.error(f"Receive loop error: {e}")
        finally:
            self.state = RealtimeState.DISCONNECTED

    async def _handle_event(self, event: dict):
        """Handle events from OpenAI Realtime API"""
        event_type = event.get("type", "")

        if event_type == "session.created":
            logger.info(f"✅ Session created: {event.get('session', {}).get('id', 'unknown')}")

        elif event_type == "session.updated":
            logger.debug("Session updated")

        elif event_type == "input_audio_buffer.speech_started":
            logger.debug("🎤 User speech started")
            self.state = RealtimeState.LISTENING
            if self.on_state_change:
                await self.on_state_change(self.state)

        elif event_type == "input_audio_buffer.speech_stopped":
            logger.debug("🎤 User speech stopped")

        elif event_type == "input_audio_buffer.committed":
            logger.debug("Audio buffer committed")

        elif event_type == "conversation.item.input_audio_transcription.completed":
            # User's speech transcribed
            transcript = event.get("transcript", "")
            if transcript and self.on_transcript:
                await self.on_transcript(transcript, "user")
            logger.info(f"📝 User: {transcript}")

        elif event_type == "response.created":
            logger.debug("Response created")
            self.state = RealtimeState.SPEAKING
            if self.on_state_change:
                await self.on_state_change(self.state)

        elif event_type == "response.audio.delta":
            # Audio chunk from assistant
            audio_b64 = event.get("delta", "")
            if audio_b64 and self.on_audio_output:
                audio_bytes = base64.b64decode(audio_b64)
                await self.on_audio_output(audio_bytes)

        elif event_type == "response.audio_transcript.delta":
            # Partial transcript of assistant's response
            transcript = event.get("delta", "")
            # Don't log partial transcripts to reduce noise

        elif event_type == "response.audio_transcript.done":
            # Complete transcript of assistant's response
            transcript = event.get("transcript", "")
            if transcript and self.on_transcript:
                await self.on_transcript(transcript, "assistant")
            logger.info(f"🤖 Assistant: {transcript}")

        elif event_type == "response.done":
            logger.debug("Response complete")
            self.state = RealtimeState.CONNECTED
            if self.on_state_change:
                await self.on_state_change(self.state)

        elif event_type == "error":
            error = event.get("error", {})
            error_msg = error.get("message", "Unknown error")
            logger.error(f"❌ OpenAI Realtime error: {error_msg}")
            if self.on_error:
                await self.on_error(error_msg)

        elif event_type.startswith("rate_limits"):
            # Rate limit info, just log
            logger.debug(f"Rate limits: {event}")

        else:
            logger.debug(f"Unhandled event: {event_type}")

    async def send_audio(self, audio_chunk: bytes):
        """Send audio chunk to OpenAI Realtime API"""
        if not self._ws or self.state == RealtimeState.DISCONNECTED:
            return

        # Convert to base64
        audio_b64 = base64.b64encode(audio_chunk).decode()

        event = {
            "type": "input_audio_buffer.append",
            "audio": audio_b64,
        }

        try:
            await self._ws.send(json.dumps(event))
        except Exception as e:
            logger.error(f"Failed to send audio: {e}")

    async def interrupt(self):
        """Interrupt the current response (barge-in)"""
        if not self._ws:
            return

        event = {
            "type": "response.cancel",
        }

        try:
            await self._ws.send(json.dumps(event))
            logger.info("⚠️ Response cancelled (barge-in)")
        except Exception as e:
            logger.error(f"Failed to cancel response: {e}")

    async def send_text(self, text: str):
        """Send text message (for testing or hybrid mode)"""
        if not self._ws:
            return

        event = {
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": text}]
            }
        }

        await self._ws.send(json.dumps(event))

        # Trigger response
        await self._ws.send(json.dumps({"type": "response.create"}))

    async def close(self):
        """Close the connection"""
        self._is_running = False

        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass

        if self._ws:
            await self._ws.close()

        self.state = RealtimeState.DISCONNECTED
        logger.info("🔌 OpenAI Realtime connection closed")

    @property
    def is_connected(self) -> bool:
        return self.state != RealtimeState.DISCONNECTED
