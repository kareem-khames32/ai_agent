"""
Streaming Speech-to-Text Service
Uses Deepgram Live WebSocket for real-time transcription with fast endpointing
"""
import asyncio
import json
import websockets
from typing import Optional, Callable, Awaitable
from dataclasses import dataclass
from loguru import logger


@dataclass
class TranscriptResult:
    """Transcript result from STT"""
    text: str
    is_final: bool
    confidence: float = 0.0
    speech_final: bool = False  # True when utterance is complete


class StreamingSTT:
    """Real-time streaming STT using Deepgram Live WebSocket"""

    def __init__(
        self,
        api_key: str,
        language: str = "ar",
        sample_rate: int = 16000,
        encoding: str = "linear16",
        # 🚀 Endpointing settings - OPTIMIZED for low latency
        endpointing: int = 300,  # ms - fast response (was 400)
        interim_results: bool = True,
        utterance_end_ms: int = 800,  # ms - quick utterance end detection (was 1500)
        vad_events: bool = True,
    ):
        self.api_key = api_key
        self.language = language
        self.sample_rate = sample_rate
        self.encoding = encoding
        self.endpointing = endpointing
        self.interim_results = interim_results
        self.utterance_end_ms = utterance_end_ms
        self.vad_events = vad_events

        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.is_connected = False
        self._keepalive_task: Optional[asyncio.Task] = None

        # Callbacks
        self.on_transcript: Optional[Callable[[TranscriptResult], Awaitable[None]]] = None
        self.on_speech_started: Optional[Callable[[], Awaitable[None]]] = None
        self.on_speech_ended: Optional[Callable[[], Awaitable[None]]] = None
        self.on_error: Optional[Callable[[str], Awaitable[None]]] = None

    def _build_url(self) -> str:
        """Build Deepgram WebSocket URL with parameters"""
        # Use Whisper for Arabic (Nova-2 doesn't support Arabic)
        is_arabic = self.language.lower().startswith("ar")
        model = "whisper-large" if is_arabic else "nova-2"

        params = [
            f"model={model}",
            f"language={self.language}",
            f"encoding={self.encoding}",
            f"sample_rate={self.sample_rate}",
            f"channels=1",
            f"punctuate=true",
            f"interim_results={'true' if self.interim_results else 'false'}",
            f"endpointing={self.endpointing}",
            f"utterance_end_ms={self.utterance_end_ms}",
            f"vad_events={'true' if self.vad_events else 'false'}",
        ]

        return f"wss://api.deepgram.com/v1/listen?{'&'.join(params)}"

    async def connect(self) -> bool:
        """Connect to Deepgram WebSocket"""
        try:
            url = self._build_url()
            headers = {"Authorization": f"Token {self.api_key}"}

            logger.info(f"🎤 Connecting to Deepgram streaming STT...")
            self.ws = await websockets.connect(
                url,
                extra_headers=headers,
                ping_interval=5,
                ping_timeout=20,
            )
            self.is_connected = True

            # Start keepalive task
            self._keepalive_task = asyncio.create_task(self._keepalive())

            # Start receiving messages
            asyncio.create_task(self._receive_loop())

            logger.info("✅ Deepgram streaming STT connected")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to Deepgram: {e}")
            self.is_connected = False
            return False

    async def _keepalive(self):
        """Send keepalive messages to prevent timeout"""
        while self.is_connected and self.ws:
            try:
                await asyncio.sleep(8)  # Send keepalive every 8 seconds
                if self.ws and self.is_connected:
                    await self.ws.send(json.dumps({"type": "KeepAlive"}))
            except Exception:
                break

    async def _receive_loop(self):
        """Receive and process messages from Deepgram"""
        try:
            async for message in self.ws:
                if not self.is_connected:
                    break

                try:
                    data = json.loads(message)
                    await self._handle_message(data)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON from Deepgram: {message}")

        except websockets.exceptions.ConnectionClosed:
            logger.info("Deepgram connection closed")
        except Exception as e:
            logger.error(f"Error in receive loop: {e}")
        finally:
            self.is_connected = False

    async def _handle_message(self, data: dict):
        """Handle a message from Deepgram"""
        msg_type = data.get("type", "")

        if msg_type == "Results":
            # Transcription result
            channel = data.get("channel", {})
            alternatives = channel.get("alternatives", [])

            if alternatives:
                transcript = alternatives[0].get("transcript", "")
                confidence = alternatives[0].get("confidence", 0.0)
                is_final = data.get("is_final", False)
                speech_final = data.get("speech_final", False)

                if transcript.strip():
                    result = TranscriptResult(
                        text=transcript,
                        is_final=is_final,
                        confidence=confidence,
                        speech_final=speech_final,
                    )

                    if self.on_transcript:
                        await self.on_transcript(result)

                    if is_final:
                        logger.info(f"📝 Final: {transcript}")
                    else:
                        logger.debug(f"📝 Interim: {transcript}")

        elif msg_type == "SpeechStarted":
            logger.info("🎙️ Speech started (VAD)")
            if self.on_speech_started:
                await self.on_speech_started()

        elif msg_type == "UtteranceEnd":
            logger.info("🔇 Utterance ended")
            if self.on_speech_ended:
                await self.on_speech_ended()

        elif msg_type == "Error":
            error = data.get("message", "Unknown error")
            logger.error(f"Deepgram error: {error}")
            if self.on_error:
                await self.on_error(error)

        elif msg_type == "Metadata":
            logger.debug(f"Deepgram metadata: {data}")

    async def send_audio(self, audio_data: bytes):
        """Send audio chunk to Deepgram"""
        if self.ws and self.is_connected:
            try:
                await self.ws.send(audio_data)
            except Exception as e:
                logger.error(f"Failed to send audio: {e}")
                self.is_connected = False

    async def close(self):
        """Close the connection"""
        self.is_connected = False

        if self._keepalive_task:
            self._keepalive_task.cancel()
            try:
                await self._keepalive_task
            except asyncio.CancelledError:
                pass

        if self.ws:
            try:
                # Send close message
                await self.ws.send(json.dumps({"type": "CloseStream"}))
                await self.ws.close()
            except Exception:
                pass

        logger.info("🔌 Deepgram STT disconnected")


