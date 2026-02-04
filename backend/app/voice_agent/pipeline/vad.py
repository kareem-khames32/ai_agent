"""
Voice Activity Detection using Energy-based Detection
Detects speech start/end with low latency
Works without numpy - uses pure Python + struct
"""
import struct
import math
from enum import Enum
from typing import Optional, Callable, List
from dataclasses import dataclass
import time

from ..utils.logger import get_logger
from ..config import VoiceAgentConfig

logger = get_logger(__name__)


class VADState(Enum):
    """Voice Activity Detection States"""
    SILENCE = "silence"
    SPEECH_START = "speech_start"
    SPEAKING = "speaking"
    SPEECH_END = "speech_end"


@dataclass
class VADEvent:
    """Event emitted by VAD"""
    state: VADState
    timestamp: float
    confidence: float
    speech_duration_ms: Optional[float] = None
    energy: Optional[float] = None  # RMS energy level


def bytes_to_float_samples(audio_bytes: bytes) -> List[float]:
    """
    Convert PCM 16-bit audio bytes to float samples [-1.0, 1.0]

    Args:
        audio_bytes: PCM 16-bit little-endian audio bytes

    Returns:
        List of float samples normalized to [-1.0, 1.0]
    """
    # Number of 16-bit samples
    num_samples = len(audio_bytes) // 2

    # Unpack all int16 samples at once
    samples = struct.unpack(f'<{num_samples}h', audio_bytes)

    # Convert to float and normalize
    return [s / 32768.0 for s in samples]


def calculate_rms(samples: List[float]) -> float:
    """
    Calculate Root Mean Square energy of audio samples

    Args:
        samples: List of float samples

    Returns:
        RMS energy value
    """
    if not samples:
        return 0.0

    # Calculate mean of squares
    sum_squares = sum(s * s for s in samples)
    mean_squares = sum_squares / len(samples)

    # Return square root
    return math.sqrt(mean_squares)


def percentile(values: List[float], p: float) -> float:
    """
    Calculate percentile of a list of values

    Args:
        values: List of float values
        p: Percentile (0-100)

    Returns:
        Value at the given percentile
    """
    if not values:
        return 0.0

    sorted_values = sorted(values)
    n = len(sorted_values)

    # Calculate index
    k = (n - 1) * p / 100.0
    f = math.floor(k)
    c = math.ceil(k)

    if f == c:
        return sorted_values[int(k)]

    # Linear interpolation
    d0 = sorted_values[int(f)] * (c - k)
    d1 = sorted_values[int(c)] * (k - f)

    return d0 + d1


