"""
Azure Streaming Speech-to-Text Service
Uses Azure Speech SDK for real-time transcription
"""
import asyncio
import queue
import threading
from typing import Optional, Callable, Awaitable
from dataclasses import dataclass
from loguru import logger

try:
    import azure.cognitiveservices.speech as speechsdk
    HAS_AZURE_SDK = True
except ImportError:
    HAS_AZURE_SDK = False
    logger.warning("Azure Speech SDK not installed. Run: pip install azure-cognitiveservices-speech")


@dataclass
class AzureTranscriptResult:
    """Transcript result from Azure STT"""
    text: str
    is_final: bool
    confidence: float = 0.0


class AzureStreamingSTT:
    """Real-time streaming STT using Azure Speech SDK"""

    def __init__(
        self,
        api_key: str,
        region: str = "eastus",
        language: str = "ar-SA",
        sample_rate: int = 16000,
    ):
        if not HAS_AZURE_SDK:
            raise ImportError("Azure Speech SDK not installed")

        self.api_key = api_key
        self.region = region
        self.language = language
        self.sample_rate = sample_rate

        self.speech_config: Optional[speechsdk.SpeechConfig] = None
        self.audio_stream: Optional[speechsdk.audio.PushAudioInputStream] = None
        self.audio_config: Optional[speechsdk.audio.AudioConfig] = None
        self.recognizer: Optional[speechsdk.SpeechRecognizer] = None

        self.is_connected = False
        self._event_loop: Optional[asyncio.AbstractEventLoop] = None

        # Thread-safe queue for results
        self._result_queue: queue.Queue = queue.Queue()
        self._process_task: Optional[asyncio.Task] = None

        # Callbacks
        self.on_transcript: Optional[Callable[[AzureTranscriptResult], Awaitable[None]]] = None
        self.on_speech_started: Optional[Callable[[], Awaitable[None]]] = None
        self.on_speech_ended: Optional[Callable[[], Awaitable[None]]] = None
        self.on_error: Optional[Callable[[str], Awaitable[None]]] = None

    async def connect(self) -> bool:
        """Initialize Azure Speech recognition"""
        try:
            self._event_loop = asyncio.get_event_loop()

            # Configure speech service
            self.speech_config = speechsdk.SpeechConfig(
                subscription=self.api_key,
                region=self.region
            )
            self.speech_config.speech_recognition_language = self.language

            # Enable detailed results
            self.speech_config.output_format = speechsdk.OutputFormat.Detailed

            # Create push audio stream (we push audio data to it)
            audio_format = speechsdk.audio.AudioStreamFormat(
                samples_per_second=self.sample_rate,
                bits_per_sample=16,
                channels=1
            )
            self.audio_stream = speechsdk.audio.PushAudioInputStream(stream_format=audio_format)
            self.audio_config = speechsdk.audio.AudioConfig(stream=self.audio_stream)

            # Create recognizer
            self.recognizer = speechsdk.SpeechRecognizer(
                speech_config=self.speech_config,
                audio_config=self.audio_config
            )

            # Set up event handlers
            self.recognizer.recognizing.connect(self._on_recognizing)
            self.recognizer.recognized.connect(self._on_recognized)
            self.recognizer.session_started.connect(self._on_session_started)
            self.recognizer.session_stopped.connect(self._on_session_stopped)
            self.recognizer.canceled.connect(self._on_canceled)

            # Start continuous recognition
            self.recognizer.start_continuous_recognition_async()
            self.is_connected = True

            # Start processing results from queue
            self._process_task = asyncio.create_task(self._process_results())

            logger.info(f"✅ Azure Streaming STT connected (region={self.region}, lang={self.language})")
            return True

        except Exception as e:
            logger.error(f"Failed to connect Azure STT: {e}")
            self.is_connected = False
            return False

    def _on_recognizing(self, evt: speechsdk.SpeechRecognitionEventArgs):
        """Handle interim results (while speaking)"""
        if evt.result.text:
            self._result_queue.put({
                "type": "recognizing",
                "text": evt.result.text,
                "is_final": False
            })

    def _on_recognized(self, evt: speechsdk.SpeechRecognitionEventArgs):
        """Handle final results (utterance complete)"""
        if evt.result.reason == speechsdk.ResultReason.RecognizedSpeech:
            if evt.result.text:
                self._result_queue.put({
                    "type": "recognized",
                    "text": evt.result.text,
                    "is_final": True
                })
        elif evt.result.reason == speechsdk.ResultReason.NoMatch:
            logger.debug("Azure STT: No speech recognized")

    def _on_session_started(self, evt):
        """Handle session start"""
        logger.info("🎙️ Azure STT session started")
        self._result_queue.put({"type": "speech_started"})

    def _on_session_stopped(self, evt):
        """Handle session stop"""
        logger.info("🔇 Azure STT session stopped")
        self._result_queue.put({"type": "speech_ended"})

    def _on_canceled(self, evt: speechsdk.SpeechRecognitionCanceledEventArgs):
        """Handle cancellation/errors"""
        if evt.reason == speechsdk.CancellationReason.Error:
            logger.error(f"Azure STT error: {evt.error_details}")
            self._result_queue.put({"type": "error", "message": evt.error_details})
        else:
            logger.info(f"Azure STT canceled: {evt.reason}")

    async def _process_results(self):
        """Process results from the queue (bridge between sync callbacks and async)"""
        while self.is_connected:
            try:
                # Check queue with timeout
                try:
                    result = self._result_queue.get_nowait()
                except queue.Empty:
                    await asyncio.sleep(0.01)  # Small sleep to avoid busy wait
                    continue

                result_type = result.get("type")

                if result_type == "recognizing":
                    # Interim result
                    if self.on_transcript:
                        await self.on_transcript(AzureTranscriptResult(
                            text=result["text"],
                            is_final=False
                        ))
                    logger.debug(f"📝 Azure interim: {result['text']}")

                elif result_type == "recognized":
                    # Final result
                    if self.on_transcript:
                        await self.on_transcript(AzureTranscriptResult(
                            text=result["text"],
                            is_final=True
                        ))
                    logger.info(f"📝 Azure final: {result['text']}")

                elif result_type == "speech_started":
                    if self.on_speech_started:
                        await self.on_speech_started()

                elif result_type == "speech_ended":
                    if self.on_speech_ended:
                        await self.on_speech_ended()

                elif result_type == "error":
                    if self.on_error:
                        await self.on_error(result.get("message", "Unknown error"))

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error processing Azure result: {e}")

    async def send_audio(self, audio_data: bytes):
        """Send audio chunk to Azure"""
        if self.audio_stream and self.is_connected:
            try:
                self.audio_stream.write(audio_data)
            except Exception as e:
                logger.error(f"Failed to send audio to Azure: {e}")

    async def close(self):
        """Close the connection"""
        self.is_connected = False

        if self._process_task:
            self._process_task.cancel()
            try:
                await self._process_task
            except asyncio.CancelledError:
                pass

        if self.recognizer:
            try:
                self.recognizer.stop_continuous_recognition_async()
            except Exception:
                pass

        if self.audio_stream:
            try:
                self.audio_stream.close()
            except Exception:
                pass

        logger.info("🔌 Azure Streaming STT disconnected")
