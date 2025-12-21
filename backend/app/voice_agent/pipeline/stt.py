"""
Speech-to-Text Module - Multi-provider support
Supports: Deepgram, OpenAI Whisper, Azure, Groq
"""
import os
import asyncio
import base64
import httpx
from typing import Optional, Callable, Awaitable
from dataclasses import dataclass
from enum import Enum

from ..utils.logger import get_logger
from ..config import VoiceAgentConfig

logger = get_logger(__name__)


class TranscriptType(Enum):
    """Type of transcript result"""
    INTERIM = "interim"
    FINAL = "final"


@dataclass
class TranscriptEvent:
    """Transcript event from STT"""
    text: str
    is_final: bool
    confidence: float
    speech_final: bool
    start_time: float
    duration: float


class STTProvider:
    """Base STT Provider interface"""

    def __init__(self, config: VoiceAgentConfig):
        self.config = config
        self.is_connected = False
        self.on_transcript: Optional[Callable[[TranscriptEvent], Awaitable[None]]] = None
        self.on_speech_started: Optional[Callable[[], Awaitable[None]]] = None
        self.on_utterance_end: Optional[Callable[[], Awaitable[None]]] = None

    async def connect(self) -> bool:
        raise NotImplementedError

    async def send_audio(self, audio_chunk: bytes):
        raise NotImplementedError

    async def close(self):
        raise NotImplementedError

    def reset(self):
        pass


class DeepgramSTT(STTProvider):
    """Deepgram Streaming STT"""

    def __init__(self, config: VoiceAgentConfig):
        super().__init__(config)
        self.client = None
        self.connection = None
        self._last_final_text = ""

    async def connect(self) -> bool:
        try:
            # Lazy import
            from deepgram import DeepgramClient

            api_key = self.config.stt_api_key or os.getenv("DEEPGRAM_API_KEY")
            if not api_key:
                logger.error("Deepgram API key not configured")
                return False

            self.client = DeepgramClient(api_key)
            self.connection = self.client.listen.websocket.v("1")

            options = {
                "model": self.config.stt_model or "nova-2",
                "language": self.config.stt_language or "ar",
                "punctuate": True,
                "interim_results": True,
                "endpointing": 300,
                "utterance_end_ms": 1000,
                "vad_events": True,
                "smart_format": True,
                "encoding": "linear16",
                "sample_rate": 16000,
                "channels": 1,
            }

            self.connection.on("transcript", self._on_transcript)
            self.connection.on("speech_started", self._on_speech_started)
            self.connection.on("utterance_end", self._on_utterance_end)
            self.connection.on("error", self._on_error)

            if self.connection.start(options):
                self.is_connected = True
                logger.info("✅ Deepgram STT connected")
                return True
            return False

        except ImportError:
            logger.error("deepgram-sdk not installed. Run: pip install deepgram-sdk")
            return False
        except Exception as e:
            logger.error(f"Deepgram connection error: {e}")
            return False

    async def send_audio(self, audio_chunk: bytes):
        if self.connection and self.is_connected:
            try:
                self.connection.send(audio_chunk)
            except Exception as e:
                logger.error(f"Deepgram send error: {e}")

    async def close(self):
        if self.connection:
            try:
                self.connection.finish()
            except:
                pass
            self.is_connected = False
            self.connection = None

    def _on_transcript(self, *args, **kwargs):
        try:
            result = kwargs.get("result") or (args[1] if len(args) > 1 else None)
            if not result:
                return

            channel = result.channel
            alternatives = channel.alternatives
            if not alternatives:
                return

            transcript = alternatives[0].transcript
            if not transcript or not transcript.strip():
                return

            is_final = getattr(result, 'is_final', False)
            speech_final = getattr(result, 'speech_final', False)

            event = TranscriptEvent(
                text=transcript.strip(),
                is_final=is_final,
                confidence=alternatives[0].confidence or 0.0,
                speech_final=speech_final,
                start_time=getattr(result, 'start', 0.0),
                duration=getattr(result, 'duration', 0.0)
            )

            if is_final:
                logger.info(f"📝 STT: \"{transcript}\"")
                self._last_final_text = transcript.strip()

            if self.on_transcript:
                asyncio.create_task(self.on_transcript(event))

        except Exception as e:
            logger.error(f"Transcript error: {e}")

    def _on_speech_started(self, *args, **kwargs):
        if self.on_speech_started:
            asyncio.create_task(self.on_speech_started())

    def _on_utterance_end(self, *args, **kwargs):
        if self.on_utterance_end:
            asyncio.create_task(self.on_utterance_end())

    def _on_error(self, *args, **kwargs):
        error = kwargs.get("error") or "Unknown"
        logger.error(f"Deepgram error: {error}")

    @property
    def last_final_text(self) -> str:
        return self._last_final_text


