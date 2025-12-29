"""
ElevenLabs Conversational AI Agent
Real-time voice conversations with best-in-class voice quality
"""
import asyncio
import json
import base64
from typing import Optional, Callable, Awaitable
from enum import Enum

from ..utils.logger import get_logger
from ..prompts import build_system_prompt

logger = get_logger(__name__)


class ElevenLabsState(Enum):
    """ElevenLabs Conversational connection states"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    LISTENING = "listening"
    SPEAKING = "speaking"


class ElevenLabsConversationalAgent:
    """
    ElevenLabs Conversational AI Agent

    Real-time voice conversations using ElevenLabs' platform.
    Features:
    - Best-in-class voice quality
    - Sub-second turnaround
    - Multiple LLM support (GPT-4, Claude, Gemini)
    - Custom knowledge base integration
    - 30 HD voices in 24 languages
    """

    # ElevenLabs Conversational WebSocket endpoint
    CONVAI_URL = "wss://api.elevenlabs.io/v1/convai/conversation"

    def __init__(
        self,
        api_key: str,
        agent_id: str,  # Pre-configured agent ID from ElevenLabs dashboard
        voice_id: str = "21m00Tcm4TlvDq8ikWAM",  # Rachel voice
        system_prompt: str = "",
        call_id: Optional[str] = None,
        language: str = "ar",
        model: str = "gpt-4",  # LLM model for the agent
    ):
        self.api_key = api_key
        self.agent_id = agent_id
        self.voice_id = voice_id
        self.call_id = call_id or "elevenlabs-conv"
        self.language = language
        self.model = model

        # Build system prompt with internal voice call instructions
        self.system_prompt = build_system_prompt(system_prompt, language=language)

        self.state = ElevenLabsState.DISCONNECTED
        self._ws = None
        self._is_running = False
        self._receive_task: Optional[asyncio.Task] = None
        self._conversation_id: Optional[str] = None

        # Callbacks
        self.on_audio_output: Optional[Callable[[bytes], Awaitable[None]]] = None
        self.on_transcript: Optional[Callable[[str, str], Awaitable[None]]] = None
        self.on_state_change: Optional[Callable[[ElevenLabsState], Awaitable[None]]] = None
        self.on_error: Optional[Callable[[str], Awaitable[None]]] = None

        # Audio settings - ElevenLabs uses 16kHz PCM
        self.sample_rate = 16000
        self.channels = 1

        logger.info(f"🎙️ ElevenLabs Conversational Agent created (agent_id={agent_id}, voice={voice_id})")

    async def connect(self) -> bool:
        """Connect to ElevenLabs Conversational AI"""
        try:
            import websockets

            self.state = ElevenLabsState.CONNECTING

            # Build WebSocket URL with agent_id
            url = f"{self.CONVAI_URL}?agent_id={self.agent_id}"

            headers = {
                "xi-api-key": self.api_key,
            }

            logger.info(f"🔌 Connecting to ElevenLabs Conversational AI...")

            # Connect with headers
            try:
                self._ws = await websockets.connect(url, additional_headers=headers)
            except TypeError:
                # Older websockets version
                self._ws = await websockets.connect(url, extra_headers=headers)

            # Send initialization message
            await self._initialize_conversation()

            # Start receiving messages
            self._is_running = True
            self._receive_task = asyncio.create_task(self._receive_loop())

            self.state = ElevenLabsState.CONNECTED
            logger.info(f"✅ Connected to ElevenLabs Conversational AI")

            return True

        except Exception as e:
            logger.error(f"Failed to connect to ElevenLabs: {e}")
            self.state = ElevenLabsState.DISCONNECTED
            return False

    async def _initialize_conversation(self):
        """Initialize the conversation session"""
        init_message = {
            "type": "conversation_initiation_client_data",
            "conversation_config_override": {
                "agent": {
                    "prompt": {
                        "prompt": self.system_prompt
                    },
                    "first_message": None,  # Let agent decide
                    "language": self.language,
                },
                "tts": {
                    "voice_id": self.voice_id,
                }
            }
        }

        await self._ws.send(json.dumps(init_message))
        logger.info(f"📋 ElevenLabs conversation initialized")

    async def _receive_loop(self):
        """Receive and process messages from ElevenLabs"""
        import websockets

        try:
            async for message in self._ws:
                if not self._is_running:
                    break

                try:
                    # Handle both text and binary messages
                    if isinstance(message, bytes):
                        # Binary audio data
                        if self.on_audio_output:
                            await self.on_audio_output(message)
                            if self.state != ElevenLabsState.SPEAKING:
                                self.state = ElevenLabsState.SPEAKING
                                if self.on_state_change:
                                    await self.on_state_change(self.state)
                    else:
                        # JSON message
                        event = json.loads(message)
                        await self._handle_event(event)
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON from ElevenLabs: {message[:100]}")

        except websockets.exceptions.ConnectionClosed:
            logger.info("ElevenLabs connection closed")
        except Exception as e:
            logger.error(f"Receive loop error: {e}")
        finally:
            self.state = ElevenLabsState.DISCONNECTED

    async def _handle_event(self, event: dict):
        """Handle events from ElevenLabs Conversational API"""
        event_type = event.get("type", "")

        if event_type == "conversation_initiation_metadata":
            # Conversation started
            self._conversation_id = event.get("conversation_id")
            logger.info(f"✅ Conversation started: {self._conversation_id}")

        elif event_type == "user_transcript":
            # User's speech transcribed
            transcript = event.get("user_transcript", "")
            if transcript and self.on_transcript:
                await self.on_transcript(transcript, "user")
            logger.info(f"📝 User: {transcript}")
            self.state = ElevenLabsState.LISTENING
            if self.on_state_change:
                await self.on_state_change(self.state)

        elif event_type == "agent_response":
            # Agent's text response
            response = event.get("agent_response", "")
            if response and self.on_transcript:
                await self.on_transcript(response, "assistant")
            logger.info(f"🤖 Agent: {response}")

        elif event_type == "audio":
            # Audio chunk (base64 encoded)
            audio_b64 = event.get("audio", "")
            if audio_b64 and self.on_audio_output:
                audio_bytes = base64.b64decode(audio_b64)
                await self.on_audio_output(audio_bytes)
                if self.state != ElevenLabsState.SPEAKING:
                    self.state = ElevenLabsState.SPEAKING
                    if self.on_state_change:
                        await self.on_state_change(self.state)

        elif event_type == "agent_response_correction":
            # Corrected response (final)
            response = event.get("agent_response", "")
            logger.debug(f"Agent response corrected: {response}")

        elif event_type == "interruption":
            # User interrupted
            logger.info("⚠️ User interrupted agent")
            self.state = ElevenLabsState.LISTENING
            if self.on_state_change:
                await self.on_state_change(self.state)

        elif event_type == "ping":
            # Respond to ping
            await self._ws.send(json.dumps({"type": "pong"}))

        elif event_type == "error":
            error_msg = event.get("message", "Unknown error")
            logger.error(f"❌ ElevenLabs error: {error_msg}")
            if self.on_error:
                await self.on_error(error_msg)

        elif event_type == "turn_complete":
            # Agent finished speaking
            self.state = ElevenLabsState.CONNECTED
            if self.on_state_change:
                await self.on_state_change(self.state)
            logger.debug("Turn complete")

        else:
            logger.debug(f"Unhandled event: {event_type}")

    async def send_audio(self, audio_chunk: bytes):
        """Send audio chunk to ElevenLabs"""
        if not self._ws or self.state == ElevenLabsState.DISCONNECTED:
            return

        # ElevenLabs expects base64 encoded audio
        audio_b64 = base64.b64encode(audio_chunk).decode()

        message = {
            "type": "user_audio_chunk",
            "user_audio_chunk": audio_b64
        }

        try:
            await self._ws.send(json.dumps(message))
        except Exception as e:
            logger.error(f"Failed to send audio: {e}")

    async def interrupt(self):
        """Interrupt the current response (barge-in)"""
        if not self._ws:
            return

        message = {
            "type": "interruption"
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
            "type": "user_message",
            "user_message": text
        }

        try:
            await self._ws.send(json.dumps(message))
            if self.on_transcript:
                await self.on_transcript(text, "user")
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

        self.state = ElevenLabsState.DISCONNECTED
        logger.info("🔌 ElevenLabs Conversational connection closed")

    @property
    def is_connected(self) -> bool:
        return self.state != ElevenLabsState.DISCONNECTED
