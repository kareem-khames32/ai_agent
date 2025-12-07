"""
Speech-to-Text Service
Supports: Deepgram, Azure Speech, OpenAI Whisper
"""
import asyncio
import base64
import json
from typing import Optional, AsyncGenerator, Dict, Any
from dataclasses import dataclass
import httpx
from loguru import logger


@dataclass
class TranscriptionResult:
    """Result from STT"""
    text: str
    confidence: float
    language: Optional[str] = None
    is_final: bool = True
    words: Optional[list] = None


class STTService:
    """Speech-to-Text service with multiple provider support"""

    def __init__(
        self,
        provider: str = "deepgram",
        api_key: Optional[str] = None,
        region: Optional[str] = None,
        language: str = "ar",  # Arabic by default
    ):
        self.provider = provider
        self.api_key = api_key
        self.region = region
        self.language = language

    async def transcribe(
        self,
        audio_data: bytes,
        sample_rate: int = 16000,
        encoding: str = "linear16",
    ) -> TranscriptionResult:
        """Transcribe audio to text"""
        if self.provider == "deepgram":
            return await self._deepgram_transcribe(audio_data, sample_rate, encoding)
        elif self.provider == "azure":
            return await self._azure_transcribe(audio_data, sample_rate, encoding)
        elif self.provider == "openai":
            return await self._openai_transcribe(audio_data)
        else:
            raise ValueError(f"Unknown STT provider: {self.provider}")

    async def _deepgram_transcribe(
        self,
        audio_data: bytes,
        sample_rate: int,
        encoding: str,
    ) -> TranscriptionResult:
        """Transcribe using Deepgram"""
        url = "https://api.deepgram.com/v1/listen"

        # Use whisper model for Arabic (nova-2 and general don't support Arabic)
        # Whisper supports 90+ languages including Arabic
        if self.language.startswith("ar"):
            params = {
                "model": "whisper-large",
                "language": "ar",
                "punctuate": "true",
            }
        else:
            params = {
                "model": "nova-2",
                "language": self.language,
                "smart_format": "true",
                "punctuate": "true",
            }

        # Set content type based on encoding
        if encoding in ["webm", "opus"]:
            content_type = "audio/webm"
            # Don't specify encoding, let Deepgram auto-detect
        elif encoding == "mp3":
            content_type = "audio/mp3"
        elif encoding == "wav":
            content_type = "audio/wav"
        else:
            # Raw PCM
            content_type = "audio/raw"
            params["encoding"] = "linear16"
            params["sample_rate"] = sample_rate

        headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": content_type,
        }

        # Debug logging
        api_key_preview = self.api_key[:10] + "..." if self.api_key and len(self.api_key) > 10 else "MISSING"
        logger.info(f"Deepgram STT: encoding={encoding}, content_type={content_type}, data_size={len(audio_data)} bytes, api_key={api_key_preview}")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                params=params,
                headers=headers,
                content=audio_data,
                timeout=30.0,
            )

            # Log error details
            if response.status_code != 200:
                logger.error(f"Deepgram error {response.status_code}: {response.text}")

            response.raise_for_status()
            result = response.json()

        # Parse response
        alternatives = result.get("results", {}).get("channels", [{}])[0].get("alternatives", [{}])
        if alternatives:
            alt = alternatives[0]
            return TranscriptionResult(
                text=alt.get("transcript", ""),
                confidence=alt.get("confidence", 0.0),
                language=result.get("results", {}).get("channels", [{}])[0].get("detected_language"),
                words=alt.get("words"),
            )

        return TranscriptionResult(text="", confidence=0.0)

    async def _azure_transcribe(
        self,
        audio_data: bytes,
        sample_rate: int,
        encoding: str,
    ) -> TranscriptionResult:
        """Transcribe using Azure Speech"""
        url = f"https://{self.region}.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1"

        # Map language to Azure format
        language_map = {
            "ar": "ar-SA",  # Saudi Arabic
            "ar-eg": "ar-EG",  # Egyptian Arabic
            "ar-sa": "ar-SA",
            "en": "en-US",
        }

        params = {
            "language": language_map.get(self.language, "ar-SA"),
        }

        headers = {
            "Ocp-Apim-Subscription-Key": self.api_key,
            "Content-Type": f"audio/raw; rate={sample_rate}; format=1channel-16bit-integer",
            "Accept": "application/json",
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                params=params,
                headers=headers,
                content=audio_data,
                timeout=30.0,
            )
            response.raise_for_status()
            result = response.json()

        return TranscriptionResult(
            text=result.get("DisplayText", ""),
            confidence=result.get("Confidence", 0.0) if "Confidence" in result else 0.9,
            language=self.language,
        )

    async def _openai_transcribe(self, audio_data: bytes) -> TranscriptionResult:
        """Transcribe using OpenAI Whisper"""
        import io

        url = "https://api.openai.com/v1/audio/transcriptions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }

        # Create form data
        files = {
            "file": ("audio.wav", io.BytesIO(audio_data), "audio/wav"),
            "model": (None, "whisper-1"),
            "language": (None, self.language[:2]),  # Whisper uses 2-letter codes
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers=headers,
                files=files,
                timeout=30.0,
            )
            response.raise_for_status()
            result = response.json()

        return TranscriptionResult(
            text=result.get("text", ""),
            confidence=0.95,  # Whisper doesn't return confidence
            language=self.language,
        )


class StreamingSTTService:
    """Streaming Speech-to-Text for real-time transcription"""

    def __init__(
        self,
        provider: str = "deepgram",
        api_key: Optional[str] = None,
        region: Optional[str] = None,
        language: str = "ar",
    ):
        self.provider = provider
        self.api_key = api_key
        self.region = region
        self.language = language
        self._ws = None

    async def connect(self) -> None:
        """Connect to streaming STT service"""
        if self.provider == "deepgram":
            await self._connect_deepgram()
        elif self.provider == "azure":
            await self._connect_azure()
        else:
            raise ValueError(f"Streaming not supported for provider: {self.provider}")

    async def _connect_deepgram(self) -> None:
        """Connect to Deepgram streaming API"""
        import websockets

        url = (
            f"wss://api.deepgram.com/v1/listen"
            f"?model=nova-2"
            f"&language={self.language}"
            f"&punctuate=true"
            f"&encoding=linear16"
            f"&sample_rate=16000"
        )

        headers = {"Authorization": f"Token {self.api_key}"}
        self._ws = await websockets.connect(url, extra_headers=headers)
        logger.info("Connected to Deepgram streaming STT")

    async def _connect_azure(self) -> None:
        """Connect to Azure streaming API"""
        # Azure uses a different streaming protocol
        # For now, we'll use batch mode
        logger.info("Azure streaming STT initialized")

    async def send_audio(self, audio_chunk: bytes) -> None:
        """Send audio chunk to STT service"""
        if self._ws:
            await self._ws.send(audio_chunk)

    async def receive_transcription(self) -> AsyncGenerator[TranscriptionResult, None]:
        """Receive transcription results"""
        if not self._ws:
            return

        async for message in self._ws:
            try:
                data = json.loads(message)

                if self.provider == "deepgram":
                    channel = data.get("channel", {})
                    alternatives = channel.get("alternatives", [{}])
                    if alternatives:
                        alt = alternatives[0]
                        yield TranscriptionResult(
                            text=alt.get("transcript", ""),
                            confidence=alt.get("confidence", 0.0),
                            is_final=data.get("is_final", False),
                            words=alt.get("words"),
                        )
            except json.JSONDecodeError:
                continue

    async def close(self) -> None:
        """Close connection"""
        if self._ws:
            await self._ws.close()
            self._ws = None
