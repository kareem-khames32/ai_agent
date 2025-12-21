"""
Speech-to-Text using Deepgram Streaming
Real-time transcription with interim results
"""
import os
import json
import asyncio
from typing import Optional, Callable, Awaitable
from dataclasses import dataclass
from enum import Enum

from deepgram import (
    DeepgramClient,
    LiveTranscriptionEvents,
    LiveOptions,
)

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
    speech_final: bool  # Deepgram's endpoint detection
    start_time: float
    duration: float


class DeepgramSTT:
    """
    Deepgram Streaming Speech-to-Text

    Features:
    - Real-time streaming transcription
    - Interim results for low latency
    - Endpoint detection
    - Arabic language support
    """

    def __init__(self, config: VoiceAgentConfig):
        self.config = config
        self.client: Optional[DeepgramClient] = None
        self.connection = None
        self.is_connected = False

        # Callbacks
        self.on_transcript: Optional[Callable[[TranscriptEvent], Awaitable[None]]] = None
        self.on_speech_started: Optional[Callable[[], Awaitable[None]]] = None
        self.on_utterance_end: Optional[Callable[[], Awaitable[None]]] = None

        # State
        self._accumulated_text = ""
        self._last_final_text = ""

        logger.info(f"DeepgramSTT initialized (lang={config.stt_language}, model={config.stt_model})")

    async def connect(self) -> bool:
        """Connect to Deepgram streaming API"""
        try:
            api_key = os.getenv("DEEPGRAM_API_KEY")
            if not api_key:
                logger.error("DEEPGRAM_API_KEY not set")
                return False

            self.client = DeepgramClient(api_key)
            self.connection = self.client.listen.asynclive.v("1")

            # Set up event handlers
            self.connection.on(LiveTranscriptionEvents.Open, self._on_open)
            self.connection.on(LiveTranscriptionEvents.Transcript, self._on_transcript)
            self.connection.on(LiveTranscriptionEvents.SpeechStarted, self._on_speech_started)
            self.connection.on(LiveTranscriptionEvents.UtteranceEnd, self._on_utterance_end)
            self.connection.on(LiveTranscriptionEvents.Error, self._on_error)
            self.connection.on(LiveTranscriptionEvents.Close, self._on_close)

            # Configure options
            options = LiveOptions(
                model=self.config.stt_model,
                language=self.config.stt_language,
                punctuate=self.config.stt_punctuate,
                interim_results=self.config.stt_interim_results,
                endpointing=self.config.stt_endpointing_ms,
                utterance_end_ms=1000,  # Utterance end detection
                vad_events=True,
                smart_format=True,
                encoding="linear16",
                sample_rate=self.config.sample_rate_input,
                channels=self.config.channels,
            )

            # Start connection
            if await self.connection.start(options):
                self.is_connected = True
                logger.info("✅ Deepgram connected")
                return True
            else:
                logger.error("Failed to start Deepgram connection")
                return False

        except Exception as e:
            logger.error(f"Deepgram connection error: {e}")
            return False

    async def send_audio(self, audio_chunk: bytes):
        """Send audio chunk to Deepgram"""
        if self.connection and self.is_connected:
            try:
                await self.connection.send(audio_chunk)
            except Exception as e:
                logger.error(f"Error sending audio: {e}")

    async def close(self):
        """Close Deepgram connection"""
        if self.connection:
            try:
                await self.connection.finish()
            except Exception as e:
                logger.debug(f"Error closing connection: {e}")
            finally:
                self.is_connected = False
                self.connection = None
                logger.info("Deepgram connection closed")

    def reset(self):
        """Reset STT state"""
        self._accumulated_text = ""
        self._last_final_text = ""
        logger.debug("STT reset")

    async def _on_open(self, *args, **kwargs):
        """Handle connection open"""
        logger.debug("Deepgram WebSocket opened")

    async def _on_transcript(self, *args, **kwargs):
        """Handle transcript result"""
        try:
            result = kwargs.get("result") or (args[1] if len(args) > 1 else None)
            if not result:
                return

            # Extract transcript data
            channel = result.channel
            alternatives = channel.alternatives

            if not alternatives or len(alternatives) == 0:
                return

            transcript = alternatives[0].transcript
            confidence = alternatives[0].confidence

            if not transcript or not transcript.strip():
                return

            is_final = result.is_final
            speech_final = result.speech_final
            start = result.start
            duration = result.duration

            # Create event
            event = TranscriptEvent(
                text=transcript.strip(),
                is_final=is_final,
                confidence=confidence,
                speech_final=speech_final,
                start_time=start,
                duration=duration
            )

            # Log transcript
            if is_final:
                logger.info(f"📝 STT Final: \"{transcript}\" (conf={confidence:.2f}, speech_final={speech_final})")
                self._last_final_text = transcript.strip()
            else:
                logger.debug(f"📝 STT Interim: \"{transcript}\"")

            # Invoke callback
            if self.on_transcript:
                await self.on_transcript(event)

        except Exception as e:
            logger.error(f"Error processing transcript: {e}")

    async def _on_speech_started(self, *args, **kwargs):
        """Handle speech started event from Deepgram VAD"""
        logger.debug("🎤 Deepgram detected speech start")
        if self.on_speech_started:
            await self.on_speech_started()

    async def _on_utterance_end(self, *args, **kwargs):
        """Handle utterance end event"""
        logger.info("🔇 Deepgram utterance end")
        if self.on_utterance_end:
            await self.on_utterance_end()

    async def _on_error(self, *args, **kwargs):
        """Handle error event"""
        error = kwargs.get("error") or (args[1] if len(args) > 1 else "Unknown error")
        logger.error(f"Deepgram error: {error}")

    async def _on_close(self, *args, **kwargs):
        """Handle connection close"""
        self.is_connected = False
        logger.info("Deepgram connection closed")

    @property
    def last_final_text(self) -> str:
        """Get the last final transcript text"""
        return self._last_final_text
