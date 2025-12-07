"""
Text-to-Speech Service
Supports: ElevenLabs, Azure TTS, OpenAI TTS, Deepgram Aura, Cartesia Sonic
"""
import asyncio
import base64
import hashlib
import time
from typing import Optional, AsyncGenerator, Dict, Any, Tuple
from dataclasses import dataclass
import httpx
from loguru import logger


class TTSCache:
    """Simple TTL-based cache for TTS audio"""

    def __init__(self, max_size: int = 100, ttl_seconds: int = 3600):
        self._cache: Dict[str, Tuple[bytes, bytes, float]] = {}  # key -> (mp3_audio, pcm_audio, timestamp)
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._hits = 0
        self._misses = 0

    def _make_key(self, text: str, voice_id: str, provider: str) -> str:
        """Create a cache key from text and voice settings"""
        content = f"{provider}:{voice_id}:{text}"
        return hashlib.sha256(content.encode()).hexdigest()[:32]

    def get(self, text: str, voice_id: str, provider: str, output_format: str = "mp3") -> Optional[bytes]:
        """Get cached audio if available and not expired"""
        key = self._make_key(text, voice_id, provider)
        if key in self._cache:
            mp3_audio, pcm_audio, timestamp = self._cache[key]
            if time.time() - timestamp < self.ttl_seconds:
                self._hits += 1
                logger.info(f"🎯 TTS Cache HIT for: {text[:30]}... (hits: {self._hits})")
                return pcm_audio if output_format == "pcm" else mp3_audio
            else:
                # Expired
                del self._cache[key]
        self._misses += 1
        return None

    def set(self, text: str, voice_id: str, provider: str, mp3_audio: bytes, pcm_audio: Optional[bytes] = None):
        """Cache audio data"""
        key = self._make_key(text, voice_id, provider)

        # Evict oldest if at capacity
        if len(self._cache) >= self.max_size:
            oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k][2])
            del self._cache[oldest_key]

        self._cache[key] = (mp3_audio, pcm_audio or b"", time.time())
        logger.info(f"💾 TTS Cached: {text[:30]}... (size: {len(self._cache)}, misses: {self._misses})")

    def stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self._hits / (self._hits + self._misses) if (self._hits + self._misses) > 0 else 0
        }


# Global TTS cache (shared across all sessions)
_tts_cache = TTSCache(max_size=200, ttl_seconds=7200)  # 2 hour TTL


@dataclass
class TTSConfig:
    """TTS Configuration"""
    voice_id: str
    speed: float = 1.0
    pitch: float = 1.0
    stability: float = 0.5  # ElevenLabs specific
    similarity_boost: float = 0.75  # ElevenLabs specific


