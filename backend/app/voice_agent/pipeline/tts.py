"""
Text-to-Speech Streaming
Converts text to audio with low latency
"""
import os
import asyncio
from typing import Optional, Callable, Awaitable, AsyncGenerator
from abc import ABC, abstractmethod
from openai import AsyncOpenAI
import httpx

from ..utils.logger import get_logger
from ..config import VoiceAgentConfig

logger = get_logger(__name__)


class TTSProvider(ABC):
    """Abstract TTS provider"""

    @abstractmethod
    async def synthesize(self, text: str) -> AsyncGenerator[bytes, None]:
        """Synthesize text to audio stream"""
        pass

    @abstractmethod
    async def close(self):
        """Close provider connection"""
        pass


class OpenAITTS(TTSProvider):
    """OpenAI TTS Provider"""

    def __init__(self, config: VoiceAgentConfig):
        self.config = config
        self.client: Optional[AsyncOpenAI] = None

    async def initialize(self):
        """Initialize OpenAI client"""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.error("OPENAI_API_KEY not set")
            return False

        self.client = AsyncOpenAI(api_key=api_key)
        logger.info("✅ OpenAI TTS initialized")
        return True

    async def synthesize(self, text: str) -> AsyncGenerator[bytes, None]:
        """Synthesize text to audio stream"""
        if not self.client:
            await self.initialize()
            if not self.client:
                return

        try:
            logger.debug(f"🔊 TTS synthesizing: \"{text[:50]}...\"")

            async with self.client.audio.speech.with_streaming_response.create(
                model="tts-1",
                voice=self.config.tts_voice,
                input=text,
                response_format="pcm",
                speed=self.config.tts_speed
            ) as response:
                first_chunk = True
                async for chunk in response.iter_bytes(chunk_size=4096):
                    if first_chunk:
                        logger.debug("⚡ TTS first byte received")
                        first_chunk = False
                    yield chunk

            logger.debug(f"✅ TTS complete for: \"{text[:30]}...\"")

        except Exception as e:
            logger.error(f"OpenAI TTS error: {e}")

    async def close(self):
        """Close provider"""
        self.client = None


class ElevenLabsTTS(TTSProvider):
    """ElevenLabs TTS Provider"""

    def __init__(self, config: VoiceAgentConfig):
        self.config = config
        self.api_key = os.getenv("ELEVENLABS_API_KEY")
        self.voice_id = config.tts_voice
        self.base_url = "https://api.elevenlabs.io/v1"
        self.client: Optional[httpx.AsyncClient] = None

    async def initialize(self):
        """Initialize HTTP client"""
        if not self.api_key:
            logger.error("ELEVENLABS_API_KEY not set")
            return False

        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={"xi-api-key": self.api_key}
        )
        logger.info("✅ ElevenLabs TTS initialized")
        return True

    async def synthesize(self, text: str) -> AsyncGenerator[bytes, None]:
        """Synthesize text to audio stream"""
        if not self.client:
            await self.initialize()
            if not self.client:
                return

        try:
            url = f"{self.base_url}/text-to-speech/{self.voice_id}/stream"

            async with self.client.stream(
                "POST",
                url,
                json={
                    "text": text,
                    "model_id": "eleven_multilingual_v2",
                    "output_format": "pcm_24000",
                    "voice_settings": {
                        "stability": 0.5,
                        "similarity_boost": 0.75
                    }
                }
            ) as response:
                first_chunk = True
                async for chunk in response.aiter_bytes(chunk_size=4096):
                    if first_chunk:
                        logger.debug("⚡ ElevenLabs first byte received")
                        first_chunk = False
                    yield chunk

        except Exception as e:
            logger.error(f"ElevenLabs TTS error: {e}")

    async def close(self):
        """Close provider"""
        if self.client:
            await self.client.aclose()


