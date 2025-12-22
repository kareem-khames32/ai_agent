"""
Call Recorder - Records and stores call audio, transcripts, and analytics
"""
import asyncio
import io
import time
import wave
import json
import os
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field, asdict
from pathlib import Path
from enum import Enum

from .utils.logger import get_logger

logger = get_logger(__name__)


class CallStatus(Enum):
    """Call status"""
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TranscriptEntry:
    """Single transcript entry"""
    role: str  # "user" or "assistant"
    text: str
    timestamp: float  # seconds from call start
    is_final: bool = True


@dataclass
class CallMetrics:
    """Call performance metrics"""
    total_latency_ms: float = 0.0
    avg_response_latency_ms: float = 0.0
    stt_latency_ms: float = 0.0
    llm_latency_ms: float = 0.0
    tts_latency_ms: float = 0.0
    response_count: int = 0

    # Token counts (for cost estimation)
    input_tokens: int = 0
    output_tokens: int = 0

    # Audio duration
    user_audio_duration_sec: float = 0.0
    assistant_audio_duration_sec: float = 0.0


@dataclass
class CallCost:
    """Call cost breakdown"""
    stt_cost: float = 0.0
    llm_cost: float = 0.0
    tts_cost: float = 0.0
    total_cost: float = 0.0
    currency: str = "USD"