class TTSService:
    """Text-to-Speech service with multiple provider support"""

    # Voice IDs for different providers
    ARABIC_VOICES = {
        "elevenlabs": {
            "male": "pNInz6obpgDQGcFmaJgB",  # Adam
            "female": "EXAVITQu4vr4xnSDxMaL",  # Bella
        },
        "azure": {
            "male": "ar-SA-HamedNeural",  # Saudi male
            "female": "ar-SA-ZariyahNeural",  # Saudi female
            "male_eg": "ar-EG-ShakirNeural",  # Egyptian male
            "female_eg": "ar-EG-SalmaNeural",  # Egyptian female
        },
        "openai": {
            "male": "onyx",
            "female": "nova",
            "alloy": "alloy",
            "echo": "echo",
            "fable": "fable",
            "shimmer": "shimmer",
        },
        "deepgram": {
            # Deepgram Aura voices - FASTEST TTS
            "asteria": "aura-asteria-en",  # Female, American
            "luna": "aura-luna-en",  # Female, American
            "stella": "aura-stella-en",  # Female, American
            "athena": "aura-athena-en",  # Female, British
            "hera": "aura-hera-en",  # Female, American
            "orion": "aura-orion-en",  # Male, American
            "arcas": "aura-arcas-en",  # Male, American
            "perseus": "aura-perseus-en",  # Male, American
            "angus": "aura-angus-en",  # Male, Irish
            "orpheus": "aura-orpheus-en",  # Male, American
            "helios": "aura-helios-en",  # Male, British
            "zeus": "aura-zeus-en",  # Male, American
        },
        "cartesia": {
            # Cartesia Sonic voices - Ultra-low latency TTS
            # Default voice IDs - check play.cartesia.ai for Arabic voices
            "default": "694f9389-aac1-45b6-b726-9d9369183238",
            "male": "694f9389-aac1-45b6-b726-9d9369183238",
            "female": "694f9389-aac1-45b6-b726-9d9369183238",
        },
    }

    def __init__(
        self,
        provider: str = "elevenlabs",
        api_key: Optional[str] = None,
        region: Optional[str] = None,  # For Azure
        voice_id: Optional[str] = None,
        voice_speed: float = 1.0,
        voice_stability: float = 0.5,
    ):
        self.provider = provider
        self.api_key = api_key
        self.region = region
        self.voice_id = voice_id or self._default_voice()
        self.voice_speed = voice_speed
        self.voice_stability = voice_stability
        # Create default config with speed and stability
        self.default_config = TTSConfig(
            voice_id=self.voice_id,
            speed=voice_speed,
            stability=voice_stability,
        )

    def _default_voice(self) -> str:
        """Get default Arabic voice for provider"""
        voices = self.ARABIC_VOICES.get(self.provider, {})
        return voices.get("female", voices.get("male", ""))

    async def synthesize(
        self,
        text: str,
        config: Optional[TTSConfig] = None,
        output_format: str = "mp3",  # "mp3" or "pcm"
        use_cache: bool = True,
    ) -> bytes:
        """Synthesize text to audio with caching support"""
        # Use default config if none provided
        config = config or self.default_config
        voice_id = config.voice_id if config else self.voice_id

        # Check cache first (much faster for repeated phrases like greetings)
        if use_cache:
            cached = _tts_cache.get(text, voice_id, self.provider, output_format)
            if cached:
                return cached

        # Synthesize using the appropriate provider
        if self.provider == "elevenlabs":
            audio = await self._elevenlabs_synthesize(text, config, output_format)
        elif self.provider == "azure":
            audio = await self._azure_synthesize(text, config, output_format)
        elif self.provider == "openai":
            audio = await self._openai_synthesize(text, config, output_format)
        elif self.provider == "deepgram":
            audio = await self._deepgram_synthesize(text, config, output_format)
        elif self.provider == "cartesia":
            audio = await self._cartesia_synthesize(text, config, output_format)
        elif self.provider == "google":
            audio = await self._google_synthesize(text, config, output_format)
        else:
            raise ValueError(f"Unknown TTS provider: {self.provider}")

        # Cache the result (store both formats if we have MP3)
        if use_cache and audio:
            if output_format == "mp3":
                _tts_cache.set(text, voice_id, self.provider, audio)
            else:
                # For PCM, we also need to get MP3 for complete cache entry
                _tts_cache.set(text, voice_id, self.provider, b"", audio)

        return audio

    async def synthesize_stream(
        self,
        text: str,
        config: Optional[TTSConfig] = None,
    ) -> AsyncGenerator[bytes, None]:
        """Stream synthesized audio"""
        if self.provider == "elevenlabs":
            async for chunk in self._elevenlabs_stream(text, config):
                yield chunk
        elif self.provider == "openai":
            async for chunk in self._openai_stream(text, config):
                yield chunk
        else:
            # Fallback to non-streaming
            audio = await self.synthesize(text, config)
            yield audio

    async def _elevenlabs_synthesize(
        self,
        text: str,
        config: Optional[TTSConfig],
        output_format: str = "mp3",
    ) -> bytes:
        """Synthesize using ElevenLabs - OPTIMIZED for speed"""
        voice_id = config.voice_id if config else self.voice_id
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

        # Add output format and optimize_streaming_latency
        params = []
        if output_format == "pcm":
            params.append("output_format=pcm_16000")
        params.append("optimize_streaming_latency=4")  # Max optimization!

        if params:
            url += "?" + "&".join(params)

        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
        }

        payload = {
            "text": text,
            "model_id": "eleven_multilingual_v2",  # Best for Arabic! Natural pronunciation
            "voice_settings": {
                "stability": config.stability if config else 0.5,  # Higher for clearer Arabic
                "similarity_boost": config.similarity_boost if config else 0.75,
            },
        }

        # Fast HTTP client
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                url,
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            return response.content

    async def _elevenlabs_stream(
        self,
        text: str,
        config: Optional[TTSConfig],
    ) -> AsyncGenerator[bytes, None]:
        """Stream using ElevenLabs - OPTIMIZED"""
        voice_id = config.voice_id if config else self.voice_id
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream?optimize_streaming_latency=4"

        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
        }

        payload = {
            "text": text,
            "model_id": "eleven_multilingual_v2",  # Best for Arabic!
            "voice_settings": {
                "stability": config.stability if config else 0.5,
                "similarity_boost": config.similarity_boost if config else 0.75,
            },
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            async with client.stream(
                "POST",
                url,
                headers=headers,
                json=payload,
            ) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes(1024):
                    yield chunk

    async def _azure_synthesize(
        self,
        text: str,
        config: Optional[TTSConfig],
        output_format: str = "mp3",
    ) -> bytes:
        """Synthesize using Azure TTS"""
        voice = config.voice_id if config else self.voice_id

        # Validate and clean region
        region = self.region.strip() if self.region else "eastus"
        if not region or region == "undefined" or region == "null":
            region = "eastus"

        # Valid Azure regions
        valid_regions = ["eastus", "eastus2", "westus", "westus2", "westus3",
                        "centralus", "northcentralus", "southcentralus",
                        "westeurope", "northeurope", "southeastasia", "eastasia",
                        "australiaeast", "brazilsouth", "canadacentral",
                        "japaneast", "japanwest", "koreacentral", "uksouth",
                        "francecentral", "germanywestcentral", "switzerlandnorth",
                        "uaenorth", "southafricanorth", "qatarcentral"]

        if region.lower() not in valid_regions:
            logger.warning(f"Unknown Azure TTS region '{region}', using 'eastus'")
            region = "eastus"

        url = f"https://{region}.tts.speech.microsoft.com/cognitiveservices/v1"
        logger.debug(f"Azure TTS URL: {url}, Voice: {voice}")

        # Choose output format
        azure_format = "raw-16khz-16bit-mono-pcm" if output_format == "pcm" else "audio-16khz-128kbitrate-mono-mp3"

        headers = {
            "Ocp-Apim-Subscription-Key": self.api_key,
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": azure_format,
        }

        # Build SSML - optimized for natural Arabic speech
        # Extract language from voice ID (e.g., ar-SA from ar-SA-HamedNeural)
        voice_lang = "-".join(voice.split("-")[:2]) if voice else "ar-SA"

        # Use mstts namespace for natural speaking style
        speed_rate = config.speed if config else 1.0
        # Convert speed to percentage (1.0 = default, 1.2 = +20%)
        rate_percent = f"{int((speed_rate - 1) * 100):+d}%" if speed_rate != 1.0 else "default"

        ssml = f"""<speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xmlns:mstts='https://www.w3.org/2001/mstts' xml:lang='{voice_lang}'>
    <voice name='{voice}'>
        <mstts:express-as style='chat'>
            <prosody rate='{rate_percent}'>
                {text}
            </prosody>
        </mstts:express-as>
    </voice>
</speak>"""

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers=headers,
                content=ssml.strip(),
                timeout=30.0,
            )
            response.raise_for_status()
            return response.content

    async def _openai_synthesize(
        self,
        text: str,
        config: Optional[TTSConfig],
        output_format: str = "mp3",
    ) -> bytes:
        """Synthesize using OpenAI TTS"""
        url = "https://api.openai.com/v1/audio/speech"

        voice = config.voice_id if config else self.voice_id or "nova"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # OpenAI supports: mp3, opus, aac, flac, wav, pcm
        openai_format = "pcm" if output_format == "pcm" else "mp3"

        payload = {
            "model": "tts-1",  # or "tts-1-hd" for higher quality
            "input": text,
            "voice": voice,
            "response_format": openai_format,
            "speed": config.speed if config else 1.0,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers=headers,
                json=payload,
                timeout=30.0,
            )
            response.raise_for_status()
            return response.content

    async def _openai_stream(
        self,
        text: str,
        config: Optional[TTSConfig],
    ) -> AsyncGenerator[bytes, None]:
        """Stream using OpenAI TTS"""
        url = "https://api.openai.com/v1/audio/speech"

        voice = config.voice_id if config else self.voice_id or "nova"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": "tts-1",
            "input": text,
            "voice": voice,
            "response_format": "mp3",
            "speed": config.speed if config else 1.0,
        }

        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                url,
                headers=headers,
                json=payload,
                timeout=60.0,
            ) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes(1024):
                    yield chunk

    async def _deepgram_synthesize(
        self,
        text: str,
        config: Optional[TTSConfig],
        output_format: str = "mp3",
    ) -> bytes:
        """Synthesize using Deepgram Aura TTS - FASTEST option!"""
        voice = config.voice_id if config else self.voice_id or "aura-asteria-en"

        # Ensure voice has the aura prefix
        if not voice.startswith("aura-"):
            voice = f"aura-{voice}-en"

        url = f"https://api.deepgram.com/v1/speak?model={voice}"

        headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "text": text,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers=headers,
                json=payload,
                timeout=30.0,
            )
            response.raise_for_status()

            # Deepgram returns audio directly
            audio_data = response.content

            # Convert to PCM if needed (Deepgram returns MP3 by default)
            if output_format == "pcm":
                # For PCM, we'd need to decode MP3 - for now return MP3
                logger.warning("Deepgram TTS PCM output not yet supported, returning MP3")

            return audio_data

    async def _cartesia_synthesize(
        self,
        text: str,
        config: Optional[TTSConfig],
        output_format: str = "mp3",
    ) -> bytes:
        """
        Synthesize using Cartesia Sonic TTS - Ultra-low latency!

        Cartesia Sonic-2024 achieves 90ms model latency with natural voices.
        Supports 40+ languages including Arabic.
        """
        voice_id = config.voice_id if config else self.voice_id or "694f9389-aac1-45b6-b726-9d9369183238"

        url = "https://api.cartesia.ai/tts/bytes"

        headers = {
            "X-API-Key": self.api_key,
            "Cartesia-Version": "2024-11-13",  # Updated API version
            "Content-Type": "application/json",
        }

        # Output format configuration
        if output_format == "pcm":
            output_config = {
                "container": "raw",
                "encoding": "pcm_s16le",
                "sample_rate": 16000,
            }
        else:
            output_config = {
                "container": "mp3",
                "encoding": "mp3",
                "sample_rate": 24000,
            }

        payload = {
            "transcript": text,
            "model_id": "sonic-multilingual",  # Supports Arabic (auto-detects language)
            "voice": {
                "mode": "id",
                "id": voice_id,
            },
            "output_format": output_config,
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                url,
                headers=headers,
                json=payload,
            )

            if response.status_code != 200:
                logger.error(f"Cartesia TTS error: {response.status_code} - {response.text}")
                response.raise_for_status()

            return response.content

    async def _cartesia_stream(
        self,
        text: str,
        config: Optional[TTSConfig],
    ) -> AsyncGenerator[bytes, None]:
        """Stream using Cartesia WebSocket for ultra-low latency"""
        voice_id = config.voice_id if config else self.voice_id

        # For streaming, use SSE endpoint
        url = "https://api.cartesia.ai/tts/sse"

        headers = {
            "X-API-Key": self.api_key,
            "Cartesia-Version": "2024-11-13",  # Updated API version
            "Content-Type": "application/json",
        }

        payload = {
            "transcript": text,
            "model_id": "sonic-multilingual",  # Supports Arabic (auto-detects language)
            "voice": {
                "mode": "id",
                "id": voice_id,
            },
            "output_format": {
                "container": "mp3",
                "encoding": "mp3",
                "sample_rate": 24000,
            },
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            async with client.stream(
                "POST",
                url,
                headers=headers,
                json=payload,
            ) as response:
                response.raise_for_status()
                async for chunk in response.aiter_bytes(1024):
                    yield chunk

    async def _google_synthesize(
        self,
        text: str,
        config: Optional[TTSConfig],
        output_format: str = "mp3",
    ) -> bytes:
        """
        Synthesize using Google Cloud TTS - WaveNet voices!

        Google WaveNet provides high-quality voices for Arabic (ar-XA).
        """
        voice_id = config.voice_id if config else self.voice_id or "ar-XA-Wavenet-B"

        # Extract language code from voice ID (e.g., "ar-XA" from "ar-XA-Wavenet-B")
        language_code = "-".join(voice_id.split("-")[:2])

        url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={self.api_key}"

        payload = {
            "input": {"text": text},
            "voice": {
                "languageCode": language_code,
                "name": voice_id,
            },
            "audioConfig": {
                "audioEncoding": "MP3" if output_format == "mp3" else "LINEAR16",
                "speakingRate": 1.0,
                "pitch": 0,
                "sampleRateHertz": 16000,
            },
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                url,
                json=payload,
            )

            if response.status_code != 200:
                logger.error(f"Google TTS error: {response.status_code} - {response.text}")
                response.raise_for_status()

            result = response.json()
            # Google returns base64-encoded audio
            audio_content = result.get("audioContent", "")
            audio_data = base64.b64decode(audio_content)

            return audio_data

    def list_voices(self) -> Dict[str, Any]:
        """List available voices for current provider"""
        return self.ARABIC_VOICES.get(self.provider, {})


def get_tts_cache_stats() -> Dict[str, Any]:
    """Get TTS cache statistics"""
    return _tts_cache.stats()


def clear_tts_cache():
    """Clear the TTS cache"""
    global _tts_cache
    _tts_cache = TTSCache(max_size=200, ttl_seconds=7200)