class OpenAIWhisperSTT(STTProvider):
    """OpenAI Whisper STT (batch mode with chunking)"""

    def __init__(self, config: VoiceAgentConfig):
        super().__init__(config)
        self.api_key = None
        self.audio_buffer = b""
        self.buffer_duration_ms = 0
        self.min_buffer_ms = 1000  # Process every 1 second
        self._last_final_text = ""
        self._processing = False

    async def connect(self) -> bool:
        # Try multiple sources for OpenAI API key:
        # 1. If stt_provider is "openai", use stt_api_key
        # 2. If llm_provider is "openai", use llm_api_key
        # 3. Fall back to environment variable
        if self.config.stt_provider == "openai":
            self.api_key = self.config.stt_api_key

        if not self.api_key and self.config.llm_provider == "openai":
            self.api_key = self.config.llm_api_key

        if not self.api_key:
            self.api_key = os.getenv("OPENAI_API_KEY")

        if not self.api_key:
            logger.error("OpenAI API key not found for Whisper STT")
            return False

        self.is_connected = True
        logger.info("✅ OpenAI Whisper STT ready")
        return True

    async def send_audio(self, audio_chunk: bytes):
        if not self.is_connected:
            return

        self.audio_buffer += audio_chunk
        # 16-bit audio at 16kHz = 32 bytes per ms
        self.buffer_duration_ms = len(self.audio_buffer) / 32

        # Process when we have enough audio
        if self.buffer_duration_ms >= self.min_buffer_ms and not self._processing:
            asyncio.create_task(self._process_buffer())

    async def _process_buffer(self):
        if self._processing or len(self.audio_buffer) < 1000:
            return

        self._processing = True
        audio_data = self.audio_buffer
        self.audio_buffer = b""
        self.buffer_duration_ms = 0

        try:
            # Convert PCM to WAV format
            import io
            import wave

            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, 'wb') as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(16000)
                wav.writeframes(audio_data)
            wav_buffer.seek(0)

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.openai.com/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    files={"file": ("audio.wav", wav_buffer, "audio/wav")},
                    data={
                        "model": "whisper-1",
                        "language": self.config.stt_language[:2] if self.config.stt_language else "ar"
                    },
                    timeout=10.0
                )

                if response.status_code == 200:
                    result = response.json()
                    text = result.get("text", "").strip()
                    if text:
                        self._last_final_text = text
                        event = TranscriptEvent(
                            text=text,
                            is_final=True,
                            confidence=0.9,
                            speech_final=True,
                            start_time=0,
                            duration=0
                        )
                        logger.info(f"📝 Whisper STT: \"{text}\"")
                        if self.on_transcript:
                            await self.on_transcript(event)
        except Exception as e:
            logger.error(f"Whisper STT error: {e}")
        finally:
            self._processing = False

    async def close(self):
        # Process remaining buffer
        if len(self.audio_buffer) > 3200:  # At least 100ms
            await self._process_buffer()
        self.is_connected = False
        self.audio_buffer = b""

    @property
    def last_final_text(self) -> str:
        return self._last_final_text