@dataclass
class CallLog:
    """Complete call log entry"""
    call_id: str
    assistant_id: Optional[str] = None
    assistant_name: Optional[str] = None

    # Mode
    voice_mode: str = "pipeline"  # pipeline or realtime
    realtime_provider: Optional[str] = None

    # Timestamps
    started_at: str = ""
    ended_at: str = ""
    duration_sec: float = 0.0

    # Status
    status: str = "in_progress"
    end_reason: str = ""  # user_hangup, timeout, error, etc.

    # Configuration
    llm_provider: str = ""
    llm_model: str = ""
    stt_provider: str = ""
    tts_provider: str = ""
    voice_id: str = ""
    language: str = ""

    # Transcripts
    transcripts: List[Dict[str, Any]] = field(default_factory=list)

    # Metrics
    metrics: Dict[str, Any] = field(default_factory=dict)

    # Cost
    cost: Dict[str, Any] = field(default_factory=dict)

    # Recording
    recording_url: Optional[str] = None
    recording_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class CallRecorder:
    """
    Records call audio and tracks analytics

    Features:
    - Records user and assistant audio separately
    - Tracks latency metrics
    - Stores transcripts
    - Calculates cost estimates
    - Saves call logs
    """

    # Cost per minute/token (approximate)
    COST_RATES = {
        "stt": {
            "deepgram": 0.0043,  # per minute
            "azure": 0.0167,
            "openai": 0.006,
            "groq": 0.0007,
            "munsit": 0.01,
        },
        "llm": {
            "openai": {"input": 0.0025, "output": 0.01},  # per 1K tokens
            "anthropic": {"input": 0.003, "output": 0.015},
            "google": {"input": 0.000125, "output": 0.0005},
            "groq": {"input": 0.00059, "output": 0.00079},
        },
        "tts": {
            "elevenlabs": 0.0003,  # per character
            "azure": 0.000016,
            "openai": 0.000015,
            "deepgram": 0.00003,
        },
        "realtime": {
            "openai": {"input": 0.06, "output": 0.24},  # per minute audio
            "google": {"input": 0.0, "output": 0.0},  # Free tier
        }
    }

    def __init__(
        self,
        call_id: str,
        sample_rate: int = 16000,
        channels: int = 1,
        recordings_dir: str = "recordings"
    ):
        self.call_id = call_id
        self.sample_rate = sample_rate
        self.channels = channels
        self.recordings_dir = Path(recordings_dir)
        self.recordings_dir.mkdir(parents=True, exist_ok=True)

        # Call log
        self.call_log = CallLog(
            call_id=call_id,
            started_at=datetime.utcnow().isoformat(),
            status=CallStatus.IN_PROGRESS.value
        )

        # Audio buffers
        self._user_audio_buffer = io.BytesIO()
        self._assistant_audio_buffer = io.BytesIO()
        self._combined_audio_buffer = io.BytesIO()

        # Timing
        self._start_time = time.time()
        self._last_user_speech_end: Optional[float] = None
        self._response_start_time: Optional[float] = None

        # Metrics tracking
        self._latencies: List[float] = []
        self._metrics = CallMetrics()
        self._cost = CallCost()

        # Transcripts
        self._transcripts: List[TranscriptEntry] = []

        logger.info(f"📹 Call recorder initialized: {call_id}")

    def set_config(
        self,
        voice_mode: str = "pipeline",
        realtime_provider: Optional[str] = None,
        llm_provider: str = "",
        llm_model: str = "",
        stt_provider: str = "",
        tts_provider: str = "",
        voice_id: str = "",
        language: str = "",
        assistant_id: Optional[str] = None,
        assistant_name: Optional[str] = None
    ):
        """Set call configuration"""
        self.call_log.voice_mode = voice_mode
        self.call_log.realtime_provider = realtime_provider
        self.call_log.llm_provider = llm_provider
        self.call_log.llm_model = llm_model
        self.call_log.stt_provider = stt_provider
        self.call_log.tts_provider = tts_provider
        self.call_log.voice_id = voice_id
        self.call_log.language = language
        self.call_log.assistant_id = assistant_id
        self.call_log.assistant_name = assistant_name

    def record_user_audio(self, audio_chunk: bytes):
        """Record user audio chunk"""
        self._user_audio_buffer.write(audio_chunk)
        self._combined_audio_buffer.write(audio_chunk)

        # Update metrics
        duration = len(audio_chunk) / (self.sample_rate * 2)  # 16-bit audio
        self._metrics.user_audio_duration_sec += duration

    def record_assistant_audio(self, audio_chunk: bytes):
        """Record assistant audio chunk"""
        self._assistant_audio_buffer.write(audio_chunk)
        self._combined_audio_buffer.write(audio_chunk)

        # Update metrics
        duration = len(audio_chunk) / (self.sample_rate * 2)
        self._metrics.assistant_audio_duration_sec += duration

    def add_transcript(self, text: str, role: str, is_final: bool = True):
        """Add transcript entry"""
        entry = TranscriptEntry(
            role=role,
            text=text,
            timestamp=time.time() - self._start_time,
            is_final=is_final
        )
        self._transcripts.append(entry)

        # Update token estimates (rough: 1 token ≈ 4 chars)
        tokens = len(text) // 4
        if role == "user":
            self._metrics.input_tokens += tokens
        else:
            self._metrics.output_tokens += tokens

    def mark_user_speech_end(self):
        """Mark when user finished speaking (for latency calculation)"""
        self._last_user_speech_end = time.time()

    def mark_response_start(self):
        """Mark when assistant started responding"""
        if self._last_user_speech_end:
            latency = (time.time() - self._last_user_speech_end) * 1000
            self._latencies.append(latency)
            self._metrics.response_count += 1
            logger.debug(f"📊 Response latency: {latency:.0f}ms")

    def update_latency(self, stt_ms: float = 0, llm_ms: float = 0, tts_ms: float = 0):
        """Update component latencies"""
        self._metrics.stt_latency_ms = stt_ms
        self._metrics.llm_latency_ms = llm_ms
        self._metrics.tts_latency_ms = tts_ms

    def _calculate_cost(self):
        """Calculate estimated cost"""
        voice_mode = self.call_log.voice_mode

        if voice_mode == "realtime":
            # Realtime API pricing (per minute)
            provider = self.call_log.realtime_provider or "openai"
            rates = self.COST_RATES["realtime"].get(provider, {"input": 0, "output": 0})

            input_minutes = self._metrics.user_audio_duration_sec / 60
            output_minutes = self._metrics.assistant_audio_duration_sec / 60

            self._cost.total_cost = (input_minutes * rates["input"]) + (output_minutes * rates["output"])
        else:
            # Pipeline pricing
            # STT cost
            stt_provider = self.call_log.stt_provider
            stt_rate = self.COST_RATES["stt"].get(stt_provider, 0.005)
            stt_minutes = self._metrics.user_audio_duration_sec / 60
            self._cost.stt_cost = stt_minutes * stt_rate

            # LLM cost
            llm_provider = self.call_log.llm_provider
            llm_rates = self.COST_RATES["llm"].get(llm_provider, {"input": 0.002, "output": 0.01})
            self._cost.llm_cost = (
                (self._metrics.input_tokens / 1000) * llm_rates["input"] +
                (self._metrics.output_tokens / 1000) * llm_rates["output"]
            )

            # TTS cost (approximate characters)
            tts_provider = self.call_log.tts_provider
            tts_rate = self.COST_RATES["tts"].get(tts_provider, 0.00002)
            total_chars = sum(len(t.text) for t in self._transcripts if t.role == "assistant")
            self._cost.tts_cost = total_chars * tts_rate

            self._cost.total_cost = self._cost.stt_cost + self._cost.llm_cost + self._cost.tts_cost

    def _save_recording(self) -> Optional[str]:
        """Save combined audio to WAV file"""
        try:
            audio_data = self._combined_audio_buffer.getvalue()
            if not audio_data:
                return None

            # Generate filename
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"{self.call_id}_{timestamp}.wav"
            filepath = self.recordings_dir / filename

            # Write WAV file
            with wave.open(str(filepath), 'wb') as wav_file:
                wav_file.setnchannels(self.channels)
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(self.sample_rate)
                wav_file.writeframes(audio_data)

            logger.info(f"📁 Recording saved: {filepath}")
            return str(filepath)

        except Exception as e:
            logger.error(f"Failed to save recording: {e}")
            return None

    def finish(self, end_reason: str = "user_hangup") -> CallLog:
        """Finish recording and generate call log"""
        # Update timestamps
        self.call_log.ended_at = datetime.utcnow().isoformat()
        self.call_log.duration_sec = time.time() - self._start_time
        self.call_log.status = CallStatus.COMPLETED.value
        self.call_log.end_reason = end_reason

        # Calculate metrics
        if self._latencies:
            self._metrics.avg_response_latency_ms = sum(self._latencies) / len(self._latencies)
            self._metrics.total_latency_ms = sum(self._latencies)

        # Calculate cost
        self._calculate_cost()

        # Save recording
        recording_path = self._save_recording()
        if recording_path:
            self.call_log.recording_path = recording_path
            self.call_log.recording_url = f"/api/recordings/{self.call_id}"

        # Compile transcripts
        self.call_log.transcripts = [
            {
                "role": t.role,
                "text": t.text,
                "timestamp": t.timestamp,
                "is_final": t.is_final
            }
            for t in self._transcripts
        ]

        # Compile metrics
        self.call_log.metrics = {
            "total_latency_ms": self._metrics.total_latency_ms,
            "avg_response_latency_ms": self._metrics.avg_response_latency_ms,
            "stt_latency_ms": self._metrics.stt_latency_ms,
            "llm_latency_ms": self._metrics.llm_latency_ms,
            "tts_latency_ms": self._metrics.tts_latency_ms,
            "response_count": self._metrics.response_count,
            "input_tokens": self._metrics.input_tokens,
            "output_tokens": self._metrics.output_tokens,
            "user_audio_duration_sec": self._metrics.user_audio_duration_sec,
            "assistant_audio_duration_sec": self._metrics.assistant_audio_duration_sec,
        }

        # Compile cost
        self.call_log.cost = {
            "stt_cost": round(self._cost.stt_cost, 4),
            "llm_cost": round(self._cost.llm_cost, 4),
            "tts_cost": round(self._cost.tts_cost, 4),
            "total_cost": round(self._cost.total_cost, 4),
            "currency": self._cost.currency,
        }

        logger.info(f"📊 Call finished: {self.call_id} | Duration: {self.call_log.duration_sec:.1f}s | Cost: ${self._cost.total_cost:.4f}")

        return self.call_log

    def get_live_transcript(self) -> List[Dict[str, Any]]:
        """Get current transcripts for live display"""
        return [
            {
                "role": t.role,
                "text": t.text,
                "timestamp": t.timestamp,
            }
            for t in self._transcripts
        ]


