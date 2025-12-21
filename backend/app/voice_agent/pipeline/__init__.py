"""
Voice Agent Pipeline Components
"""
# Lazy imports for optional dependencies
_vad_loaded = False
_stt_loaded = False

def _load_vad():
    global _vad_loaded, VADProcessor, VADEvent, VADState
    if not _vad_loaded:
        try:
            from .vad import VADProcessor, VADEvent, VADState
            _vad_loaded = True
        except ImportError:
            VADProcessor = None
            VADEvent = None
            VADState = None

def _load_stt():
    global _stt_loaded, STTStreamer, DeepgramSTT, TranscriptEvent, TranscriptType
    if not _stt_loaded:
        from .stt import STTStreamer, DeepgramSTT, TranscriptEvent, TranscriptType
        _stt_loaded = True

# Load on import
try:
    from .vad import VADProcessor, VADEvent, VADState
except ImportError:
    # numpy not installed
    VADProcessor = None
    VADEvent = None
    VADState = None

from .stt import STTStreamer, DeepgramSTT, TranscriptEvent, TranscriptType
from .turn_detector import TurnDetector, TurnEvent, TurnState
from .llm import LLMStreamer, LLMContext, Message
from .tts import TTSStreamer, TTSProvider

__all__ = [
    "VADProcessor",
    "VADEvent",
    "VADState",
    "STTStreamer",
    "DeepgramSTT",
    "TranscriptEvent",
    "TranscriptType",
    "TurnDetector",
    "TurnEvent",
    "TurnState",
    "LLMStreamer",
    "LLMContext",
    "Message",
    "TTSStreamer",
    "TTSProvider",
]