class VADProcessor:
    """
    Voice Activity Detection using Energy-based Detection

    State machine:
    SILENCE → SPEECH_START → SPEAKING → SPEECH_END → SILENCE

    Features:
    - Fast detection (<50ms)
    - Adaptive threshold based on noise floor
    - Minimum speech duration filter
    - Configurable silence threshold
    - Works without numpy (pure Python)
    """

    def __init__(self, config: VoiceAgentConfig):
        self.config = config
        self.sample_rate = config.sample_rate_input

        # Energy-based VAD parameters
        # Higher thresholds to avoid picking up background audio (TV/YouTube)
        self.energy_threshold = 0.02  # Base energy threshold (doubled)
        self.adaptive_threshold = 0.02
        self.adaptation_rate = 0.05
        self.min_energy = 0.015  # Minimum energy to consider as speech (3x higher)
        self.speech_multiplier = 4.0  # Speech should be 4x noise floor (was 3x)

        # State
        self.state = VADState.SILENCE
        self.speech_start_time: Optional[float] = None
        self.last_speech_time: Optional[float] = None
        self.silence_start_time: Optional[float] = None

        # Buffers
        self.audio_buffer: List[float] = []
        self.window_size = 512  # Analysis window size (32ms at 16kHz)
        self.energy_history: List[float] = []
        self.max_history = 50  # Keep track of last N energy values

        # Callbacks
        self.on_speech_start: Optional[Callable[[], None]] = None
        self.on_speech_end: Optional[Callable[[float], None]] = None

        logger.info(f"VAD initialized (threshold={config.vad_threshold}, silence={config.vad_silence_threshold_ms}ms) [no-numpy]")

    def reset(self):
        """Reset VAD state"""
        self.state = VADState.SILENCE
        self.speech_start_time = None
        self.last_speech_time = None
        self.silence_start_time = None
        self.audio_buffer = []
        self.energy_history = []
        self.adaptive_threshold = self.energy_threshold
        logger.debug("VAD reset")

    def process(self, audio_chunk: bytes) -> Optional[VADEvent]:
        """
        Process audio chunk and detect voice activity

        Args:
            audio_chunk: PCM 16-bit audio bytes

        Returns:
            VADEvent if state changed, None otherwise
        """
        # Convert bytes to float samples
        audio_float = bytes_to_float_samples(audio_chunk)

        # Add to buffer
        self.audio_buffer.extend(audio_float)

        # Process in windows
        event = None
        while len(self.audio_buffer) >= self.window_size:
            window = self.audio_buffer[:self.window_size]
            self.audio_buffer = self.audio_buffer[self.window_size:]

            # Calculate RMS energy
            energy = calculate_rms(window)

            # Update energy history for adaptive threshold
            self.energy_history.append(energy)
            if len(self.energy_history) > self.max_history:
                self.energy_history.pop(0)

            # Calculate adaptive threshold based on noise floor
            if len(self.energy_history) >= 10:
                # Use 20th percentile as noise floor estimate
                noise_floor = percentile(self.energy_history, 20)
                # Speech should be significantly above noise floor
                self.adaptive_threshold = max(
                    self.min_energy,
                    noise_floor * self.speech_multiplier
                )

            # Calculate confidence (0-1 based on how much energy exceeds threshold)
            if self.adaptive_threshold > 0:
                confidence = min(1.0, energy / (self.adaptive_threshold * 2))
            else:
                confidence = 0.0

            # Update state based on energy
            new_event = self._update_state(energy, confidence)
            if new_event:
                event = new_event

        return event

    def _update_state(self, energy: float, confidence: float) -> Optional[VADEvent]:
        """Update state machine based on energy level"""
        now = time.time()
        is_speech = energy >= self.adaptive_threshold

        if self.state == VADState.SILENCE:
            if is_speech:
                # Potential speech start
                self.speech_start_time = now
                self.state = VADState.SPEECH_START
                logger.info(f"🎤 Speech START (energy={energy:.4f}, threshold={self.adaptive_threshold:.4f})")

                if self.on_speech_start:
                    self.on_speech_start()

                return VADEvent(
                    state=VADState.SPEECH_START,
                    timestamp=now,
                    confidence=confidence,
                    energy=energy
                )

        elif self.state == VADState.SPEECH_START:
            if is_speech:
                # Confirm speech after minimum duration
                speech_duration = (now - self.speech_start_time) * 1000
                if speech_duration >= self.config.vad_min_speech_ms:
                    self.state = VADState.SPEAKING
                    self.last_speech_time = now
                    logger.debug(f"🗣️ Confirmed SPEAKING after {speech_duration:.0f}ms")
                    return VADEvent(
                        state=VADState.SPEAKING,
                        timestamp=now,
                        confidence=confidence,
                        speech_duration_ms=speech_duration,
                        energy=energy
                    )
            else:
                # False positive, back to silence
                self.state = VADState.SILENCE
                self.speech_start_time = None
                logger.debug("False positive, back to silence")

        elif self.state == VADState.SPEAKING:
            if is_speech:
                self.last_speech_time = now
                self.silence_start_time = None
            else:
                # Potential speech end
                if self.silence_start_time is None:
                    self.silence_start_time = now
                else:
                    silence_duration = (now - self.silence_start_time) * 1000
                    if silence_duration >= self.config.vad_silence_threshold_ms:
                        # Speech ended
                        speech_duration = (self.last_speech_time - self.speech_start_time) * 1000
                        self.state = VADState.SPEECH_END
                        logger.info(f"🔇 Speech END (duration={speech_duration:.0f}ms, silence={silence_duration:.0f}ms)")

                        if self.on_speech_end:
                            self.on_speech_end(speech_duration)

                        # Reset to silence
                        event = VADEvent(
                            state=VADState.SPEECH_END,
                            timestamp=now,
                            confidence=confidence,
                            speech_duration_ms=speech_duration,
                            energy=energy
                        )
                        self.state = VADState.SILENCE
                        self.speech_start_time = None
                        self.silence_start_time = None
                        return event

        return None

    @property
    def is_speaking(self) -> bool:
        """Check if currently in speaking state"""
        return self.state in (VADState.SPEECH_START, VADState.SPEAKING)

    @property
    def speech_duration_ms(self) -> Optional[float]:
        """Get current speech duration in ms"""
        if self.speech_start_time:
            return (time.time() - self.speech_start_time) * 1000
        return None
