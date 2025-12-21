"""
Text-to-Speech Streaming
Converts text to audio with low latency
Supports: OpenAI, ElevenLabs, Cartesia, Azure, Deepgram
"""
import os
import asyncio
from typing import Optional, Callable, Awaitable, AsyncGenerator
from abc import ABC, abstractmethod
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
    """OpenAI TTS Provider - Using HTTP directly"""

    def __init__(self, config: VoiceAgentConfig):
        self.config = config
        self.api_key = config.tts_api_key or os.getenv("OPENAI_API_KEY")
        self.client: Optional[httpx.AsyncClient] = None

    async def initialize(self):
        """Initialize HTTP client"""
        if not self.api_key:
            logger.error("OpenAI TTS API key not set")
            return False

        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
        )
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

            url = "https://api.openai.com/v1/audio/speech"
            data = {
                "model": "tts-1",
                "voice": self.config.tts_voice or "alloy",
                "input": text,
                "response_format": "pcm",
                "speed": self.config.tts_speed or 1.0
            }

            async with self.client.stream("POST", url, json=data) as response:
                if response.status_code != 200:
                    error = await response.aread()
                    logger.error(f"OpenAI TTS error: {error}")
                    return

                first_chunk = True
                async for chunk in response.aiter_bytes(chunk_size=4096):
                    if first_chunk:
                        logger.debug("⚡ TTS first byte received")
                        first_chunk = False
                    yield chunk

            logger.debug(f"✅ TTS complete")

        except Exception as e:
            logger.error(f"OpenAI TTS error: {e}")

    async def close(self):
        """Close provider"""
        if self.client:
            await self.client.aclose()
            self.client = None


class ElevenLabsTTS(TTSProvider):
    """ElevenLabs TTS Provider"""

    def __init__(self, config: VoiceAgentConfig):
        self.config = config
        self.api_key = config.tts_api_key or os.getenv("ELEVENLABS_API_KEY")
        self.voice_id = config.tts_voice or "21m00Tcm4TlvDq8ikWAM"  # Default Rachel
        self.base_url = "https://api.elevenlabs.io/v1"
        self.client: Optional[httpx.AsyncClient] = None

    async def initialize(self):
        """Initialize HTTP client"""
        if not self.api_key:
            logger.error("ElevenLabs API key not set")
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
        self.api_key = config.tts_api_key or os.getenv("CARTESIA_API_KEY")
        self.voice_id = config.tts_voice
        self.base_url = "https://api.cartesia.ai"
        self.client: Optional[httpx.AsyncClient] = None

    async def initialize(self):
        """Initialize HTTP client"""
        if not self.api_key:
            logger.error("Cartesia API key not set")
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
                    "model_id": "sonic-multilingual",
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


class AzureTTS(TTSProvider):
    """Azure Cognitive Services TTS Provider"""

    def __init__(self, config: VoiceAgentConfig):
        self.config = config
        self.api_key = config.tts_api_key or os.getenv("AZURE_TTS_API_KEY")
        self.region = config.tts_region or os.getenv("AZURE_TTS_REGION", "eastus")
        self.voice = config.tts_voice or "ar-SA-HamedNeural"
        self.client: Optional[httpx.AsyncClient] = None

    async def initialize(self):
        """Initialize HTTP client"""
        if not self.api_key:
            logger.error("Azure TTS API key not set")
            return False

        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "Ocp-Apim-Subscription-Key": self.api_key,
                "Content-Type": "application/ssml+xml",
                "X-Microsoft-OutputFormat": "raw-24khz-16bit-mono-pcm"
            }
        )
        logger.info("✅ Azure TTS initialized")
        return True

    async def synthesize(self, text: str) -> AsyncGenerator[bytes, None]:
        """Synthesize text to audio stream"""
        if not self.client:
            await self.initialize()
            if not self.client:
                return

        try:
            url = f"https://{self.region}.tts.speech.microsoft.com/cognitiveservices/v1"

            ssml = f"""<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='ar-SA'>
                <voice name='{self.voice}'>{text}</voice>
            </speak>"""

            response = await self.client.post(url, content=ssml)
            if response.status_code == 200:
                yield response.content
            else:
                logger.error(f"Azure TTS error: {response.status_code}")

        except Exception as e:
            logger.error(f"Azure TTS error: {e}")

    async def close(self):
        """Close provider"""
        if self.client:
            await self.client.aclose()


class DeepgramTTS(TTSProvider):
    """Deepgram Aura TTS Provider - Fast"""

    def __init__(self, config: VoiceAgentConfig):
        self.config = config
        self.api_key = config.tts_api_key or os.getenv("DEEPGRAM_API_KEY")
        self.voice = config.tts_voice or "aura-asteria-en"
        self.client: Optional[httpx.AsyncClient] = None

    async def initialize(self):
        """Initialize HTTP client"""
        if not self.api_key:
            logger.error("Deepgram TTS API key not set")
            return False

        self.client = httpx.AsyncClient(
            timeout=30.0,
            headers={
                "Authorization": f"Token {self.api_key}",
                "Content-Type": "application/json"
            }
        )
        logger.info("✅ Deepgram TTS initialized")
        return True

    async def synthesize(self, text: str) -> AsyncGenerator[bytes, None]:
        """Synthesize text to audio stream"""
        if not self.client:
            await self.initialize()
            if not self.client:
                return

        try:
            url = f"https://api.deepgram.com/v1/speak?model={self.voice}&encoding=linear16&sample_rate=24000"

            async with self.client.stream(
                "POST",
                url,
                json={"text": text}
            ) as response:
                first_chunk = True
                async for chunk in response.aiter_bytes(chunk_size=4096):
                    if first_chunk:
                        logger.debug("⚡ Deepgram TTS first byte received")
                        first_chunk = False
                    yield chunk

        except Exception as e:
            logger.error(f"Deepgram TTS error: {e}")

    async def close(self):
        """Close provider"""
        if self.client:
            await self.client.aclose()


class TTSStreamer:
    """
    TTS Streamer with provider abstraction

    Supports:
    - OpenAI (tts-1)
    - ElevenLabs (eleven_multilingual_v2)
    - Cartesia (sonic)
    - Azure (Neural voices)
    - Deepgram (Aura)
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
        elif provider_name == "azure":
            self.provider = AzureTTS(self.config)
        elif provider_name == "deepgram":
            self.provider = DeepgramTTS(self.config)
        else:
            logger.error(f"Unknown TTS provider: {provider_name}")
            return False

        result = await self.provider.initialize()
        if result:
            logger.info(f"✅ TTS provider {provider_name} ready")
        return result

    async def speak(self, text: str):
        """Speak text and stream audio chunks"""
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
