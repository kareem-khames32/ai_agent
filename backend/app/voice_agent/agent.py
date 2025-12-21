"""
Voice Agent Orchestrator
Main pipeline that connects all components
"""
import asyncio
import time
import uuid
from typing import Optional, Callable, Awaitable
from enum import Enum

from .config import VoiceAgentConfig, get_config
from .pipeline import (
    VADProcessor, VADState, VADEvent,
    STTStreamer, TranscriptEvent,
    TurnDetector, TurnState,
    LLMStreamer,
    TTSStreamer
)
from .utils.logger import get_logger, LatencyTracker

logger = get_logger(__name__)


class AgentState(Enum):
    """Voice agent states"""
    IDLE = "idle"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"


class VoiceAgent:
    """
    Voice Agent Orchestrator

    Pipeline: Audio In → VAD → STT → Turn Detection → LLM → TTS → Audio Out

    Features:
    - End-to-end streaming
    - Sub-800ms latency target
    - Barge-in support
    - Smart turn detection
    """

    def __init__(
        self,
        config: Optional[VoiceAgentConfig] = None,
        call_id: Optional[str] = None
    ):
        self.config = config or get_config()
        self.call_id = call_id or str(uuid.uuid4())[:8]
        self.state = AgentState.IDLE

        # Latency tracking
        self.latency = LatencyTracker(self.call_id)

        # Pipeline components (VAD is optional - needs numpy)
        self.vad = VADProcessor(self.config) if VADProcessor else None
        self.stt = STTStreamer(self.config)  # Multi-provider STT
        self.turn_detector = TurnDetector(self.config)
        self.llm = LLMStreamer(self.config)
        self.tts = TTSStreamer(self.config)

        # Callbacks
        self.on_audio_output: Optional[Callable[[bytes], Awaitable[None]]] = None
        self.on_transcript: Optional[Callable[[str, bool], Awaitable[None]]] = None
        self.on_response: Optional[Callable[[str], Awaitable[None]]] = None
        self.on_state_change: Optional[Callable[[AgentState], Awaitable[None]]] = None

        # Internal state
        self._is_running = False
        self._turn_check_task: Optional[asyncio.Task] = None
        self._response_task: Optional[asyncio.Task] = None
        self._llm_generating = False  # Track if LLM is still generating
        self._pending_tts_count = 0   # Track pending TTS sentences

        # Wire up callbacks
        self._setup_callbacks()

        logger.info(f"🎙️ VoiceAgent created (call_id={self.call_id})")

    def _setup_callbacks(self):
        """Wire up internal callbacks between components"""

        # VAD callbacks (optional - needs numpy)
        if self.vad:
            self.vad.on_speech_start = self._on_vad_speech_start
            self.vad.on_speech_end = self._on_vad_speech_end

        # STT callbacks
        self.stt.on_transcript = self._on_stt_transcript
        self.stt.on_speech_started = self._on_stt_speech_started
        self.stt.on_utterance_end = self._on_stt_utterance_end

        # Turn detector callbacks
        self.turn_detector.on_turn_complete = self._on_turn_complete
        self.turn_detector.on_turn_start = self._on_turn_start

        # LLM callbacks
        self.llm.on_sentence = self._on_llm_sentence
        self.llm.on_complete = self._on_llm_complete

        # TTS callbacks
        self.tts.on_audio_chunk = self._on_tts_audio
        self.tts.on_speech_start = self._on_tts_speech_start
        self.tts.on_speech_end = self._on_tts_speech_end

    async def start(self, system_prompt: str = ""):
        """Start the voice agent"""
        logger.info(f"🚀 Starting VoiceAgent (call_id={self.call_id})")

        # Initialize components
        if not await self.stt.connect():
            raise RuntimeError("Failed to connect to STT")

        if not await self.tts.initialize():
            raise RuntimeError("Failed to initialize TTS")

        if not await self.llm.initialize():
            raise RuntimeError("Failed to initialize LLM")

        # Set system prompt
        if system_prompt:
            self.llm.set_system_prompt(system_prompt)

        self._is_running = True
        await self._set_state(AgentState.LISTENING)

        # Start turn check loop
        self._turn_check_task = asyncio.create_task(self._turn_check_loop())

        logger.info(f"✅ VoiceAgent started (call_id={self.call_id})")

    async def stop(self):
        """Stop the voice agent"""
        logger.info(f"🛑 Stopping VoiceAgent (call_id={self.call_id})")

        self._is_running = False

        # Cancel tasks
        if self._turn_check_task:
            self._turn_check_task.cancel()
        if self._response_task:
            self._response_task.cancel()

        # Close components
        await self.stt.close()
        await self.tts.close()

        # Report latency
        self.latency.report()

        logger.info(f"✅ VoiceAgent stopped (call_id={self.call_id})")

    async def process_audio(self, audio_chunk: bytes):
        """
        Process incoming audio chunk

        Args:
            audio_chunk: PCM 16-bit audio bytes
        """
        if not self._is_running:
            return

        # Handle barge-in (only if VAD available)
        if self.state == AgentState.SPEAKING and self.vad and VADState:
            # Check VAD for user speech during AI response
            vad_event = self.vad.process(audio_chunk)
            if vad_event and vad_event.state == VADState.SPEECH_START:
                await self._handle_bargein()
                return

        # Normal processing
        if self.state in (AgentState.LISTENING, AgentState.IDLE):
            # Process through VAD if available
            if self.vad:
                self.vad.process(audio_chunk)

            # Send to STT (it needs continuous audio)
            await self.stt.send_audio(audio_chunk)

    async def _handle_bargein(self):
        """Handle user barge-in during AI response"""
        self.latency.mark("bargein_detected")
        logger.info("⚠️ BARGE-IN detected!")

        # Cancel LLM generation
        self.llm.cancel()
        self._llm_generating = False

        # Cancel TTS
        self.tts.cancel()
        self.tts.clear_queue()
        self._pending_tts_count = 0

        # Reset state
        await self._set_state(AgentState.LISTENING)

        self.latency.mark("bargein_handled")
        self.latency.measure("bargein_detected", "bargein_handled")

    async def _set_state(self, new_state: AgentState):
        """Set agent state"""
        if self.state != new_state:
            old_state = self.state
            self.state = new_state
            logger.info(f"📊 State: {old_state.value} → {new_state.value}")

            if self.on_state_change:
                await self.on_state_change(new_state)

    # VAD Callbacks
    def _on_vad_speech_start(self):
        """VAD detected speech start"""
        asyncio.create_task(self.turn_detector.on_speech_start())

    def _on_vad_speech_end(self, duration_ms: float):
        """VAD detected speech end"""
        self.latency.mark("speech_end")
        asyncio.create_task(self.turn_detector.on_speech_end())

    # STT Callbacks
    async def _on_stt_transcript(self, event: TranscriptEvent):
        """Handle STT transcript"""
        if event.is_final:
            self.latency.mark("stt_final")

        # Update turn detector
        await self.turn_detector.on_transcript(
            event.text,
            event.is_final,
            event.speech_final
        )

        # Notify external callback
        if self.on_transcript:
            await self.on_transcript(event.text, event.is_final)

    async def _on_stt_speech_started(self):
        """STT detected speech"""
        pass

    async def _on_stt_utterance_end(self):
        """STT detected utterance end"""
        await self.turn_detector.on_utterance_end()

    # Turn Detector Callbacks
    async def _on_turn_start(self):
        """Turn started"""
        await self._set_state(AgentState.LISTENING)

    async def _on_turn_complete(self, text: str):
        """Turn complete, generate response"""
        logger.info(f"🎯 Turn complete: \"{text}\"")

        await self._set_state(AgentState.PROCESSING)
        self.latency.mark("llm_start")

        # Generate response in background
        self._response_task = asyncio.create_task(
            self._generate_response(text)
        )

    async def _generate_response(self, user_text: str):
        """Generate and speak response"""
        self._llm_generating = True
        self._pending_tts_count = 0

        try:
            first_sentence = True

            async for token in self.llm.generate_stream(user_text):
                if first_sentence and self.llm.is_generating:
                    first_sentence = False
                    # Will be handled by on_sentence callback

        except asyncio.CancelledError:
            logger.debug("Response generation cancelled")
        except Exception as e:
            logger.error(f"Response generation error: {e}")
        finally:
            self._llm_generating = False
            # Check if we should go back to listening
            await self._check_speaking_complete()

    # LLM Callbacks
    async def _on_llm_sentence(self, sentence: str):
        """LLM generated a sentence"""
        if self.state == AgentState.PROCESSING:
            self.latency.mark("llm_first_token")
            await self._set_state(AgentState.SPEAKING)
            self.latency.mark("tts_start")

        # Track pending TTS
        self._pending_tts_count += 1

        # Speak the sentence
        await self.tts.speak(sentence)

        # Decrement after speaking completes
        self._pending_tts_count -= 1
        await self._check_speaking_complete()

    async def _on_llm_complete(self, response: str):
        """LLM finished generating"""
        if self.on_response:
            await self.on_response(response)

    # TTS Callbacks
    async def _on_tts_audio(self, audio_chunk: bytes):
        """TTS generated audio chunk"""
        self.latency.mark("tts_first_byte")

        if self.on_audio_output:
            await self.on_audio_output(audio_chunk)

    async def _on_tts_speech_start(self):
        """TTS started speaking"""
        self.latency.mark("first_audio_byte")

    async def _on_tts_speech_end(self):
        """TTS finished speaking a sentence"""
        # We track speaking completion via _check_speaking_complete
        pass

    async def _check_speaking_complete(self):
        """Check if all speaking is complete and we can go back to listening"""
        if not self._llm_generating and self._pending_tts_count <= 0:
            if self.state == AgentState.SPEAKING:
                await self._set_state(AgentState.LISTENING)

    # Turn check loop
    async def _turn_check_loop(self):
        """Periodically check for turn completion"""
        while self._is_running:
            try:
                await self.turn_detector.check_timeout()
                await asyncio.sleep(0.05)  # Check every 50ms
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Turn check error: {e}")

    # Properties
    @property
    def is_running(self) -> bool:
        """Check if agent is running"""
        return self._is_running

    @property
    def current_state(self) -> str:
        """Get current state"""
        return self.state.value
