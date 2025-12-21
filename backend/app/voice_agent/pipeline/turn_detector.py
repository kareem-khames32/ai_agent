"""
Smart Turn Detection
Determines when user has finished speaking using multiple signals
"""
import time
import re
from typing import Optional, Callable, Awaitable
from dataclasses import dataclass
from enum import Enum

from ..utils.logger import get_logger
from ..config import VoiceAgentConfig

logger = get_logger(__name__)


class TurnState(Enum):
    """Turn detection states"""
    IDLE = "idle"                    # No active turn
    LISTENING = "listening"          # User is speaking
    PENDING = "pending"              # Waiting for turn end confirmation
    TURN_COMPLETE = "turn_complete"  # Turn is complete, ready for response


@dataclass
class TurnEvent:
    """Turn detection event"""
    state: TurnState
    text: str
    confidence: float
    silence_ms: float
    has_punctuation: bool


# Punctuation patterns that indicate end of thought
END_PUNCTUATION_AR = re.compile(r'[.؟!،:؛]$')
END_PUNCTUATION_EN = re.compile(r'[.?!,;:]$')


class TurnDetector:
    """
    Smart Turn Detection

    Uses multiple signals to determine turn completion:
    1. Silence duration (primary)
    2. End punctuation (reduces required silence)
    3. STT endpoint detection
    4. Maximum wait time (fallback)

    Goal: Minimize latency while avoiding interruptions
    """

    def __init__(self, config: VoiceAgentConfig):
        self.config = config
        self.state = TurnState.IDLE

        # Timing
        self.last_speech_time: Optional[float] = None
        self.turn_start_time: Optional[float] = None
        self.pending_start_time: Optional[float] = None

        # Text accumulation
        self.current_text = ""
        self.interim_text = ""

        # Callbacks
        self.on_turn_complete: Optional[Callable[[str], Awaitable[None]]] = None
        self.on_turn_start: Optional[Callable[[], Awaitable[None]]] = None

        # Configuration
        self.base_silence_ms = config.turn_silence_ms
        self.punctuation_silence_ms = config.turn_silence_ms // 2  # Faster with punctuation
        self.max_wait_ms = config.turn_max_wait_ms

        logger.info(f"TurnDetector initialized (silence={self.base_silence_ms}ms, punct_silence={self.punctuation_silence_ms}ms)")

    def reset(self):
        """Reset turn detection state"""
        self.state = TurnState.IDLE
        self.last_speech_time = None
        self.turn_start_time = None
        self.pending_start_time = None
        self.current_text = ""
        self.interim_text = ""
        logger.debug("Turn detector reset")

    async def on_speech_start(self):
        """Handle speech start event"""
        now = time.time()

        if self.state == TurnState.IDLE:
            self.state = TurnState.LISTENING
            self.turn_start_time = now
            self.current_text = ""
            self.interim_text = ""
            logger.info("🎯 Turn STARTED")

            if self.on_turn_start:
                await self.on_turn_start()

        elif self.state == TurnState.PENDING:
            # User started speaking again, cancel pending turn
            self.state = TurnState.LISTENING
            self.pending_start_time = None
            logger.debug("Turn pending cancelled - user continued speaking")

        self.last_speech_time = now

    async def on_transcript(self, text: str, is_final: bool, speech_final: bool = False):
        """
        Handle transcript update

        Args:
            text: Transcript text
            is_final: Whether this is a final transcript
            speech_final: Deepgram's speech endpoint detection
        """
        now = time.time()
        self.last_speech_time = now

        if self.state == TurnState.IDLE:
            # Start new turn
            await self.on_speech_start()

        if is_final:
            # Append final text
            if text and text.strip():
                if self.current_text:
                    self.current_text += " " + text.strip()
                else:
                    self.current_text = text.strip()
                self.interim_text = ""
                logger.debug(f"Turn text updated: \"{self.current_text}\"")
        else:
            # Update interim text
            self.interim_text = text.strip()

        # Check if speech_final indicates endpoint
        if speech_final and self.current_text:
            logger.info("🔔 STT endpoint detected")
            await self._check_turn_complete()

    async def on_speech_end(self):
        """Handle speech end from VAD"""
        if self.state == TurnState.LISTENING:
            self.state = TurnState.PENDING
            self.pending_start_time = time.time()
            logger.debug("Turn pending - silence detected")

    async def on_utterance_end(self):
        """Handle utterance end from STT"""
        if self.state in (TurnState.LISTENING, TurnState.PENDING) and self.current_text:
            logger.info("🔔 Utterance end detected")
            await self._check_turn_complete()

    async def check_timeout(self) -> bool:
        """
        Check if turn should complete based on timeout
        Call this periodically (e.g., every 50ms)

        Returns:
            True if turn completed
        """
        if self.state not in (TurnState.LISTENING, TurnState.PENDING):
            return False

        if not self.last_speech_time:
            return False

        now = time.time()
        silence_ms = (now - self.last_speech_time) * 1000

        # Determine required silence based on punctuation
        full_text = self._get_full_text()
        has_end_punct = self._has_end_punctuation(full_text)

        required_silence = self.punctuation_silence_ms if has_end_punct else self.base_silence_ms

        # Check max wait time
        if self.turn_start_time:
            turn_duration = (now - self.turn_start_time) * 1000
            if turn_duration > self.max_wait_ms and full_text:
                logger.info(f"⏰ Max wait reached ({turn_duration:.0f}ms)")
                await self._complete_turn()
                return True

        # Check silence threshold
        if silence_ms >= required_silence and full_text:
            logger.info(f"🔇 Silence threshold reached ({silence_ms:.0f}ms >= {required_silence}ms, punct={has_end_punct})")
            await self._complete_turn()
            return True

        return False

    async def _check_turn_complete(self):
        """Check if turn should complete based on current state"""
        full_text = self._get_full_text()

        if not full_text:
            return

        has_punct = self._has_end_punctuation(full_text)

        if has_punct:
            # Complete turn immediately with punctuation
            await self._complete_turn()
        else:
            # Move to pending state
            if self.state == TurnState.LISTENING:
                self.state = TurnState.PENDING
                self.pending_start_time = time.time()

    async def _complete_turn(self):
        """Complete the current turn"""
        full_text = self._get_full_text()

        if not full_text:
            self.reset()
            return

        logger.info(f"✅ Turn COMPLETE: \"{full_text}\"")

        self.state = TurnState.TURN_COMPLETE

        if self.on_turn_complete:
            await self.on_turn_complete(full_text)

        # Reset for next turn
        self.current_text = ""
        self.interim_text = ""
        self.turn_start_time = None
        self.pending_start_time = None
        self.state = TurnState.IDLE

    def _get_full_text(self) -> str:
        """Get full text including interim"""
        if self.interim_text:
            return f"{self.current_text} {self.interim_text}".strip()
        return self.current_text.strip()

    def _has_end_punctuation(self, text: str) -> bool:
        """Check if text ends with punctuation"""
        if not text:
            return False

        # Check Arabic punctuation
        if END_PUNCTUATION_AR.search(text):
            return True

        # Check English punctuation
        if END_PUNCTUATION_EN.search(text):
            return True

        return False

    @property
    def is_active(self) -> bool:
        """Check if turn is active"""
        return self.state in (TurnState.LISTENING, TurnState.PENDING)

    @property
    def current_turn_text(self) -> str:
        """Get current turn text"""
        return self._get_full_text()

    @property
    def turn_duration_ms(self) -> Optional[float]:
        """Get current turn duration in ms"""
        if self.turn_start_time:
            return (time.time() - self.turn_start_time) * 1000
        return None
