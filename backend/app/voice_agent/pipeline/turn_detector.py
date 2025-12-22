"""
VAD-Based Turn Detection
Determines when user has finished speaking using VAD ONLY

CRITICAL: STT endpoint/is_final is IGNORED for turn decisions!
VAD is the ONLY source of truth for speech timing.
STT is only used for converting audio to text.
"""
import time
import re
from typing import Optional, Callable, Awaitable, List
from dataclasses import dataclass
from enum import Enum

from ..utils.logger import get_logger
from ..config import VoiceAgentConfig

logger = get_logger(__name__)


class TurnState(Enum):
    """Turn detection states"""
    IDLE = "idle"                    # No active turn
    LISTENING = "listening"          # User is speaking (VAD says so)
    PENDING = "pending"              # VAD speech ended, waiting for silence threshold
    TURN_COMPLETE = "turn_complete"  # Turn is complete, ready for response


@dataclass
class TurnEvent:
    """Turn detection event"""
    state: TurnState
    text: str
    confidence: float
    silence_ms: float
    has_punctuation: bool


class TurnDetector:
    """
    VAD-Based Turn Detection

    CRITICAL DESIGN PRINCIPLE:
    - VAD is the ONLY source of truth for when speech starts/ends
    - STT is ONLY used for text buffering, NOT for turn decisions
    - We IGNORE STT is_final and speech_final completely!

    Turn completion logic:
    1. VAD detects speech start → start buffering STT text
    2. VAD detects speech end → start silence timer
    3. Silence timer reaches threshold → combine buffer → turn complete
    4. If VAD detects new speech during pending → cancel pending, continue buffering

    This prevents the issue where STT sends "final" results mid-sentence
    based on punctuation, causing premature turn completion.
    """

    def __init__(self, config: VoiceAgentConfig):
        self.config = config
        self.state = TurnState.IDLE

        # VAD-based timing (the ONLY source of truth!)
        self.vad_speech_start_time: Optional[float] = None
        self.vad_speech_end_time: Optional[float] = None
        self.turn_start_time: Optional[float] = None

        # TEXT BUFFER - Collects ALL STT results until VAD confirms speech end
        self.text_buffer: List[str] = []
        self.last_text_time: Optional[float] = None

        # Callbacks
        self.on_turn_complete: Optional[Callable[[str], Awaitable[None]]] = None
        self.on_turn_start: Optional[Callable[[], Awaitable[None]]] = None

        # Silence thresholds AFTER VAD says speech ended
        # Note: VAD already waits ~500ms before firing on_speech_end
        # So these are ADDITIONAL wait times on top of VAD's silence
        self.min_silence_after_speech_ms = 300  # Base: +300ms after VAD (total ~800ms)
        self.extended_silence_ms = 700          # For incomplete sentences: +700ms (total ~1200ms)
        self.quick_response_silence_ms = 100    # For quick responses: +100ms (total ~600ms)
        self.max_wait_ms = config.turn_max_wait_ms

        # Quick response words (can complete with shorter silence)
        self.quick_responses = {
            "نعم", "لا", "ايوه", "أيوه", "لأ", "ماشي", "تمام", "طيب", "حاضر",
            "اه", "آه", "مم", "اوك", "اوكي", "صح", "غلط", "موافق",
            "yes", "no", "ok", "okay", "yeah", "yep", "nope"
        }

        # Incomplete sentence markers (need longer silence)
        self.incomplete_markers = {
            "و", "أو", "بس", "لكن", "يعني", "إن", "الله", "في", "على", "من",
            "and", "or", "but", "because", "if", "when", "that"
        }

        logger.info(f"TurnDetector initialized - VAD-ONLY mode (base_silence=+{self.min_silence_after_speech_ms}ms, quick=+{self.quick_response_silence_ms}ms)")

    def reset(self):
        """Reset turn detection state"""
        self.state = TurnState.IDLE
        self.vad_speech_start_time = None
        self.vad_speech_end_time = None
        self.turn_start_time = None
        self.text_buffer = []
        self.last_text_time = None
        logger.debug("Turn detector reset")

    # ========================================
    # VAD CALLBACKS - The ONLY source of truth!
    # ========================================

    async def on_vad_speech_start(self):
        """
        Called when VAD detects speech started.
        This is the ONLY way to start a turn!
        """
        now = time.time()

        if self.state == TurnState.IDLE:
            # New turn starting
            self.state = TurnState.LISTENING
            self.vad_speech_start_time = now
            self.turn_start_time = now
            self.text_buffer = []  # Clear buffer for new turn
            self.vad_speech_end_time = None
            logger.info("🎯 Turn STARTED (VAD speech start)")

            if self.on_turn_start:
                await self.on_turn_start()

        elif self.state == TurnState.PENDING:
            # User started speaking again during pending!
            # Cancel the pending turn completion
            self.state = TurnState.LISTENING
            self.vad_speech_end_time = None
            logger.info("↩️ Turn pending CANCELLED - user continued speaking")

    async def on_vad_speech_end(self):
        """
        Called when VAD detects speech ended.
        This starts the silence timer for turn completion.
        """
        if self.state == TurnState.LISTENING:
            self.state = TurnState.PENDING
            self.vad_speech_end_time = time.time()
            logger.info("🔇 VAD speech END - starting silence timer")

    # For backward compatibility with old callback names
    async def on_speech_start(self):
        """Alias for on_vad_speech_start"""
        await self.on_vad_speech_start()

    async def on_speech_end(self):
        """Alias for on_vad_speech_end"""
        await self.on_vad_speech_end()

    # ========================================
    # STT CALLBACKS - Text buffering ONLY!
    # ========================================

    async def on_transcript(self, text: str, is_final: bool, speech_final: bool = False):
        """
        Handle STT transcript.

        ⚠️ CRITICAL: We IGNORE is_final and speech_final!
        We only buffer the text here, NOT make turn decisions!
        Turn decisions are based on VAD ONLY!

        Args:
            text: Transcript text
            is_final: IGNORED - STT's idea of "final" based on punctuation
            speech_final: IGNORED - STT's endpoint detection
        """
        if not text or not text.strip():
            return

        text = text.strip()
        now = time.time()

        # If we get text but turn hasn't started yet, start it
        # (This handles cases where VAD callback might be delayed)
        if self.state == TurnState.IDLE:
            await self.on_vad_speech_start()

        # Buffer the text (avoid duplicates)
        if not self.text_buffer or not self._is_duplicate(text):
            self.text_buffer.append(text)
            self.last_text_time = now
            logger.debug(f"📝 STT buffered: \"{text}\" (is_final={is_final} - IGNORED!)")

        # ❌ DO NOT call _check_turn_complete() here!
        # ❌ DO NOT use speech_final for any decision!
        # Turn completion is handled by check_timeout() based on VAD timing

    async def on_utterance_end(self):
        """
        Handle utterance end from STT.

        ⚠️ IGNORED! We don't use STT utterance end for turn decisions!
        """
        # Previously this would trigger turn completion - NOT ANYMORE!
        logger.debug("🔔 STT utterance end - IGNORED (using VAD only)")
        pass

    # ========================================
    # TURN COMPLETION LOGIC - Based on VAD timing!
    # ========================================

    async def check_timeout(self) -> bool:
        """
        Check if turn should complete based on VAD silence duration.
        Call this periodically (e.g., every 50ms).

        This is the ONLY place where turn completion decisions are made!

        Returns:
            True if turn completed
        """
        # Only check in PENDING state (VAD detected speech end)
        if self.state != TurnState.PENDING:
            return False

        if self.vad_speech_end_time is None:
            return False

        # Get combined text from buffer
        full_text = self._combine_buffer()

        # No text? Nothing to respond to
        if not full_text:
            return False

        # Calculate silence duration since VAD said speech ended
        now = time.time()
        silence_ms = (now - self.vad_speech_end_time) * 1000

        # Determine required silence based on text characteristics
        required_silence = self._get_required_silence(full_text)

        # Check max wait time (fallback)
        if self.turn_start_time:
            turn_duration = (now - self.turn_start_time) * 1000
            if turn_duration > self.max_wait_ms:
                word_count = self._get_word_count(full_text)
                logger.info(f"⏰ Max wait reached ({turn_duration:.0f}ms, words={word_count})")
                await self._complete_turn(full_text)
                return True

        # Check if silence threshold reached
        if silence_ms >= required_silence:
            word_count = self._get_word_count(full_text)
            logger.info(f"🔇 Silence threshold reached ({silence_ms:.0f}ms >= {required_silence}ms, words={word_count})")
            await self._complete_turn(full_text)
            return True

        return False

    async def _complete_turn(self, full_text: str):
        """Complete the current turn with the combined text"""
        if not full_text:
            self.reset()
            return

        word_count = self._get_word_count(full_text)
        logger.info(f"✅ Turn COMPLETE ({word_count} words): \"{full_text}\"")

        self.state = TurnState.TURN_COMPLETE

        if self.on_turn_complete:
            await self.on_turn_complete(full_text)

        # Reset for next turn
        self.text_buffer = []
        self.turn_start_time = None
        self.vad_speech_start_time = None
        self.vad_speech_end_time = None
        self.last_text_time = None
        self.state = TurnState.IDLE

    # ========================================
    # TEXT BUFFER UTILITIES
    # ========================================

    def _combine_buffer(self) -> str:
        """
        Combine all buffered STT results into single coherent text.
        Handles overlapping/duplicate text from STT.
        """
        if not self.text_buffer:
            return ""

        # Smart merge - handle overlaps
        combined = self.text_buffer[0]

        for i in range(1, len(self.text_buffer)):
            new_text = self.text_buffer[i]
            combined = self._smart_merge(combined, new_text)

        return combined.strip()

    def _smart_merge(self, existing: str, new: str) -> str:
        """
        Merge two text strings, handling overlaps.
        STT often sends overlapping text chunks.
        """
        if not existing:
            return new
        if not new:
            return existing

        # Check if new text is completely contained in existing
        if new in existing:
            return existing

        # Check if existing ends with start of new (overlap)
        existing_words = existing.split()
        new_words = new.split()

        # Find overlap
        for overlap_size in range(min(len(existing_words), len(new_words)), 0, -1):
            if existing_words[-overlap_size:] == new_words[:overlap_size]:
                # Found overlap, merge without duplicating
                return existing + " " + " ".join(new_words[overlap_size:])

        # No overlap found, just concatenate
        return existing + " " + new

    def _is_duplicate(self, new_text: str) -> bool:
        """Check if text is duplicate of last buffer entry"""
        if not self.text_buffer:
            return False

        last_text = self.text_buffer[-1]

        # Exact match
        if new_text == last_text:
            return True

        # New text is subset of last
        if new_text in last_text:
            return True

        return False

    # ========================================
    # SILENCE THRESHOLD CALCULATION
    # ========================================

    def _get_required_silence(self, text: str) -> float:
        """
        Determine ADDITIONAL silence duration after VAD speech_end.

        Note: VAD already waits ~500ms before firing speech_end.
        These are additional wait times:
        - Quick response: +100ms (total ~600ms)
        - Normal sentence: +300ms (total ~800ms)
        - Incomplete: +700ms (total ~1200ms)
        """
        word_count = self._get_word_count(text)
        is_quick = self._is_quick_response(text)
        is_incomplete = self._looks_incomplete(text)

        # Quick responses (نعم، لا، تمام، etc.) - almost immediate
        if is_quick and word_count == 1:
            return self.quick_response_silence_ms  # +100ms

        # Single word but not a quick response - wait more
        if word_count == 1:
            return self.extended_silence_ms  # +700ms

        # Looks incomplete - wait longer
        if is_incomplete:
            return self.extended_silence_ms  # +700ms

        # 2-3 words - moderate wait
        if word_count <= 3:
            return self.min_silence_after_speech_ms + 150  # +450ms

        # Normal sentence (4+ words)
        return self.min_silence_after_speech_ms  # +300ms

    def _get_word_count(self, text: str) -> int:
        """Get word count from text"""
        if not text:
            return 0
        words = [w for w in text.split() if w.strip()]
        return len(words)

    def _is_quick_response(self, text: str) -> bool:
        """Check if text is a quick response word"""
        if not text:
            return False
        # Normalize and check
        normalized = text.strip().lower()
        # Remove punctuation for comparison
        normalized = re.sub(r'[.؟!،:؛?!,;:]', '', normalized).strip()
        return normalized in self.quick_responses or normalized in {r.lower() for r in self.quick_responses}

    def _looks_incomplete(self, text: str) -> bool:
        """Check if text looks like an incomplete sentence"""
        if not text:
            return False

        # Get last word
        words = text.split()
        if not words:
            return False

        last_word = words[-1].strip()
        # Remove punctuation
        last_word_clean = re.sub(r'[.؟!،:؛?!,;:]', '', last_word).strip()

        # Check if last word is an incomplete marker
        if last_word_clean in self.incomplete_markers:
            return True

        return False

    # ========================================
    # PROPERTIES
    # ========================================

    @property
    def is_active(self) -> bool:
        """Check if turn is active"""
        return self.state in (TurnState.LISTENING, TurnState.PENDING)

    @property
    def current_turn_text(self) -> str:
        """Get current turn text"""
        return self._combine_buffer()

    @property
    def turn_duration_ms(self) -> Optional[float]:
        """Get current turn duration in ms"""
        if self.turn_start_time:
            return (time.time() - self.turn_start_time) * 1000
        return None

    def force_complete(self) -> Optional[str]:
        """Force turn completion (e.g., on timeout or disconnect)"""
        if self.text_buffer:
            text = self._combine_buffer()
            self.reset()
            return text
        return None