class CallLogStorage:
    """
    Storage for call logs
    Uses JSON files for simplicity (can be replaced with database)
    """

    def __init__(self, storage_dir: str = "call_logs"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._index_file = self.storage_dir / "index.json"
        self._load_index()

    def _load_index(self):
        """Load call log index"""
        if self._index_file.exists():
            with open(self._index_file, 'r') as f:
                self._index = json.load(f)
        else:
            self._index = {"calls": [], "total_count": 0}

    def _save_index(self):
        """Save call log index"""
        with open(self._index_file, 'w') as f:
            json.dump(self._index, f, indent=2)

    def save(self, call_log: CallLog):
        """Save a call log"""
        # Save individual call file
        call_file = self.storage_dir / f"{call_log.call_id}.json"
        with open(call_file, 'w') as f:
            json.dump(call_log.to_dict(), f, indent=2)

        # Update index
        summary = {
            "call_id": call_log.call_id,
            "assistant_name": call_log.assistant_name,
            "started_at": call_log.started_at,
            "duration_sec": call_log.duration_sec,
            "status": call_log.status,
            "voice_mode": call_log.voice_mode,
            "total_cost": call_log.cost.get("total_cost", 0),
        }

        # Remove old entry if exists
        self._index["calls"] = [c for c in self._index["calls"] if c["call_id"] != call_log.call_id]

        # Add new entry at the beginning
        self._index["calls"].insert(0, summary)
        self._index["total_count"] = len(self._index["calls"])

        self._save_index()
        logger.info(f"💾 Call log saved: {call_log.call_id}")

    def get(self, call_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific call log"""
        call_file = self.storage_dir / f"{call_id}.json"
        if call_file.exists():
            with open(call_file, 'r') as f:
                return json.load(f)
        return None

    def list_calls(self, limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        """List call logs with pagination"""
        calls = self._index["calls"][offset:offset + limit]
        return {
            "calls": calls,
            "total_count": self._index["total_count"],
            "limit": limit,
            "offset": offset,
        }

    def delete(self, call_id: str) -> bool:
        """Delete a call log"""
        call_file = self.storage_dir / f"{call_id}.json"
        if call_file.exists():
            call_file.unlink()
            self._index["calls"] = [c for c in self._index["calls"] if c["call_id"] != call_id]
            self._index["total_count"] = len(self._index["calls"])
            self._save_index()
            return True
        return False


# Global storage instance
call_log_storage = CallLogStorage()