class CartesiaTTS(TTSProvider):
    """Cartesia TTS Provider - Ultra low latency"""

    def __init__(self, config: VoiceAgentConfig):
        self.config = config
        self.api_key = os.getenv("CARTESIA_API_KEY")
        self.voice_id = config.tts_voice
        self.base_url = "https://api.cartesia.ai"
        self.client: Optional[httpx.AsyncClient] = None

    async def initialize(self):
        """Initialize HTTP client"""
        if not self.api_key:
            logger.error("CARTESIA_API_KEY not set")
            return False

        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "X-API-Key": self.api_key,
                "Cartesia-Version": "2024-06-10"
            }
        )
        logger.info("✅ Cartesia TTS initialized")
        return True

    async def synthesize(self, text: str) -> AsyncGenerator[bytes, None]:
        """Synthesize text to audio stream"""
        if not self.client:
            await self.initialize()
            if not self.client:
                return

        try:
            url = f"{self.base_url}/tts/bytes"

            async with self.client.stream(
                "POST",
                url,
                json={
                    "model_id": "sonic-english",
                    "transcript": text,
                    "voice": {
                        "mode": "id",
                        "id": self.voice_id
                    },
                    "output_format": {
                        "container": "raw",
                        "encoding": "pcm_s16le",
                        "sample_rate": 24000
                    }
                }
            ) as response:
                first_chunk = True
                async for chunk in response.aiter_bytes(chunk_size=4096):
                    if first_chunk:
                        logger.debug("⚡ Cartesia first byte received")
                        first_chunk = False
                    yield chunk

        except Exception as e:
            logger.error(f"Cartesia TTS error: {e}")

    async def close(self):
        """Close provider"""
        if self.client:
            await self.client.aclose()


class TTSStreamer:
    """
    TTS Streamer with provider abstraction

    Features:
    - Multiple TTS providers (OpenAI, ElevenLabs, Cartesia)
    - Streaming audio output
    - Sentence queuing
    - Cancellation support for barge-in
    """

    def __init__(self, config: VoiceAgentConfig):
        self.config = config
        self.provider: Optional[TTSProvider] = None

        # State
        self.is_speaking = False
        self.should_cancel = False
        self.sentence_queue: asyncio.Queue = asyncio.Queue()

        # Callbacks
        self.on_audio_chunk: Optional[Callable[[bytes], Awaitable[None]]] = None
        self.on_speech_start: Optional[Callable[[], Awaitable[None]]] = None
        self.on_speech_end: Optional[Callable[[], Awaitable[None]]] = None

        logger.info(f"TTSStreamer initialized (provider={config.tts_provider})")

    async def initialize(self):
        """Initialize TTS provider"""
        provider_name = self.config.tts_provider.lower()

        if provider_name == "openai":
            self.provider = OpenAITTS(self.config)
        elif provider_name == "elevenlabs":
            self.provider = ElevenLabsTTS(self.config)
        elif provider_name == "cartesia":
            self.provider = CartesiaTTS(self.config)
        else:
            logger.error(f"Unknown TTS provider: {provider_name}")
            return False

        result = await self.provider.initialize()
        if result:
            logger.info(f"✅ TTS provider {provider_name} ready")
        return result

    async def speak(self, text: str):
        """
        Speak text and stream audio chunks

        Args:
            text: Text to synthesize
        """
        if not self.provider:
            await self.initialize()
            if not self.provider:
                return

        if not text or not text.strip():
            return

        self.is_speaking = True
        self.should_cancel = False

        try:
            logger.info(f"🔊 Speaking: \"{text[:50]}...\"")

            if self.on_speech_start:
                await self.on_speech_start()

            first_chunk = True
            async for audio_chunk in self.provider.synthesize(text):
                if self.should_cancel:
                    logger.info("🛑 TTS cancelled (barge-in)")
                    break

                if first_chunk:
                    logger.debug("⚡ First audio chunk sent")
                    first_chunk = False

                if self.on_audio_chunk:
                    await self.on_audio_chunk(audio_chunk)

            if self.on_speech_end:
                await self.on_speech_end()

        except Exception as e:
            logger.error(f"TTS speak error: {e}")
        finally:
            self.is_speaking = False

    async def queue_sentence(self, sentence: str):
        """Queue sentence for TTS"""
        await self.sentence_queue.put(sentence)

    async def process_queue(self):
        """Process sentence queue"""
        while True:
            try:
                sentence = await asyncio.wait_for(
                    self.sentence_queue.get(),
                    timeout=0.1
                )
                await self.speak(sentence)
            except asyncio.TimeoutError:
                pass
            except Exception as e:
                logger.error(f"Queue processing error: {e}")

    def cancel(self):
        """Cancel current speech (for barge-in)"""
        if self.is_speaking:
            self.should_cancel = True
            logger.info("🛑 TTS cancellation requested")

    def clear_queue(self):
        """Clear pending sentences"""
        while not self.sentence_queue.empty():
            try:
                self.sentence_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        logger.debug("TTS queue cleared")

    async def close(self):
        """Close TTS provider"""
        if self.provider:
            await self.provider.close()
            logger.info("TTS closed")