class AzureWhisperSTT(STTProvider):
    """Azure Speech-to-Text (batch mode)"""

    def __init__(self, config: VoiceAgentConfig):
        super().__init__(config)
        self.api_key = None
        self.region = None
        self.audio_buffer = b""
        self.buffer_duration_ms = 0
        self.min_buffer_ms = 1000
        self._last_final_text = ""
        self._processing = False

    async def connect(self) -> bool:
        self.api_key = self.config.stt_api_key or os.getenv("AZURE_SPEECH_KEY")
        self.region = self.config.stt_region or os.getenv("AZURE_SPEECH_REGION", "eastus")

        if not self.api_key:
            logger.error("Azure Speech API key not configured")
            return False

        self.is_connected = True
        logger.info(f"✅ Azure STT ready (region={self.region})")
        return True

    async def send_audio(self, audio_chunk: bytes):
        if not self.is_connected:
            return

        self.audio_buffer += audio_chunk
        self.buffer_duration_ms = len(self.audio_buffer) / 32

        if self.buffer_duration_ms >= self.min_buffer_ms and not self._processing:
            asyncio.create_task(self._process_buffer())

    async def _process_buffer(self):
        if self._processing or len(self.audio_buffer) < 1000:
            return

        self._processing = True
        audio_data = self.audio_buffer
        self.audio_buffer = b""

        try:
            import io
            import wave

            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, 'wb') as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(16000)
                wav.writeframes(audio_data)
            wav_buffer.seek(0)

            # Get language code for Azure
            lang = self.config.stt_language or "ar-SA"
            if len(lang) == 2:
                lang = f"{lang}-SA" if lang == "ar" else f"{lang}-US"

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"https://{self.region}.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1",
                    headers={
                        "Ocp-Apim-Subscription-Key": self.api_key,
                        "Content-Type": "audio/wav; codecs=audio/pcm; samplerate=16000"
                    },
                    params={"language": lang},
                    content=wav_buffer.read(),
                    timeout=10.0
                )

                if response.status_code == 200:
                    result = response.json()
                    text = result.get("DisplayText", "").strip()
                    if text:
                        self._last_final_text = text
                        event = TranscriptEvent(
                            text=text,
                            is_final=True,
                            confidence=result.get("RecognitionStatus") == "Success",
                            speech_final=True,
                            start_time=0,
                            duration=0
                        )
                        logger.info(f"📝 Azure STT: \"{text}\"")
                        if self.on_transcript:
                            await self.on_transcript(event)
                else:
                    logger.error(f"Azure STT error: {response.status_code}")
        except Exception as e:
            logger.error(f"Azure STT error: {e}")
        finally:
            self._processing = False

    async def close(self):
        if len(self.audio_buffer) > 3200:
            await self._process_buffer()
        self.is_connected = False

    @property
    def last_final_text(self) -> str:
        return self._last_final_text


