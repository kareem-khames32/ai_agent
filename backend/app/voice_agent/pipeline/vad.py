"""
Voice Activity Detection using Silero VAD
Detects speech start/end with low latency
"""
import numpy as np
import torch
from enum import Enum
from typing import Optional, Callable
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


class VADProcessor:
    """
    Voice Activity Detection using Silero VAD

    State machine:
    SILENCE → SPEECH_START → SPEAKING → SPEECH_END → SILENCE

    Features:
    - Fast detection (<50ms)
    - Adaptive threshold
    - Minimum speech duration filter
    - Configurable silence threshold
    """

    def __init__(self, config: VoiceAgentConfig):
        self.config = config
        self.sample_rate = config.sample_rate_input

        # Load Silero VAD model
        self.model, self.utils = torch.hub.load(
            repo_or_dir='snakers4/silero-vad',
            model='silero_vad',
            force_reload=False,
            trust_repo=True
        )
        self.model.eval()

        # State
        self.state = VADState.SILENCE
        self.speech_start_time: Optional[float] = None
        self.last_speech_time: Optional[float] = None
        self.silence_start_time: Optional[float] = None

        # Buffers
        self.audio_buffer = np.array([], dtype=np.float32)
        self.window_size = 512  # Silero VAD window size

        # Callbacks
        self.on_speech_start: Optional[Callable[[], None]] = None
        self.on_speech_end: Optional[Callable[[float], None]] = None

        logger.info(f"VAD initialized (threshold={config.vad_threshold}, silence={config.vad_silence_threshold_ms}ms)")

    def reset(self):
        """Reset VAD state"""
        self.state = VADState.SILENCE
        self.speech_start_time = None
        self.last_speech_time = None
        self.silence_start_time = None
        self.audio_buffer = np.array([], dtype=np.float32)
        self.model.reset_states()
        logger.debug("VAD reset")

    def process(self, audio_chunk: bytes) -> Optional[VADEvent]:
        """
        Process audio chunk and detect voice activity

        Args:
            audio_chunk: PCM 16-bit audio bytes

        Returns:
            VADEvent if state changed, None otherwise
        """
        # Convert bytes to float32 numpy array
        audio_int16 = np.frombuffer(audio_chunk, dtype=np.int16)
        audio_float = audio_int16.astype(np.float32) / 32768.0

        # Add to buffer
        self.audio_buffer = np.concatenate([self.audio_buffer, audio_float])

        # Process in windows
        event = None
        while len(self.audio_buffer) >= self.window_size:
            window = self.audio_buffer[:self.window_size]
            self.audio_buffer = self.audio_buffer[self.window_size:]

            # Run VAD
            tensor = torch.from_numpy(window)
            confidence = self.model(tensor, self.sample_rate).item()

            # Update state based on confidence
            event = self._update_state(confidence)

        return event

    def _update_state(self, confidence: float) -> Optional[VADEvent]:
        """Update state machine based on VAD confidence"""
        now = time.time()
        is_speech = confidence >= self.config.vad_threshold

        if self.state == VADState.SILENCE:
            if is_speech:
                # Potential speech start
                self.speech_start_time = now
                self.state = VADState.SPEECH_START
                logger.info(f"🎤 Speech START (conf={confidence:.2f})")

                if self.on_speech_start:
                    self.on_speech_start()

                return VADEvent(
                    state=VADState.SPEECH_START,
                    timestamp=now,
                    confidence=confidence
                )

        elif self.state == VADState.SPEECH_START:
            if is_speech:
                # Confirm speech
                speech_duration = (now - self.speech_start_time) * 1000
                if speech_duration >= self.config.vad_min_speech_ms:
                    self.state = VADState.SPEAKING
                    self.last_speech_time = now
                    logger.debug(f"🗣️ Confirmed SPEAKING after {speech_duration:.0f}ms")
                    return VADEvent(
                        state=VADState.SPEAKING,
                        timestamp=now,
                        confidence=confidence,
                        speech_duration_ms=speech_duration
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
                            speech_duration_ms=speech_duration
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
