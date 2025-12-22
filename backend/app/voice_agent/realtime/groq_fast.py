"""
Groq Fast Inference Agent
Ultra-fast LLM inference with Groq LPU for near-realtime voice
"""
import asyncio
import base64
import io
from typing import Optional, Callable, Awaitable, List, Dict, Any
from enum import Enum

from ..utils.logger import get_logger

logger = get_logger(__name__)


class GroqFastState(Enum):
    """Groq Fast connection states"""
    DISCONNECTED = "disconnected"
    READY = "ready"
    PROCESSING = "processing"
    SPEAKING = "speaking"


class GroqFastAgent:
    """
    Groq Fast Inference Agent

    Ultra-fast voice processing using Groq's LPU.
    Uses fast pipeline: Groq Whisper STT → Groq LLM → TTS

    Features:
    - Whisper large-v3 at ~10x realtime speed
    - LLM inference at 500+ tokens/sec
    - Total latency < 500ms
    """

    def __init__(
        self,
        api_key: str,
        model: str = "llama-3.3-70b-versatile",
        voice: str = "alloy",  # TTS voice (will use fallback TTS)
        system_prompt: str = "",
        call_id: Optional[str] = None,
        tts_provider: str = "openai",  # Fallback TTS provider
        tts_api_key: Optional[str] = None,
    ):
        self.api_key = api_key
        self.model = model
        self.voice = voice
        self.system_prompt = system_prompt
        self.call_id = call_id or "groq-fast"
        self.tts_provider = tts_provider
        self.tts_api_key = tts_api_key

        self.state = GroqFastState.DISCONNECTED
        self._is_running = False

        # Groq client
        self._groq_client = None

        # Conversation history
        self._messages: List[Dict[str, Any]] = []
        if system_prompt:
            self._messages.append({"role": "system", "content": system_prompt})

        # Audio buffer for STT
        self._audio_buffer = io.BytesIO()
        self._buffer_lock = asyncio.Lock()

        # Callbacks
        self.on_audio_output: Optional[Callable[[bytes], Awaitable[None]]] = None
        self.on_transcript: Optional[Callable[[str, str], Awaitable[None]]] = None
        self.on_state_change: Optional[Callable[[GroqFastState], Awaitable[None]]] = None
        self.on_error: Optional[Callable[[str], Awaitable[None]]] = None

        # Processing task
        self._process_task: Optional[asyncio.Task] = None
        self._should_interrupt = False

        logger.info(f"🎙️ Groq Fast Agent created (model={model}, voice={voice})")

    async def connect(self) -> bool:
        """Initialize Groq client"""
        try:
            from groq import AsyncGroq

            self._groq_client = AsyncGroq(api_key=self.api_key)
            self._is_running = True
            self.state = GroqFastState.READY

            logger.info(f"✅ Groq Fast Agent ready")
            return True

        except ImportError:
            logger.error("groq package not installed. Run: pip install groq")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize Groq client: {e}")
            return False

    async def send_audio(self, audio_chunk: bytes):
        """Buffer audio for STT processing"""
        if self.state == GroqFastState.DISCONNECTED:
            return

        async with self._buffer_lock:
            self._audio_buffer.write(audio_chunk)

    async def process_turn(self):
        """Process accumulated audio and generate response"""
        if not self._groq_client or self.state == GroqFastState.DISCONNECTED:
            return

        async with self._buffer_lock:
            audio_data = self._audio_buffer.getvalue()
            self._audio_buffer = io.BytesIO()

        if len(audio_data) < 1600:  # Minimum audio length
            return

        self.state = GroqFastState.PROCESSING
        if self.on_state_change:
            await self.on_state_change(self.state)

        try:
            # Step 1: Fast STT with Groq Whisper
            user_text = await self._transcribe_audio(audio_data)
            if not user_text:
                self.state = GroqFastState.READY
                return

            logger.info(f"📝 User: {user_text}")
            if self.on_transcript:
                await self.on_transcript(user_text, "user")

            # Add to history
            self._messages.append({"role": "user", "content": user_text})

            # Step 2: Ultra-fast LLM response with Groq
            if self._should_interrupt:
                self._should_interrupt = False
                self.state = GroqFastState.READY
                return

            response_text = await self._generate_response()
            if not response_text:
                self.state = GroqFastState.READY
                return

            logger.info(f"🤖 Assistant: {response_text}")
            if self.on_transcript:
                await self.on_transcript(response_text, "assistant")

            # Add to history
            self._messages.append({"role": "assistant", "content": response_text})

            # Step 3: TTS
            if self._should_interrupt:
                self._should_interrupt = False
                self.state = GroqFastState.READY
                return

            self.state = GroqFastState.SPEAKING
            if self.on_state_change:
                await self.on_state_change(self.state)

            await self._synthesize_speech(response_text)

        except Exception as e:
            logger.error(f"Process turn error: {e}")
            if self.on_error:
                await self.on_error(str(e))

        finally:
            self.state = GroqFastState.READY
            if self.on_state_change:
                await self.on_state_change(self.state)

    async def _transcribe_audio(self, audio_data: bytes) -> Optional[str]:
        """Transcribe audio using Groq Whisper"""
        try:
            # Create a file-like object
            audio_file = io.BytesIO(audio_data)
            audio_file.name = "audio.wav"

            # Use Groq's Whisper API
            transcription = await self._groq_client.audio.transcriptions.create(
                file=("audio.wav", audio_data, "audio/wav"),
                model="whisper-large-v3-turbo",
                language="en",
                response_format="text"
            )

            return transcription.strip() if transcription else None

        except Exception as e:
            logger.error(f"Transcription error: {e}")
            return None

    async def _generate_response(self) -> Optional[str]:
        """Generate response using Groq LLM"""
        try:
            response = await self._groq_client.chat.completions.create(
                model=self.model,
                messages=self._messages,
                max_tokens=500,
                temperature=0.7,
            )

            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"LLM generation error: {e}")
            return None

    async def _synthesize_speech(self, text: str):
        """Synthesize speech using TTS provider"""
        try:
            if self.tts_provider == "openai" and self.tts_api_key:
                await self._openai_tts(text)
            elif self.tts_provider == "elevenlabs" and self.tts_api_key:
                await self._elevenlabs_tts(text)
            else:
                # Use Groq's upcoming TTS or fallback
                logger.warning("No TTS provider configured, skipping audio output")

        except Exception as e:
            logger.error(f"TTS error: {e}")

    async def _openai_tts(self, text: str):
        """Use OpenAI TTS"""
        import httpx

        url = "https://api.openai.com/v1/audio/speech"
        headers = {
            "Authorization": f"Bearer {self.tts_api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "tts-1",
            "voice": self.voice,
            "input": text,
            "response_format": "pcm"
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=data, headers=headers, timeout=30)
            if response.status_code == 200:
                audio_bytes = response.content
                if self.on_audio_output:
                    # Stream in chunks
                    chunk_size = 4800  # 150ms at 16kHz
                    for i in range(0, len(audio_bytes), chunk_size):
                        if self._should_interrupt:
                            break
                        chunk = audio_bytes[i:i+chunk_size]
                        await self.on_audio_output(chunk)
                        await asyncio.sleep(0.05)

    async def _elevenlabs_tts(self, text: str):
        """Use ElevenLabs TTS"""
        import httpx

        # Default voice ID for ElevenLabs
        voice_id = self.voice if len(self.voice) > 10 else "21m00Tcm4TlvDq8ikWAM"

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"
        headers = {
            "xi-api-key": self.tts_api_key,
            "Content-Type": "application/json"
        }
        data = {
            "text": text,
            "model_id": "eleven_turbo_v2_5",
            "output_format": "pcm_16000"
        }

        async with httpx.AsyncClient() as client:
            async with client.stream("POST", url, json=data, headers=headers, timeout=30) as response:
                if response.status_code == 200:
                    async for chunk in response.aiter_bytes(4800):
                        if self._should_interrupt:
                            break
                        if self.on_audio_output:
                            await self.on_audio_output(chunk)

    async def interrupt(self):
        """Interrupt current processing"""
        self._should_interrupt = True
        logger.info("⚠️ Groq processing interrupted")

    async def send_text(self, text: str):
        """Send text directly (skip STT)"""
        if not self._groq_client:
            return

        self._messages.append({"role": "user", "content": text})

        self.state = GroqFastState.PROCESSING
        if self.on_state_change:
            await self.on_state_change(self.state)

        response_text = await self._generate_response()
        if response_text:
            self._messages.append({"role": "assistant", "content": response_text})
            if self.on_transcript:
                await self.on_transcript(response_text, "assistant")

            self.state = GroqFastState.SPEAKING
            if self.on_state_change:
                await self.on_state_change(self.state)

            await self._synthesize_speech(response_text)

        self.state = GroqFastState.READY
        if self.on_state_change:
            await self.on_state_change(self.state)

    async def close(self):
        """Close the agent"""
        self._is_running = False
        self._should_interrupt = True

        if self._process_task:
            self._process_task.cancel()
            try:
                await self._process_task
            except asyncio.CancelledError:
                pass

        self.state = GroqFastState.DISCONNECTED
        logger.info("🔌 Groq Fast Agent closed")

    @property
    def is_connected(self) -> bool:
        return self.state != GroqFastState.DISCONNECTED