class SentenceBuffer:
    """Buffer text and detect complete sentences for TTS"""

    # Arabic and English sentence endings (ONLY full stops, not commas!)
    # Note: Arabic comma ، should NOT be here - it's used mid-sentence like English comma
    SENTENCE_ENDINGS = {'.', '!', '?', '。', '！', '？', '؟'}  # Removed ، and ؛
    # Phrase endings - only use these when buffer gets very long
    PHRASE_ENDINGS = {',', '،', ':', '؛', '-', '–'}

    def __init__(self, min_chars: int = 25, max_chars: int = 200):
        """
        Initialize sentence buffer with sensible defaults for natural speech.

        Args:
            min_chars: Minimum characters before splitting (default 25 for natural phrases)
            max_chars: Maximum characters before forcing a split (default 200 for complete thoughts)
        """
        self.buffer = ""
        self.min_chars = min_chars
        self.max_chars = max_chars

    def add(self, text: str) -> list[str]:
        """Add text and return complete sentences"""
        self.buffer += text
        sentences = []

        while True:
            # Find the first sentence ending
            earliest_end = -1
            for ending in self.SENTENCE_ENDINGS:
                pos = self.buffer.find(ending)
                if pos != -1 and (earliest_end == -1 or pos < earliest_end):
                    earliest_end = pos

            # If no sentence ending but buffer is getting long, try phrase endings
            if earliest_end == -1 and len(self.buffer) > self.max_chars:
                for ending in self.PHRASE_ENDINGS:
                    pos = self.buffer.find(ending)
                    if pos != -1 and pos >= self.min_chars:
                        if earliest_end == -1 or pos < earliest_end:
                            earliest_end = pos

            # If still nothing and buffer is very long, force break at space
            if earliest_end == -1 and len(self.buffer) > self.max_chars * 1.5:
                space_pos = self.buffer.rfind(' ', 0, self.max_chars)
                if space_pos > self.min_chars:
                    earliest_end = space_pos - 1  # Adjust for no ending character

            if earliest_end != -1 and earliest_end >= self.min_chars - 1:
                sentence = self.buffer[:earliest_end + 1].strip()
                self.buffer = self.buffer[earliest_end + 1:].strip()
                if sentence:
                    sentences.append(sentence)
            else:
                break

        return sentences

    def flush(self) -> Optional[str]:
        """Flush remaining buffer content"""
        if self.buffer.strip():
            result = self.buffer.strip()
            self.buffer = ""
            return result
        return None