class GroqWhisperSTT(STTProvider):
    """Groq Whisper STT (fast batch mode)"""

    def __init__(self, config: VoiceAgentConfig):
        super().__init__(config)
        self.api_key = None
        self.audio_buffer = b""
        self.buffer_duration_ms = 0
        self.min_buffer_ms = 800
        self._last_final_text = ""
        self._processing = False

    async def connect(self) -> bool:
        self.api_key = self.config.stt_api_key or os.getenv("GROQ_API_KEY")
        if not self.api_key:
            logger.error("Groq API key not configured")
            return False
        self.is_connected = True
        logger.info("✅ Groq Whisper STT ready")
        return True

    async def send_audio(self, audio_chunk: bytes):
        if not self.is_connected:
            return

        self.audio_buffer += audio_chunk
        self.buffer_duration_ms = len(self.audio_buffer) / 32

        if self.buffer_duration_ms >= self.min_buffer_ms and not self._processing:
            asyncio.create_task(self._process_buffer())

    async def _process_buffer(self):
        if self._processing or len(self.audio_buffer) < 1000:
            return

        self._processing = True
        audio_data = self.audio_buffer
        self.audio_buffer = b""

        try:
            import io
            import wave

            wav_buffer = io.BytesIO()
            with wave.open(wav_buffer, 'wb') as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(16000)
                wav.writeframes(audio_data)
            wav_buffer.seek(0)

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://api.groq.com/openai/v1/audio/transcriptions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    files={"file": ("audio.wav", wav_buffer, "audio/wav")},
                    data={
                        "model": "whisper-large-v3",
                        "language": self.config.stt_language[:2] if self.config.stt_language else "ar"
                    },
                    timeout=10.0
                )

                if response.status_code == 200:
                    result = response.json()
                    text = result.get("text", "").strip()
                    if text:
                        self._last_final_text = text
                        event = TranscriptEvent(
                            text=text,
                            is_final=True,
                            confidence=0.9,
                            speech_final=True,
                            start_time=0,
                            duration=0
                        )
                        logger.info(f"📝 Groq STT: \"{text}\"")
                        if self.on_transcript:
                            await self.on_transcript(event)
        except Exception as e:
            logger.error(f"Groq STT error: {e}")
        finally:
            self._processing = False

    async def close(self):
        if len(self.audio_buffer) > 3200:
            await self._process_buffer()
        self.is_connected = False

    @property
    def last_final_text(self) -> str:
        return self._last_final_text


class STTStreamer:
    """
    Multi-provider STT Streamer
    Automatically selects provider based on config
    """

    def __init__(self, config: VoiceAgentConfig):
        self.config = config
        self.provider: Optional[STTProvider] = None
        self._last_final_text = ""

        # Callbacks to be forwarded
        self.on_transcript: Optional[Callable[[TranscriptEvent], Awaitable[None]]] = None
        self.on_speech_started: Optional[Callable[[], Awaitable[None]]] = None
        self.on_utterance_end: Optional[Callable[[], Awaitable[None]]] = None

    async def connect(self) -> bool:
        """Connect to STT provider"""
        provider_name = (self.config.stt_provider or "deepgram").lower()

        logger.info(f"🎤 Connecting to STT provider: {provider_name}")

        # Create provider instance
        if provider_name == "deepgram":
            self.provider = DeepgramSTT(self.config)
        elif provider_name in ["openai", "whisper"]:
            self.provider = OpenAIWhisperSTT(self.config)
        elif provider_name == "groq":
            self.provider = GroqWhisperSTT(self.config)
        elif provider_name == "azure":
            self.provider = AzureWhisperSTT(self.config)
        else:
            logger.warning(f"Unknown STT provider: {provider_name}, using Deepgram")
            self.provider = DeepgramSTT(self.config)

        # Set up callbacks
        self.provider.on_transcript = self._on_transcript
        self.provider.on_speech_started = self.on_speech_started
        self.provider.on_utterance_end = self.on_utterance_end

        # Connect
        success = await self.provider.connect()
        if not success:
            # Try fallback to OpenAI Whisper
            if provider_name != "openai":
                logger.warning(f"{provider_name} failed, trying OpenAI Whisper fallback")
                self.provider = OpenAIWhisperSTT(self.config)
                self.provider.on_transcript = self._on_transcript
                success = await self.provider.connect()

        return success

    async def _on_transcript(self, event: TranscriptEvent):
        """Forward transcript event"""
        if event.is_final:
            self._last_final_text = event.text
        if self.on_transcript:
            await self.on_transcript(event)

    async def send_audio(self, audio_chunk: bytes):
        """Send audio to STT provider"""
        if self.provider:
            await self.provider.send_audio(audio_chunk)

    async def close(self):
        """Close STT connection"""
        if self.provider:
            await self.provider.close()
            self.provider = None

    def reset(self):
        """Reset STT state"""
        if self.provider:
            self.provider.reset()
        self._last_final_text = ""

    @property
    def is_connected(self) -> bool:
        return self.provider.is_connected if self.provider else False

    @property
    def last_final_text(self) -> str:
        return self._last_final_text
