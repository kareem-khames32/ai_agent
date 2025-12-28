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
from .prompts import is_noise_only, clean_transcript

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
        self._last_tts_audio_time = 0.0  # Track when last TTS audio was sent
        self._bargein_cooldown_ms = config.interruption_cooldown_ms
        self._bargein_energy_threshold = 0.005  # Very low threshold - trust echo cancellation

        # Barge-in (Interruption) tracking
        self._enable_interruption = config.enable_interruption
        self._interruption_words_required = config.interruption_words
        self._bargein_detecting = False  # Currently detecting barge-in
        self._bargein_word_count = 0     # Words detected during barge-in
        self._bargein_text_buffer = ""   # User's interruption text
        self._bargein_start_time = 0.0   # When barge-in detection started
        self._bargein_timeout_ms = 3000  # Max time to wait for words (3 seconds)
        self._current_ai_response = ""   # What AI is currently saying (for context)
        self._partial_ai_response = ""   # What AI was saying when interrupted
        self._in_speaking_mode = False   # Flag to block VAD callbacks during SPEAKING
        self._speaking_ended_time = 0.0  # When SPEAKING state ended (for delayed STT handling)

        # Wire up callbacks
        self._setup_callbacks()

        logger.info(f"🎙️ VoiceAgent created (call_id={self.call_id})")
        logger.info(f"   Interruption: enabled={self._enable_interruption}, words={self._interruption_words_required}, cooldown={self._bargein_cooldown_ms}ms")

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

        # Set system prompt with language from config
        language = self.config.stt_language or "ar"
        if system_prompt:
            self.llm.set_system_prompt(system_prompt, language=language)

        self._is_running = True
        await self._set_state(AgentState.LISTENING)

        # Start turn check loop
        self._turn_check_task = asyncio.create_task(self._turn_check_loop())

        logger.info(f"✅ VoiceAgent started (call_id={self.call_id}, language={language})")

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

        # Debug: Log state periodically (every ~1 second worth of audio)
        if len(audio_chunk) > 0 and hasattr(self, '_audio_chunk_count'):
            self._audio_chunk_count += 1
        else:
            self._audio_chunk_count = 1

        if self._audio_chunk_count % 25 == 1:  # Log every ~0.5 second
            logger.info(f"📊 Audio: state={self.state.value}, vad={self.vad is not None}, intr={self._enable_interruption}, detecting={self._bargein_detecting}")

        # Handle barge-in (only if interruption enabled)
        if self.state == AgentState.SPEAKING and self._enable_interruption:
            # Set flag to block VAD callbacks
            self._in_speaking_mode = True

            # ALWAYS send audio to STT during SPEAKING to detect user speech
            # Don't rely on VAD - STT will tell us if user is speaking
            await self.stt.send_audio(audio_chunk)

            # Check for barge-in timeout
            if self._bargein_detecting:
                elapsed = (time.time() - self._bargein_start_time) * 1000
                if elapsed > self._bargein_timeout_ms:
                    logger.info(f"🎤 Barge-in timeout ({elapsed:.0f}ms) - cancelling detection")
                    self._bargein_detecting = False
                    self._bargein_word_count = 0
                    self._bargein_text_buffer = ""

            return

        # Continue barge-in detection even if state changed to LISTENING
        # This handles the case where TTS finished but we're still counting words
        if self._bargein_detecting and self.state == AgentState.LISTENING:
            logger.debug(f"Continuing barge-in detection in LISTENING state (words={self._bargein_word_count})")
            # Send audio to STT to continue getting words
            await self.stt.send_audio(audio_chunk)
            return

        # Normal processing
        if self.state in (AgentState.LISTENING, AgentState.IDLE):
            # Process through VAD if available
            if self.vad:
                self.vad.process(audio_chunk)

            # Send to STT (it needs continuous audio)
            await self.stt.send_audio(audio_chunk)

    async def _handle_bargein(self, user_interruption: str = ""):
        """
        Handle user barge-in during AI response.

        Instead of just stopping and going to next step, we:
        1. Save what AI was saying (partial response)
        2. Stop TTS
        3. Process user's interruption WITH context of what AI was saying
        """
        self.latency.mark("bargein_detected")
        logger.info(f"⚠️ BARGE-IN confirmed! User said: \"{user_interruption}\"")
        logger.info(f"   AI was saying: \"{self._partial_ai_response[:100]}...\"")

        # Cancel LLM generation
        self.llm.cancel()
        self._llm_generating = False

        # Cancel TTS
        self.tts.cancel()
        self.tts.clear_queue()
        self._pending_tts_count = 0

        # Reset barge-in detection state
        self._bargein_detecting = False
        self._bargein_word_count = 0
        self._speaking_ended_time = 0.0  # Reset the window

        # Reset turn detector for new turn
        self.turn_detector.reset()

        # Set state to processing - we'll respond to the interruption
        await self._set_state(AgentState.PROCESSING)

        self.latency.mark("bargein_handled")
        self.latency.measure("bargein_detected", "bargein_handled")

        # Generate response with interruption context
        # This helps the AI acknowledge what it was saying and respond naturally
        self._response_task = asyncio.create_task(
            self._generate_interruption_response(user_interruption, self._partial_ai_response)
        )

    async def _generate_interruption_response(self, user_text: str, ai_partial_response: str):
        """
        Generate response to user's interruption with context.

        The LLM will know what it was saying when interrupted, so it can:
        - Acknowledge the interruption naturally
        - Not repeat what it already said
        - Respond to user's actual question/comment
        """
        self._llm_generating = True
        self._pending_tts_count = 0
        self._current_ai_response = ""

        try:
            # Add context about the interruption to the conversation
            # This helps the AI respond naturally
            interruption_context = f"[العميل قاطعني وأنا كنت بقول: \"{ai_partial_response[:150]}...\"] العميل قال: {user_text}"

            logger.info(f"🎯 Processing interruption with context")

            first_sentence = True
            async for token in self.llm.generate_stream(interruption_context):
                if first_sentence and self.llm.is_generating:
                    first_sentence = False

        except asyncio.CancelledError:
            logger.debug("Interruption response cancelled")
        except Exception as e:
            logger.error(f"Interruption response error: {e}")
        finally:
            self._llm_generating = False
            await self._check_speaking_complete()

    async def _set_state(self, new_state: AgentState):
        """Set agent state"""
        if self.state != new_state:
            old_state = self.state
            self.state = new_state
            logger.info(f"📊 State: {old_state.value} → {new_state.value}")

            # Track when SPEAKING state ended (for delayed STT handling)
            if old_state == AgentState.SPEAKING:
                self._in_speaking_mode = False
                self._speaking_ended_time = time.time()
                logger.debug(f"SPEAKING ended, tracking time for delayed STT")

            if self.on_state_change:
                await self.on_state_change(new_state)

    # VAD Callbacks
    def _on_vad_speech_start(self):
        """VAD detected speech start"""
        # CRITICAL: Check _in_speaking_mode FIRST - it's set before vad.process()
        if self._in_speaking_mode or self._bargein_detecting:
            logger.debug(f"VAD speech_start BLOCKED - speaking_mode={self._in_speaking_mode}, bargein={self._bargein_detecting}")
            return
        asyncio.create_task(self.turn_detector.on_speech_start())

    def _on_vad_speech_end(self, duration_ms: float):
        """VAD detected speech end"""
        # CRITICAL: Check _in_speaking_mode FIRST - it's set before vad.process()
        if self._in_speaking_mode or self._bargein_detecting:
            logger.debug(f"VAD speech_end BLOCKED - speaking_mode={self._in_speaking_mode}, bargein={self._bargein_detecting}")
            return
        self.latency.mark("speech_end")
        asyncio.create_task(self.turn_detector.on_speech_end())

    # STT Callbacks
    async def _on_stt_transcript(self, event: TranscriptEvent):
        """
        Handle STT transcript.

        ⚠️ IMPORTANT: STT results are ONLY buffered by turn detector!
        is_final and speech_final are IGNORED for turn decisions!
        Turn completion is based on VAD ONLY!
        """
        if event.is_final:
            self.latency.mark("stt_final")

        # Check if we're in SPEAKING state OR recently left it (Azure STT is slow ~500ms)
        speaking_or_recent = (
            self.state == AgentState.SPEAKING or
            (self._speaking_ended_time > 0 and time.time() - self._speaking_ended_time < 1.5)
        )

        # Handle barge-in: ANY transcript during or shortly after SPEAKING
        if speaking_or_recent and self._enable_interruption:
            if event.text and event.text.strip():
                # Start barge-in detection if not already started
                if not self._bargein_detecting:
                    self._bargein_detecting = True
                    self._bargein_start_time = time.time()
                    self._partial_ai_response = self._current_ai_response
                    logger.info(f"🎤 BARGE-IN STARTED via STT! User said: \"{event.text}\" (state={self.state.value})")

                # Count words in the transcript
                words = event.text.strip().split()
                word_count = len(words)

                # Update barge-in buffer
                self._bargein_text_buffer = event.text.strip()
                self._bargein_word_count = word_count

                logger.info(f"🎤 Barge-in words: {word_count}/{self._interruption_words_required} - \"{event.text}\"")

                # Check if we have enough words OR immediate mode (0 words)
                if self._interruption_words_required <= 0 or word_count >= self._interruption_words_required:
                    logger.info(f"🎤 ✅ BARGE-IN CONFIRMED with {word_count} words! Stopping AI...")
                    await self._handle_bargein(self._bargein_text_buffer)
                    return

            # Don't process normally during barge-in window
            return

        # Handle barge-in word counting even if state changed to LISTENING
        if self._bargein_detecting:
            if event.text and event.text.strip():
                words = event.text.strip().split()
                word_count = len(words)
                self._bargein_text_buffer = event.text.strip()
                self._bargein_word_count = word_count

                logger.info(f"🎤 Barge-in words (detecting): {word_count}/{self._interruption_words_required} - \"{event.text}\"")

                if self._interruption_words_required <= 0 or word_count >= self._interruption_words_required:
                    logger.info(f"🎤 ✅ BARGE-IN CONFIRMED with {word_count} words!")
                    await self._handle_bargein(self._bargein_text_buffer)
                    return

            return

        # Normal transcript handling (when not in barge-in detection)
        if self.state in (AgentState.LISTENING, AgentState.IDLE):
            # Buffer text in turn detector (is_final/speech_final are IGNORED!)
            await self.turn_detector.on_transcript(
                event.text,
                event.is_final,
                event.speech_final
            )

        # Notify external callback
        if self.on_transcript:
            await self.on_transcript(event.text, event.is_final)

    async def _on_stt_speech_started(self):
        """STT detected speech - not used for turn detection"""
        pass

    async def _on_stt_utterance_end(self):
        """
        STT detected utterance end.

        ⚠️ IGNORED! We don't use STT endpoint for turn decisions!
        Turn completion is based on VAD silence ONLY!
        """
        # Previously this would trigger turn completion - NOT ANYMORE!
        # await self.turn_detector.on_utterance_end()  # DISABLED!
        pass

    # Turn Detector Callbacks
    async def _on_turn_start(self):
        """Turn started"""
        await self._set_state(AgentState.LISTENING)

    async def _on_turn_complete(self, text: str):
        """Turn complete, generate response"""
        language = self.config.stt_language or "ar"

        # Filter out noise-only input (الو، ها، آه، etc.)
        if is_noise_only(text, language):
            logger.info(f"🔇 Ignoring noise-only input: \"{text}\"")
            await self._set_state(AgentState.LISTENING)
            return

        # Clean transcript (remove leading noise words)
        cleaned_text = clean_transcript(text, language)
        if not cleaned_text.strip():
            logger.info(f"🔇 Empty after cleaning: \"{text}\"")
            await self._set_state(AgentState.LISTENING)
            return

        logger.info(f"🎯 Turn complete: \"{cleaned_text}\"")

        await self._set_state(AgentState.PROCESSING)
        self.latency.mark("llm_start")

        # Generate response in background
        self._response_task = asyncio.create_task(
            self._generate_response(cleaned_text)
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
            # Reset AI response tracking for new response
            self._current_ai_response = ""
            # Reset VAD for clean barge-in detection
            if self.vad:
                self.vad.reset()
                logger.debug("VAD reset for barge-in detection")

        # Track what AI is saying (for barge-in context)
        self._current_ai_response += sentence + " "

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

        # Track when TTS audio is sent (for barge-in cooldown)
        self._last_tts_audio_time = time.time()

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
                # Don't change state if barge-in is being detected
                if self._bargein_detecting:
                    logger.debug("Speaking complete but waiting for barge-in detection")
                    return
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
