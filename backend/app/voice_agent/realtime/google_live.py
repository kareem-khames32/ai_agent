"""
Google Gemini Live API Agent
Multimodal live streaming with Gemini 2.0
"""
import asyncio
import json
import base64
from typing import Optional, Callable, Awaitable
from enum import Enum

from ..utils.logger import get_logger
from ..prompts import build_system_prompt

logger = get_logger(__name__)


class GeminiLiveState(Enum):
    """Gemini Live connection states"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    LISTENING = "listening"
    SPEAKING = "speaking"


class GoogleGeminiLiveAgent:
    """
    Google Gemini Live API Agent

    Multimodal live streaming using Gemini 2.0.
    Features:
    - Real-time audio input/output
    - Multimodal understanding (audio + context)
    - Low latency responses
    - Native function calling
    """

    # Gemini Live uses WebSocket for streaming
    # Use v1beta for Live API support
    LIVE_URL = "wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent"

    # Models that support Live API (bidiGenerateContent)
    # Note: Thinking models do NOT support Live API
    SUPPORTED_MODELS = [
        "gemini-2.0-flash-exp",
        "gemini-2.0-flash-live-001",
        "gemini-2.5-flash-preview-native-audio",
    ]

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.0-flash-exp",
        voice: str = "Aoede",
        system_prompt: str = "",
        call_id: Optional[str] = None,
        language: str = "ar",
        max_tokens: int = 200,
    ):
        self.api_key = api_key
        self.model = model
        self.voice = voice
        self.call_id = call_id or "gemini-live"
        self.language = language
        self.max_tokens = max_tokens

        # Build system prompt with internal voice call instructions
        self.system_prompt = build_system_prompt(system_prompt, language=language)

        self.state = GeminiLiveState.DISCONNECTED
        self._ws = None
        self._is_running = False
        self._receive_task: Optional[asyncio.Task] = None

        # Callbacks
        self.on_audio_output: Optional[Callable[[bytes], Awaitable[None]]] = None
        self.on_transcript: Optional[Callable[[str, str], Awaitable[None]]] = None
        self.on_state_change: Optional[Callable[[GeminiLiveState], Awaitable[None]]] = None
        self.on_error: Optional[Callable[[str], Awaitable[None]]] = None

        # Audio settings - Gemini uses 16kHz PCM
        self.sample_rate = 16000
        self.channels = 1

        logger.info(f"🎙️ Google Gemini Live Agent created (model={model}, voice={voice})")

    async def connect(self) -> bool:
        """Connect to Gemini Live API"""
        try:
            import websockets

            self.state = GeminiLiveState.CONNECTING

            # Validate model - thinking models don't support Live API
            if "thinking" in self.model.lower():
                logger.warning(f"⚠️ Model {self.model} does not support Live API. Using gemini-2.0-flash-exp instead.")
                self.model = "gemini-2.0-flash-exp"

            # Check if model is in supported list
            model_supported = any(supported in self.model for supported in self.SUPPORTED_MODELS)
            if not model_supported:
                logger.warning(f"⚠️ Model {self.model} may not support Live API. Trying anyway...")

            # Build WebSocket URL with API key
            url = f"{self.LIVE_URL}?key={self.api_key}"

            logger.info(f"🔌 Connecting to Gemini Live API (model={self.model})...")
            self._ws = await websockets.connect(url)

            # Send setup message
            await self._configure_session()

            # Start receiving messages
            self._is_running = True
            self._receive_task = asyncio.create_task(self._receive_loop())

            self.state = GeminiLiveState.CONNECTED
            logger.info(f"✅ Connected to Gemini Live API")

            return True

        except Exception as e:
            logger.error(f"Failed to connect to Gemini Live: {e}")
            self.state = GeminiLiveState.DISCONNECTED
            return False

    async def _configure_session(self):
        """Configure the Gemini Live session"""
        # Setup message for Gemini Live
        setup_message = {
            "setup": {
                "model": f"models/{self.model}",
                "generation_config": {
                    "response_modalities": ["AUDIO"],
                    "speech_config": {
                        "voice_config": {
                            "prebuilt_voice_config": {
                                "voice_name": self.voice
                            }
                        }
                    }
                },
                "system_instruction": {
                    "parts": [{"text": self.system_prompt}]
                } if self.system_prompt else None
            }
        }

        # Remove None values
        if setup_message["setup"]["system_instruction"] is None:
            del setup_message["setup"]["system_instruction"]

        await self._ws.send(json.dumps(setup_message))
        logger.info(f"📋 Gemini session configured (voice={self.voice})")

    async def _receive_loop(self):
        """Receive and process messages from Gemini"""
        import websockets

        try:
            async for message in self._ws:
                if not self._is_running:
                    break

                try:
                    event = json.loads(message)
                    await self._handle_event(event)
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON from Gemini: {message[:100]}")

        except websockets.exceptions.ConnectionClosed:
            logger.info("Gemini Live connection closed")
        except Exception as e:
            logger.error(f"Receive loop error: {e}")
        finally:
            self.state = GeminiLiveState.DISCONNECTED

    async def _handle_event(self, event: dict):
        """Handle events from Gemini Live API"""

        # Check for setup complete
        if "setupComplete" in event:
            logger.info("✅ Gemini Live setup complete")
            return

        # Check for server content (audio/text response)
        if "serverContent" in event:
            content = event["serverContent"]

            # Check if model is speaking
            model_turn = content.get("modelTurn", {})
            parts = model_turn.get("parts", [])

            for part in parts:
                # Handle audio output
                if "inlineData" in part:
                    inline_data = part["inlineData"]
                    if inline_data.get("mimeType", "").startswith("audio/"):
                        audio_b64 = inline_data.get("data", "")
                        if audio_b64 and self.on_audio_output:
                            audio_bytes = base64.b64decode(audio_b64)
                            await self.on_audio_output(audio_bytes)

                            # Update state to speaking
                            if self.state != GeminiLiveState.SPEAKING:
                                self.state = GeminiLiveState.SPEAKING
                                if self.on_state_change:
                                    await self.on_state_change(self.state)

                # Handle text response
                if "text" in part:
                    text = part["text"]
                    if text and self.on_transcript:
                        await self.on_transcript(text, "assistant")
                    logger.info(f"🤖 Gemini: {text}")

            # Check if turn is complete
            if content.get("turnComplete", False):
                self.state = GeminiLiveState.CONNECTED
                if self.on_state_change:
                    await self.on_state_change(self.state)
                logger.debug("Turn complete")

            # Check for interrupted
            if content.get("interrupted", False):
                logger.info("⚠️ Response interrupted (barge-in)")

        # Check for tool calls
        if "toolCall" in event:
            tool_call = event["toolCall"]
            logger.info(f"🔧 Tool call: {tool_call}")
            # Handle tool calls here if needed

        # Check for errors
        if "error" in event:
            error = event["error"]
            error_msg = error.get("message", "Unknown error")
            logger.error(f"❌ Gemini Live error: {error_msg}")
            if self.on_error:
                await self.on_error(error_msg)

    async def send_audio(self, audio_chunk: bytes):
        """Send audio chunk to Gemini Live API"""
        if not self._ws or self.state == GeminiLiveState.DISCONNECTED:
            return

        # Convert to base64
        audio_b64 = base64.b64encode(audio_chunk).decode()

        # Gemini Live real-time input format
        message = {
            "realtimeInput": {
                "mediaChunks": [{
                    "mimeType": "audio/pcm;rate=16000",
                    "data": audio_b64
                }]
            }
        }

        try:
            await self._ws.send(json.dumps(message))
        except Exception as e:
            logger.error(f"Failed to send audio: {e}")

    async def interrupt(self):
        """Interrupt the current response (barge-in)"""
        if not self._ws:
            return

        # Gemini uses client content interrupt
        message = {
            "clientContent": {
                "turnComplete": True
            }
        }

        try:
            await self._ws.send(json.dumps(message))
            logger.info("⚠️ Response interrupted (barge-in)")
        except Exception as e:
            logger.error(f"Failed to interrupt: {e}")

    async def send_text(self, text: str):
        """Send text message for testing or hybrid mode"""
        if not self._ws:
            return

        message = {
            "clientContent": {
                "turns": [{
                    "role": "user",
                    "parts": [{"text": text}]
                }],
                "turnComplete": True
            }
        }

        try:
            await self._ws.send(json.dumps(message))
        except Exception as e:
            logger.error(f"Failed to send text: {e}")

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

        self.state = GeminiLiveState.DISCONNECTED
        logger.info("🔌 Gemini Live connection closed")

    @property
    def is_connected(self) -> bool:
        return self.state != GeminiLiveState.DISCONNECTED
