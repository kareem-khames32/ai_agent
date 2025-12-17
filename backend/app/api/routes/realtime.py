"""
Real-time Voice WebSocket - Live streaming conversation
Ultra-low latency pipeline with streaming STT/LLM/TTS
Includes cost tracking for all API calls
"""
import asyncio
import base64
import json
import struct
import time
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
from loguru import logger
import httpx

from app.services.llm import LLMService, Message
from app.services.tts import TTSService
from app.services.stt_streaming import StreamingSTT, SentenceBuffer, TranscriptResult
from app.services.base_prompt import combine_prompts

# Try to import Azure Streaming STT
try:
    from app.services.azure_stt_streaming import AzureStreamingSTT, AzureTranscriptResult
    HAS_AZURE_STREAMING = True
except ImportError:
    HAS_AZURE_STREAMING = False


# Suppress GeneratorExit RuntimeError - it's a warning, not a real error
def _handle_exception(loop, context):
    exception = context.get("exception")
    if exception and isinstance(exception, RuntimeError):
        if "async generator ignored GeneratorExit" in str(exception):
            # This is expected when we cancel streaming - ignore it
            return
    # For other exceptions, use default handler
    loop.default_exception_handler(context)


# Set up the exception handler
try:
    loop = asyncio.get_event_loop()
    loop.set_exception_handler(_handle_exception)
except RuntimeError:
    pass  # No event loop yet, will be set up later


# Recording storage directory
RECORDINGS_DIR = Path("recordings")
RECORDINGS_DIR.mkdir(exist_ok=True)

router = APIRouter()


@router.get("/recordings/{recording_id}")
async def get_recording(recording_id: str):
    """
    Get combined recording (WAV file with both user and AI audio)
    """
    file_path = RECORDINGS_DIR / f"{recording_id}.wav"

    if not file_path.exists():
        return JSONResponse({"error": "Recording not found"}, status_code=404)

    return FileResponse(
        file_path,
        media_type="audio/wav",
        filename=f"{recording_id}.wav"
    )


@router.get("/recordings")
async def list_recordings():
    """List all recordings"""
    recordings = []
    for f in RECORDINGS_DIR.glob("*.wav"):
        recording_id = f.stem
        recordings.append({
            "id": recording_id,
            "size": f.stat().st_size,
            "created": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
        })
    return {"recordings": recordings}


@router.get("/recordings/{recording_id}/info")
async def get_recording_info(recording_id: str):
    """Get detailed info about a recording for debugging"""
    file_path = RECORDINGS_DIR / f"{recording_id}.wav"

    if not file_path.exists():
        return JSONResponse({"error": "Recording not found"}, status_code=404)

    # Read WAV header
    with open(file_path, "rb") as f:
        data = f.read(44)  # WAV header is 44 bytes

    if len(data) < 44:
        return {"error": "File too small for WAV"}

    # Parse WAV header
    riff = data[0:4].decode('ascii', errors='ignore')
    file_size = struct.unpack('<I', data[4:8])[0]
    wave = data[8:12].decode('ascii', errors='ignore')
    fmt = data[12:16].decode('ascii', errors='ignore')
    fmt_size = struct.unpack('<I', data[16:20])[0]
    audio_format = struct.unpack('<H', data[20:22])[0]
    channels = struct.unpack('<H', data[22:24])[0]
    sample_rate = struct.unpack('<I', data[24:28])[0]
    byte_rate = struct.unpack('<I', data[28:32])[0]
    block_align = struct.unpack('<H', data[32:34])[0]
    bits_per_sample = struct.unpack('<H', data[34:36])[0]
    data_marker = data[36:40].decode('ascii', errors='ignore')
    data_size = struct.unpack('<I', data[40:44])[0]

    duration = data_size / (sample_rate * channels * bits_per_sample / 8)

    return {
        "file_path": str(file_path),
        "file_size_bytes": file_path.stat().st_size,
        "header": {
            "riff": riff,
            "wave": wave,
            "fmt": fmt,
            "fmt_size": fmt_size,
            "audio_format": audio_format,
            "audio_format_name": "PCM" if audio_format == 1 else f"Unknown ({audio_format})",
            "channels": channels,
            "sample_rate": sample_rate,
            "byte_rate": byte_rate,
            "block_align": block_align,
            "bits_per_sample": bits_per_sample,
            "data_marker": data_marker,
            "data_size": data_size,
        },
        "duration_seconds": round(duration, 2),
        "expected_byte_rate": sample_rate * channels * bits_per_sample // 8,
        "valid": riff == "RIFF" and wave == "WAVE" and audio_format == 1,
    }


from pydantic import BaseModel

class PreviewVoiceRequest(BaseModel):
    text: str
    provider: str
    voice_id: str
    api_key: str
    region: str = ""


@router.post("/preview-voice")
async def preview_voice(request: PreviewVoiceRequest):
    """
    Generate a voice preview using the specified TTS provider
    Returns MP3 audio for playback
    """
    try:
        logger.info(f"🎤 Voice preview: provider={request.provider}, voice={request.voice_id}")

        tts = TTSService(
            provider=request.provider,
            api_key=request.api_key,
            voice_id=request.voice_id,
            region=request.region,
        )

        audio_mp3 = await tts.synthesize(request.text, output_format="mp3")

        from fastapi.responses import Response
        return Response(
            content=audio_mp3,
            media_type="audio/mpeg",
            headers={"Content-Disposition": "inline; filename=preview.mp3"}
        )

    except Exception as e:
        logger.error(f"Preview error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


# ============== Pricing (per unit) ==============
PRICING = {
    # STT Pricing (per minute)
    "stt": {
        "deepgram": 0.0043,  # Nova-2/Nova-3 (default)
        "deepgram_nova": 0.0043,  # Nova-2/Nova-3
        "deepgram_nova3": 0.0043,  # Nova-3 (Latest)
        "deepgram_whisper": 0.0048,  # Whisper
        "deepgram_flux": 0.0043,  # Flux (Voice Agents)
        "azure": 0.0167,  # Azure STT - Best quality for Arabic
        "openai_whisper": 0.006,  # OpenAI Whisper
        "openai": 0.006,  # OpenAI Whisper
        "groq": 0.0007,  # Groq Whisper - $0.04/hour = ~$0.0007/min - FASTEST & CHEAPEST!
        "munsit": 0.01,  # CNTXT Munsit - BEST Arabic STT (estimated pricing)
    },
    # LLM Pricing (per 1M tokens) - input/output
    "llm": {
        "anthropic": {
            # Current models
            "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0},
            "claude-3-5-sonnet-20241022": {"input": 3.0, "output": 15.0},
            "claude-3-5-haiku-20241022": {"input": 0.80, "output": 4.0},
            "claude-3-opus-20240229": {"input": 15.0, "output": 75.0},
            # 2025 models (estimated pricing based on tier)
            "claude-opus-4": {"input": 15.0, "output": 75.0},
            "claude-sonnet-4.5": {"input": 3.0, "output": 15.0},
            "claude-opus-4.5": {"input": 15.0, "output": 75.0},
            "claude-haiku-4.5": {"input": 0.80, "output": 4.0},
        },
        "openai": {
            # Current models
            "gpt-4o": {"input": 2.5, "output": 10.0},
            "gpt-4o-mini": {"input": 0.15, "output": 0.6},
            "gpt-4-turbo": {"input": 10.0, "output": 30.0},
            "gpt-4": {"input": 30.0, "output": 60.0},
            "gpt-3.5-turbo": {"input": 0.5, "output": 1.5},
            # 2025 models (estimated pricing based on tier)
            "gpt-4.1": {"input": 2.5, "output": 10.0},
            "gpt-4.1-mini": {"input": 0.15, "output": 0.6},
            "gpt-4.1-nano": {"input": 0.10, "output": 0.4},
            "o3": {"input": 10.0, "output": 40.0},  # Reasoning model
            "o4-mini": {"input": 3.0, "output": 12.0},  # Reasoning model
        },
        "google": {
            # Current models
            "gemini-2.0-flash": {"input": 0.075, "output": 0.30},
            "gemini-1.5-pro": {"input": 1.25, "output": 5.0},
            "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
            # 2025 models
            "gemini-2.5-pro": {"input": 1.25, "output": 5.0},
            "gemini-2.5-flash": {"input": 0.075, "output": 0.30},
            "gemini-2.0-pro": {"input": 1.25, "output": 5.0},
            "gemini-2.0-flash-lite": {"input": 0.04, "output": 0.15},
            "gemini-3-pro": {"input": 1.50, "output": 6.0},
        },
        "groq": {
            # Llama models
            "llama-3.3-70b-versatile": {"input": 0.59, "output": 0.79},
            "llama-3.2-90b-vision-preview": {"input": 0.90, "output": 0.90},
            "llama-3.2-11b-vision-preview": {"input": 0.18, "output": 0.18},
            "llama-3.1-70b-versatile": {"input": 0.59, "output": 0.79},
            "llama-3.1-8b-instant": {"input": 0.05, "output": 0.08},
            # Other models
            "mixtral-8x7b-32768": {"input": 0.24, "output": 0.24},
            "gemma2-9b-it": {"input": 0.20, "output": 0.20},
        },
        "together": {
            # Llama models
            "meta-llama/Llama-3.3-70B-Instruct-Turbo": {"input": 0.88, "output": 0.88},
            "meta-llama/Llama-3.2-11B-Vision-Instruct-Turbo": {"input": 0.18, "output": 0.18},
            # Qwen models
            "Qwen/Qwen2.5-72B-Instruct-Turbo": {"input": 1.20, "output": 1.20},
            "Qwen/Qwen3-235B-A22B": {"input": 2.00, "output": 2.00},
            # Mistral models
            "mistralai/Mixtral-8x7B-Instruct-v0.1": {"input": 0.60, "output": 0.60},
            "mistralai/Mistral-Small-24B": {"input": 0.80, "output": 0.80},
            # DeepSeek
            "deepseek-ai/DeepSeek-R1": {"input": 0.55, "output": 2.19},
        },
    },
    # TTS Pricing (per 1M characters)
    "tts": {
        "elevenlabs": 300.0,  # ~$0.30 per 1K chars
        "openai": 15.0,  # $15 per 1M chars
        "azure": 16.0,  # $16 per 1M chars
        "deepgram": 15.0,  # ~$0.015 per 1K chars - FASTEST
        "cartesia": 50.0,  # Cartesia Sonic - Ultra-low latency (estimated pricing)
    },
}


class CostTracker:
    """Track costs for a session"""

    def __init__(self):
        self.stt_minutes = 0.0
        self.stt_provider = ""
        self.stt_model = ""  # Track specific model for accurate pricing
        self.llm_input_tokens = 0
        self.llm_output_tokens = 0
        self.llm_provider = ""
        self.llm_model = ""
        self.tts_characters = 0
        self.tts_provider = ""

    def add_stt(self, audio_duration_seconds: float, provider: str, model: str = ""):
        """Add STT usage"""
        self.stt_minutes += audio_duration_seconds / 60.0
        self.stt_provider = provider
        if model:
            self.stt_model = model

    def add_llm(self, input_tokens: int, output_tokens: int, provider: str, model: str):
        """Add LLM usage"""
        self.llm_input_tokens += input_tokens
        self.llm_output_tokens += output_tokens
        self.llm_provider = provider
        self.llm_model = model

    def add_tts(self, characters: int, provider: str):
        """Add TTS usage"""
        self.tts_characters += characters
        self.tts_provider = provider

    def calculate_cost(self) -> dict:
        """Calculate total cost"""
        logger.info(f"💵 Calculating cost: STT={self.stt_minutes:.2f}min/{self.stt_provider}/{self.stt_model}, LLM={self.llm_input_tokens}+{self.llm_output_tokens} tokens/{self.llm_provider}/{self.llm_model}, TTS={self.tts_characters} chars/{self.tts_provider}")

        # STT cost - determine pricing key based on provider and model
        stt_key = self.stt_provider
        if self.stt_model:
            # Use model-specific pricing if available
            if "whisper" in self.stt_model.lower():
                stt_key = f"{self.stt_provider}_whisper"
            elif "nova-3" in self.stt_model.lower() or "nova3" in self.stt_model.lower():
                stt_key = f"{self.stt_provider}_nova3"
            elif "flux" in self.stt_model.lower():
                stt_key = f"{self.stt_provider}_flux"
        elif "whisper" in self.stt_provider.lower():
            stt_key = f"{self.stt_provider}"

        if stt_key not in PRICING["stt"]:
            stt_key = self.stt_provider  # fallback to provider
        if stt_key not in PRICING["stt"]:
            stt_key = "deepgram"  # ultimate fallback
        stt_cost = self.stt_minutes * PRICING["stt"].get(stt_key, 0.005)

        # LLM cost
        llm_cost = 0.0
        if self.llm_provider in PRICING["llm"] and self.llm_model in PRICING["llm"][self.llm_provider]:
            rates = PRICING["llm"][self.llm_provider][self.llm_model]
            llm_cost = (self.llm_input_tokens * rates["input"] + self.llm_output_tokens * rates["output"]) / 1_000_000
        elif self.llm_provider in PRICING["llm"]:
            # Use average pricing for unknown models in known provider
            provider_rates = list(PRICING["llm"][self.llm_provider].values())
            avg_input = sum(r["input"] for r in provider_rates) / len(provider_rates)
            avg_output = sum(r["output"] for r in provider_rates) / len(provider_rates)
            llm_cost = (self.llm_input_tokens * avg_input + self.llm_output_tokens * avg_output) / 1_000_000
            logger.warning(f"⚠️ Using average pricing for unknown model: {self.llm_provider}/{self.llm_model}")
        else:
            # Default fallback pricing
            llm_cost = (self.llm_input_tokens * 1.0 + self.llm_output_tokens * 3.0) / 1_000_000
            logger.warning(f"⚠️ LLM pricing not found for {self.llm_provider}/{self.llm_model}, using default")

        # TTS cost
        tts_cost = 0.0
        if self.tts_provider in PRICING["tts"]:
            tts_cost = self.tts_characters * PRICING["tts"][self.tts_provider] / 1_000_000
        else:
            logger.warning(f"⚠️ TTS pricing not found for {self.tts_provider}")

        total = stt_cost + llm_cost + tts_cost
        logger.info(f"💵 Cost breakdown: STT=${stt_cost:.6f}, LLM=${llm_cost:.6f}, TTS=${tts_cost:.6f}, Total=${total:.6f}")

        return {
            "stt": {
                "minutes": round(self.stt_minutes, 2),
                "provider": self.stt_provider,
                "cost": round(stt_cost, 6),
            },
            "llm": {
                "input_tokens": self.llm_input_tokens,
                "output_tokens": self.llm_output_tokens,
                "provider": self.llm_provider,
                "model": self.llm_model,
                "cost": round(llm_cost, 6),
            },
            "tts": {
                "characters": self.tts_characters,
                "provider": self.tts_provider,
                "cost": round(tts_cost, 6),
            },
            "total_cost": round(total, 6),
        }


class RealtimeVoiceSession:
    """
    Real-time voice conversation session with STREAMING STT

    Architecture (like Vapi/Retell):
    Audio → Deepgram WebSocket (real-time) → Transcript ready → LLM → TTS
                    ↓
         Transcribes WHILE user speaks!
    """

    def __init__(
        self,
        session_id: str,
        client_ws: WebSocket,
        # STT config
        stt_provider: str = "deepgram",
        stt_api_key: str = "",
        stt_region: Optional[str] = None,
        # LLM config
        llm_provider: str = "anthropic",
        llm_api_key: str = "",
        llm_model: Optional[str] = None,
        llm_temperature: float = 0.7,
        # TTS config
        tts_provider: str = "elevenlabs",
        tts_api_key: str = "",
        tts_region: Optional[str] = None,
        tts_voice_id: Optional[str] = None,
        tts_voice_speed: float = 1.0,
        tts_voice_stability: float = 0.5,
        # Other settings
        system_prompt: str = "",
        language: str = "ar",
        # Interruption settings
        interruption_enabled: bool = True,
        interruption_words_threshold: int = 0,  # 0 = immediate, 1-10 = wait for N words
        # Call behavior
        stop_on_hangup: bool = True,
    ):
        self.session_id = session_id
        self.client_ws = client_ws

        # STT config
        self.stt_provider = stt_provider
        self.stt_api_key = stt_api_key
        self.stt_region = stt_region

        # LLM config
        self.llm_provider = llm_provider
        self.llm_model = llm_model or self._get_default_model(llm_provider)
        self.llm = LLMService(provider=llm_provider, api_key=llm_api_key, model=self.llm_model)
        self.llm_temperature = llm_temperature

        # TTS config
        self.tts_provider = tts_provider
        self.tts_voice_speed = tts_voice_speed
        self.tts_voice_stability = tts_voice_stability
        self.tts = TTSService(
            provider=tts_provider,
            api_key=tts_api_key,
            region=tts_region,
            voice_id=tts_voice_id,
            voice_speed=tts_voice_speed,
            voice_stability=tts_voice_stability,
        )

        self.system_prompt = system_prompt
        self.language = language

        # Interruption settings
        self.interruption_enabled = interruption_enabled
        self.interruption_words_threshold = interruption_words_threshold
        self.interrupt_word_count = 0  # Track words during current speech
        self.stop_on_hangup = stop_on_hangup
        self.is_speaking = False  # Is AI currently speaking?
        self.should_stop_speaking = False  # Should we stop TTS?
        self.audio_only_stop = False  # True = stop TTS only, continue LLM (VAPI style)

        # 🎯 Backchannel detection - VAPI style
        # Backchannels = user acknowledging (ignore, don't interrupt)
        # Interruptions = user wants to stop AI (interrupt immediately)
        self.backchannel_phrases = {
            # Arabic acknowledgments
            "آه", "أه", "اه", "ايوه", "ايوا", "أيوه", "تمام", "طيب", "ماشي", "حاضر",
            "نعم", "اي", "صح", "بالظبط", "فاهم", "فاهمك", "اوك", "اوكي",
            # Greetings (shouldn't interrupt AI mid-response)
            "عليكم السلام", "وعليكم السلام", "السلام عليكم", "اهلا", "مرحبا",
            "ألو", "الو", "هلو", "alo", "hello", "hi",  # Phone greetings
            # Common responses
            "معاك", "معك", "معايا", "معي", "انا", "أنا", "ايه", "أيه",
            # English acknowledgments
            "ok", "okay", "yes", "yeah", "yep", "uh huh", "mm", "mmm", "hmm",
            "right", "sure", "got it", "i see", "alright",
        }
        self.interruption_phrases = {
            # Arabic explicit interruptions
            "لا", "لأ", "استنى", "وقف", "مش كده", "غلط", "لحظة", "بس", "خلاص",
            "اسكت", "سكوت", "توقف", "مش صح", "انتظر", "ثانية",
            # English explicit interruptions
            "no", "wait", "stop", "hold on", "that's wrong", "not right",
            "one second", "hang on", "pause",
        }
        self.first_audio_sent_this_turn = False  # Track if we sent first audio chunk

        self.messages: list[Message] = []
        self.audio_buffer: bytes = b""
        self.last_audio_time: float = 0
        self.is_processing = False
        self.silence_threshold = 0.5  # 🎯 500ms - balanced for natural speech pauses
        self.min_audio_length = 3200  # minimum bytes before processing
        self.process_task: Optional[asyncio.Task] = None

        # Cost tracking
        self.cost_tracker = CostTracker()

        # Audio recording
        self.recording_enabled = True
        self.recording_segments: list[tuple[str, bytes, float]] = []
        self.recording_id: Optional[str] = None
        self.recording_start_time: float = time.time()

        # 🚀 STREAMING STT - Real-time transcription
        self.streaming_stt: Optional[StreamingSTT] = None
        self.azure_streaming_stt: Optional[AzureStreamingSTT] = None if HAS_AZURE_STREAMING else None
        self.current_transcript = ""  # Accumulated transcript (all speech until processed)
        self._last_processed_transcript = ""  # Track last processed to prevent duplicates
        self.speech_start_time: float = 0  # When user started speaking
        self.last_speech_end_time: float = 0  # When last speech ended
        self.last_transcript_time: float = 0  # When last transcript was received (more reliable)
        self.user_is_speaking: bool = False  # Track if user is currently speaking
        self.utterance_complete: bool = False  # True when speech_final received (user stopped)

        # 🧠 Smart re-thinking - cancel and restart if user adds more before AI speaks
        self.is_thinking: bool = False  # AI is processing (LLM) but not speaking yet
        self.should_restart_thinking: bool = False  # Signal to restart with new input

        # 🎯 Track which audio was ACTUALLY played (not just sent)
        self.played_sequences: set[int] = set()  # Sequences confirmed played by frontend
        self.sequence_to_text: dict[int, str] = {}  # Map sequence number to text

        # 🎯 Track unspoken text when interrupted - to continue in next response
        self.unspoken_text: str = ""  # Text AI wanted to say but was interrupted

    async def init_streaming_stt(self):
        """Initialize streaming STT connection - supports Deepgram and Azure"""

        # 🎯 Deepgram Streaming STT
        if self.stt_provider == "deepgram" and self.stt_api_key:
            self.streaming_stt = StreamingSTT(
                api_key=self.stt_api_key,
                language=self.language,
                endpointing=200,  # 🎯 200ms - balanced for natural pauses
                utterance_end_ms=400,  # 🎯 400ms silence = utterance end
                interim_results=True,
                vad_events=True,
            )

            # Set callbacks
            self.streaming_stt.on_transcript = self._on_transcript
            self.streaming_stt.on_speech_started = self._on_speech_started
            self.streaming_stt.on_speech_ended = self._on_speech_ended

            # Connect
            connected = await self.streaming_stt.connect()
            if connected:
                logger.info("🎤 Deepgram Streaming STT initialized")
            return connected

        # 🎯 Azure Streaming STT
        elif self.stt_provider == "azure" and self.stt_api_key and HAS_AZURE_STREAMING:
            self.azure_streaming_stt = AzureStreamingSTT(
                api_key=self.stt_api_key,
                region=self.stt_region or "eastus",
                language=self.language if "-" in self.language else f"{self.language}-SA",
                sample_rate=16000,
            )

            # Set callbacks - wrap to convert AzureTranscriptResult to TranscriptResult
            async def on_azure_transcript(result: AzureTranscriptResult):
                # Convert to common format
                common_result = TranscriptResult(
                    text=result.text,
                    is_final=result.is_final,
                    confidence=result.confidence,
                    speech_final=result.is_final,  # Azure uses is_final for utterance end
                )
                await self._on_transcript(common_result)

            self.azure_streaming_stt.on_transcript = on_azure_transcript
            self.azure_streaming_stt.on_speech_started = self._on_speech_started
            self.azure_streaming_stt.on_speech_ended = self._on_speech_ended

            # Connect
            connected = await self.azure_streaming_stt.connect()
            if connected:
                logger.info("🎤 Azure Streaming STT initialized")
            return connected

        return False

    def _classify_speech(self, text: str) -> str:
        """
        🎯 VAPI-style backchannel detection
        Classify user speech as: 'backchannel', 'interruption', or 'normal'

        - backchannel: user acknowledging (آه، تمام) → IGNORE, don't interrupt AI
        - interruption: user wants to stop (لا، استنى) → INTERRUPT immediately
        - normal: regular speech → use word threshold

        🔧 Uses WORD-BASED matching to avoid false positives like "ألو" matching "لا"
        """
        if not text:
            return "normal"

        # Clean text for comparison
        clean = text.strip().lower()
        # Remove punctuation
        for char in '.؟?!،,':
            clean = clean.replace(char, '')
        clean = clean.strip()

        # Split into words for accurate matching (avoid "ألو" matching "لا")
        words = set(clean.split())

        # Check for backchannel FIRST (greetings, acknowledgments should NOT interrupt)
        for phrase in self.backchannel_phrases:
            phrase_words = set(phrase.split())
            # Check if ALL words in phrase exist in text
            if phrase_words.issubset(words):
                logger.info(f"💬 Classified as BACKCHANNEL: '{text}'")
                return "backchannel"

        # Check for explicit interruption (only as EXACT WORD match)
        # This prevents "ألو" from matching "لا"
        for phrase in self.interruption_phrases:
            phrase_words = set(phrase.split())
            # Check if ALL words in phrase exist as exact words in text
            if phrase_words.issubset(words):
                logger.info(f"🛑 Classified as INTERRUPTION: '{text}'")
                return "interruption"

        # Normal speech - no special classification
        return "normal"

    async def _on_transcript(self, result: TranscriptResult):
        """Handle transcript from streaming STT with BACKCHANNEL DETECTION"""
        try:
            # 🔍 Debug: Always log transcript info
            word_count = len(result.text.strip().split()) if result.text.strip() else 0
            logger.info(f"📝 Transcript: '{result.text[:50]}' | words={word_count} | final={result.is_final}")

            # 🎯 VAPI-style backchannel detection
            speech_type = self._classify_speech(result.text)

            # If AI is speaking or thinking, handle interruption
            if self.interruption_enabled and (self.is_speaking or self.is_thinking):
                if speech_type == "backchannel":
                    # 💬 BACKCHANNEL - Ignore completely, don't interrupt
                    logger.info(f"💬 Backchannel detected: '{result.text}' - IGNORING (AI continues)")
                    # Don't buffer this, don't interrupt - just ignore
                    return

                elif speech_type == "interruption":
                    # 🛑 EXPLICIT INTERRUPTION - Stop immediately
                    if not self.should_stop_speaking:
                        if self.is_speaking:
                            self.should_stop_speaking = True
                            self.audio_only_stop = True
                            logger.info(f"🛑 EXPLICIT INTERRUPTION: '{result.text}' - stopping AUDIO")
                            await self.client_ws.send_json({"type": "stop_audio"})
                        elif self.is_thinking:
                            self.should_stop_speaking = True
                            self.audio_only_stop = False
                            self.should_restart_thinking = True
                            logger.info(f"🛑 EXPLICIT INTERRUPTION: '{result.text}' - restarting THINKING")
                            await self.client_ws.send_json({"type": "interrupted"})

                else:
                    # 🎯 NORMAL SPEECH - Use word threshold
                    self.interrupt_word_count = max(self.interrupt_word_count, word_count)

                    # Only interrupt if we've reached word threshold AND first audio was sent
                    should_interrupt = (
                        self.interruption_words_threshold == 0 or  # Immediate mode
                        self.interrupt_word_count >= self.interruption_words_threshold
                    )

                    # 🎯 KEY FIX: Only interrupt if first audio was actually sent!
                    # This ensures user gets to hear at least some response
                    if should_interrupt and self.first_audio_sent_this_turn and not self.should_stop_speaking:
                        if self.is_speaking:
                            self.should_stop_speaking = True
                            self.audio_only_stop = True
                            logger.info(f"🛑 Word-threshold ({self.interrupt_word_count}) reached: stopping AUDIO")
                            await self.client_ws.send_json({"type": "stop_audio"})
                        elif self.is_thinking:
                            self.should_stop_speaking = True
                            self.audio_only_stop = False
                            self.should_restart_thinking = True
                            logger.info(f"🛑 Word-threshold ({self.interrupt_word_count}) reached: restarting THINKING")
                            await self.client_ws.send_json({"type": "interrupted"})

            # 🎯 Only skip backchannels when AI is ACTIVELY speaking/thinking
            # When AI is idle, ALL user input should be buffered (even greetings)
            ai_is_busy = self.is_speaking or self.is_thinking

            if speech_type == "backchannel" and ai_is_busy:
                # AI is busy and user said backchannel - ignore
                logger.info(f"💬 Backchannel not buffered (AI busy): '{result.text}'")
                return

            # 🎯 Buffer BOTH interim and final results
            # Azure Streaming often doesn't send final results, so we use interim too
            #
            # NOTE: We REPLACE (not append) because:
            # 1. Streaming STT sends FULL accumulated text in each interim
            # 2. After pause, STT may re-transcribe with corrections (مية → 100)
            # 3. Appending causes duplication like "خلاص بدفع مية خلاص بدفع 100"
            # The longer timeouts (800ms) will collect the full sentence naturally

            if result.is_final:
                self.current_transcript = result.text
                self.last_transcript_time = time.time()
                self.utterance_complete = True
                logger.info(f"📝 Final: {result.text}")
            else:
                # Interim result - always replace (STT sends full text each time)
                self.current_transcript = result.text
                self.last_transcript_time = time.time()
                logger.info(f"📝 Interim: {result.text[:50]}...")
        except Exception as e:
            logger.error(f"❌ Error in _on_transcript: {e}")

    async def _on_speech_started(self):
        """User started speaking - DON'T interrupt immediately, wait for transcript"""
        try:
            self.speech_start_time = time.time()
            self.user_is_speaking = True
            self.utterance_complete = False  # Reset - new speech starting
            self.interrupt_word_count = 0  # Reset word counter for new speech
            self.last_speech_end_time = 0  # 🎯 KEY: Reset so check_and_process waits for speech_ended
            await self.client_ws.send_json({"type": "speech_started"})

            # 🎯 VAPI-style: Don't interrupt immediately on speech start
            # Wait for transcript to determine if it's a backchannel or real interruption
            # The _on_transcript method will handle interruption based on:
            # - Backchannel (آه، تمام) → Ignore
            # - Explicit interruption (لا، استنى) → Stop immediately
            # - Normal speech → Use word threshold

            if self.is_speaking or self.is_thinking:
                logger.info(f"🎤 Speech started while AI busy - waiting for transcript to classify")
            else:
                logger.info(f"🎤 Speech started - AI not busy, will process as normal")
        except Exception as e:
            logger.error(f"❌ Error in _on_speech_started: {e}")

    async def _on_speech_ended(self):
        """User stopped speaking (utterance end)"""
        try:
            self.user_is_speaking = False
            self.last_speech_end_time = time.time()
            logger.info("🔇 Speech ended - waiting for more or processing after silence")
            # DON'T trigger processing here - let the timeout handler decide
            # This allows collecting multiple speech segments
            await self.client_ws.send_json({"type": "speech_ended"})
        except Exception as e:
            logger.error(f"❌ Error in _on_speech_ended: {e}")

    def _get_default_model(self, provider: str) -> str:
        """Get default model for provider"""
        defaults = {
            "anthropic": "claude-3-5-haiku-20241022",  # Fastest Claude
            "openai": "gpt-4o-mini",  # Fastest OpenAI
            "google": "gemini-2.0-flash",  # Fast Gemini
            "groq": "llama-3.3-70b-versatile",  # Ultra-fast Groq
            "together": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        }
        return defaults.get(provider, "llama-3.3-70b-versatile")

    def mark_sequence_played(self, sequence: int):
        """Mark an audio sequence as actually played by frontend"""
        self.played_sequences.add(sequence)

    def get_played_text(self) -> str:
        """Get the text that was actually played (based on confirmed sequences)"""
        if not self.played_sequences or not self.sequence_to_text:
            return ""

        # Get text for all played sequences in order
        played_texts = []
        for seq in sorted(self.played_sequences):
            if seq in self.sequence_to_text:
                played_texts.append(self.sequence_to_text[seq])

        return " ".join(played_texts).strip()

    def reset_sequence_tracking(self):
        """Reset sequence tracking for new response"""
        self.played_sequences.clear()
        self.sequence_to_text.clear()

    async def add_audio_chunk(self, audio_data: bytes):
        """Send audio chunk to streaming STT (real-time transcription)"""
        self.last_audio_time = time.time()

        # 🚀 Send to Deepgram streaming STT
        if self.streaming_stt and self.streaming_stt.is_connected:
            await self.streaming_stt.send_audio(audio_data)

        # 🚀 Send to Azure streaming STT
        if self.azure_streaming_stt and self.azure_streaming_stt.is_connected:
            await self.azure_streaming_stt.send_audio(audio_data)

        # Save for recording BEFORE adding to buffer
        if self.recording_enabled and len(audio_data) > 0:
            is_first_chunk = len(self.audio_buffer) == 0
            if is_first_chunk:
                # Start new user segment
                segment_time = time.time() - self.recording_start_time
                self.recording_segments.append(("user", audio_data, segment_time))
                logger.debug(f"📼 New user segment at {segment_time:.2f}s")
            else:
                # Append to last user segment
                if self.recording_segments and self.recording_segments[-1][0] == "user":
                    last = self.recording_segments[-1]
                    self.recording_segments[-1] = (last[0], last[1] + audio_data, last[2])

        # Buffer for processing
        self.audio_buffer += audio_data

    async def check_and_process(self):
        """
        Collect ALL user speech and process only after complete silence.
        This ensures the AI responds to the full message, not fragments.

        🚀 OPTIMIZED for low latency:
        - Fast polling (50ms)
        - Quick response after utterance end (200ms)
        - Balanced for speech combination
        """
        try:
            while True:
                # 🚀 Fast polling for responsive feel
                await asyncio.sleep(0.05)  # 50ms polling (was 200ms)

                # Check if there's buffered transcript to process
                transcript = self.current_transcript.strip()

                # Skip if nothing to process or AI is busy
                if not transcript:
                    # 🎯 ONLY use batch STT if streaming STT is NOT active
                    # This prevents double-processing (streaming + batch)
                    streaming_active = (
                        (self.streaming_stt and self.streaming_stt.is_connected) or
                        (self.azure_streaming_stt and self.azure_streaming_stt.is_connected)
                    )

                    if not streaming_active:
                        # Batch STT fallback - only when no streaming
                        if len(self.audio_buffer) > self.min_audio_length and not self.is_processing:
                            # 🎯 Make sure user is NOT speaking
                            if self.user_is_speaking:
                                continue
                            # Wait for proper silence
                            time_since_last_audio = time.time() - self.last_audio_time
                            time_since_speech_end = time.time() - self.last_speech_end_time if self.last_speech_end_time else 0
                            # 🎯 Need 0.5s of silence - balanced for natural speech
                            if time_since_last_audio > 0.5 and time_since_speech_end > 0.2:
                                logger.info(f"📤 Processing batch audio after {time_since_last_audio:.1f}s silence")
                                await self.process_audio()
                    continue

                # If user is still speaking (VAD), keep buffering
                if self.user_is_speaking:
                    continue

                # If AI is processing or speaking, handle accordingly
                if self.is_speaking or self.is_processing:
                    # AI is busy - but user has new input!
                    # Signal that we have more to say (will be combined)
                    if not self.should_restart_thinking:
                        logger.info(f"🔄 User added more while AI busy: '{transcript[:50]}...'")
                        self.should_restart_thinking = True
                    continue

                if self.is_thinking:
                    # User added more while AI thinking - signal restart
                    logger.info(f"🔄 User added more while AI thinking: '{transcript[:50]}...'")
                    self.should_restart_thinking = True
                    continue

                # 🎯 Wait for utterance to be complete (speech_final from Deepgram)
                time_since_last_audio = time.time() - self.last_audio_time
                time_since_last_transcript = time.time() - self.last_transcript_time
                time_since_speech_end = time.time() - self.last_speech_end_time if self.last_speech_end_time else 0

                # 🎯 KEY FIX: Must have speech_ended event AND enough silence
                # This prevents processing while user is still mid-sentence
                if self.last_speech_end_time == 0:
                    # No speech_ended event yet - keep waiting
                    continue

                if self.utterance_complete:
                    # 🎯 Utterance complete (speech_final from STT)
                    # Still wait for natural pause to catch continuation
                    if time_since_last_transcript < 0.5:  # 500ms buffer
                        continue
                    if time_since_speech_end < 0.6:  # 600ms after speech ended
                        continue
                else:
                    # 🎯 No speech_final yet - wait longer for natural pause
                    # Arabic speech has natural pauses of 500-800ms within sentences
                    if time_since_last_audio < 0.8:  # 800ms for audio silence
                        continue
                    if time_since_last_transcript < 0.7:  # 700ms for transcript
                        continue
                    if time_since_speech_end < 0.8:  # 800ms after VAD says speech ended
                        continue

                # User truly stopped - process the complete message!
                # 🎯 Prevent duplicate processing of same message
                if hasattr(self, '_last_processed_transcript') and self._last_processed_transcript == transcript:
                    logger.debug(f"⏭️ Skipping duplicate transcript: '{transcript[:30]}...'")
                    self.current_transcript = ""  # Clear buffer
                    continue

                self._last_processed_transcript = transcript  # Track what we processed
                self.current_transcript = ""  # Clear buffer
                self.utterance_complete = False  # Reset for next utterance
                logger.info(f"📝 Processing complete message: '{transcript}'")
                await self.process_transcript(transcript)
        except asyncio.CancelledError:
            logger.info("🛑 check_and_process task cancelled")
            raise
        except Exception as e:
            logger.error(f"❌ Fatal error in check_and_process: {e}")
            import traceback
            traceback.print_exc()

    async def process_transcript(self, transcript: str):
        """Process transcript from streaming STT - FAST PATH with smart re-thinking"""
        if self.is_processing:
            return

        # 🚫 REMOVED backchannel detection here - it was blocking valid responses!
        # Backchannels are ONLY ignored in _on_transcript when AI is ACTIVELY speaking
        # User responding "وعليكم السلام" to AI is a VALID response, not a backchannel

        self.is_processing = True
        self.is_thinking = True  # AI is now thinking (not speaking yet)
        self.should_restart_thinking = False  # Reset restart flag
        process_start = time.time()

        try:
            # 🔄 RESTART LOOP - if user adds more input while thinking, restart
            while True:
                # Check if we should restart with new input from current_transcript
                if self.should_restart_thinking:
                    logger.info("🔄 Restart requested - collecting new input...")

                    # Wait briefly for new transcript (keep it fast!)
                    for _ in range(3):  # Wait up to 0.3 seconds max
                        await asyncio.sleep(0.1)
                        if self.current_transcript.strip():
                            break
                        if not self.user_is_speaking:
                            break

                    new_input = self.current_transcript.strip()
                    if new_input:
                        self.current_transcript = ""
                        transcript = f"{transcript} {new_input}"
                        logger.info(f"🔄 Combined input: '{transcript[:60]}...'")
                    else:
                        logger.info(f"🔄 Restarting with: '{transcript[:60]}...'")

                    # 🎯 Remove BOTH the partial assistant response AND the old user message
                    # to start fresh with the combined transcript
                    while self.messages:
                        last_msg = self.messages[-1]
                        if last_msg.role == "assistant":
                            logger.info(f"🗑️ Removing partial assistant response: '{last_msg.content[:30]}...'")
                            self.messages.pop()
                        elif last_msg.role == "user":
                            logger.info(f"🗑️ Removing old user message: '{last_msg.content[:30]}...'")
                            self.messages.pop()
                            break  # Stop after removing the user message
                        else:
                            break

                    self.should_restart_thinking = False
                    self.is_thinking = True
                    self.should_stop_speaking = False
                    self._is_restart_iteration = True  # Flag to replace user message on frontend

                # Calculate STT latency
                stt_latency = int((time.time() - self.speech_start_time) * 1000) if self.speech_start_time else 0
                logger.info(f"🎯 Processing: '{transcript[:50]}...' ({stt_latency}ms)")

                await self.client_ws.send_json({"type": "processing"})

                # Send user transcript (with replace flag if this is a restart)
                await self.client_ws.send_json({
                    "type": "transcript",
                    "role": "user",
                    "text": transcript,
                    "replace": getattr(self, '_is_restart_iteration', False),  # Replace last user msg if restarting
                })
                self._is_restart_iteration = False  # Reset flag

                # Add to conversation - combine with last user message if exists
                if self.messages and self.messages[-1].role == "user":
                    # Combine with previous user message
                    combined = self.messages[-1].content + " " + transcript
                    self.messages[-1] = Message(role="user", content=combined)
                    logger.info(f"🔗 Combined user messages: '{combined[:60]}...'")
                else:
                    self.messages.append(Message(role="user", content=transcript))

                # Track STT cost with model for accurate pricing
                audio_duration = len(self.audio_buffer) / (16000 * 2) if self.audio_buffer else 1.0
                stt_model = self._get_stt_model()
                self.cost_tracker.add_stt(audio_duration, self.stt_provider, stt_model)
                self.audio_buffer = b""  # Clear

                # Generate response
                try:
                    await self._process_streaming_response()
                except Exception as e:
                    logger.error(f"Streaming failed: {e}")
                    await self._process_non_streaming_response()

                # If we didn't restart, we're done
                if not self.should_restart_thinking:
                    break
                # Otherwise continue loop for restart

        except Exception as e:
            logger.error(f"Error processing transcript: {e}")
            await self.client_ws.send_json({"type": "error", "message": str(e)})

        finally:
            self.is_processing = False
            self.is_thinking = False
            total_time = int((time.time() - process_start) * 1000)
            logger.info(f"⏱️ Turn complete: {total_time}ms")

    async def process_audio(self):
        """Process accumulated audio buffer (FALLBACK - batch STT) with restart support"""
        if self.is_processing or len(self.audio_buffer) < self.min_audio_length:
            return

        # 🎯 Don't process if user is still speaking!
        if self.user_is_speaking:
            logger.info("⏳ User still speaking, waiting...")
            return

        self.is_processing = True
        self.is_thinking = True
        self.should_restart_thinking = False

        # 🎯 Minimal wait - human-like fast response
        await asyncio.sleep(0.05)

        # 🎯 Check again if user started speaking during the wait
        if self.user_is_speaking:
            logger.info("⏳ User started speaking again, aborting process")
            self.is_processing = False
            self.is_thinking = False
            return

        # Now safe to take the buffer
        audio_to_process = self.audio_buffer
        self.audio_buffer = b""
        process_start = time.time()

        try:
            logger.info("🎤 process_audio: BATCH STT path")
            # Notify client we're processing
            await self.client_ws.send_json({"type": "processing"})

            # Note: User audio is already recorded in add_audio_chunk()
            # Don't record here to avoid duplication

            # Transcribe audio using Deepgram batch API (supports Arabic with whisper)
            transcript = await self.transcribe_audio(audio_to_process)

            if transcript and transcript.strip():
                # 🔄 RESTART LOOP - same as process_transcript
                while True:
                    # Check if we should restart with new input
                    if self.should_restart_thinking:
                        logger.info("🔄 Restart requested - collecting new input...")

                        # Wait briefly for new transcript
                        for _ in range(3):  # 0.3 seconds max
                            await asyncio.sleep(0.1)
                            if self.current_transcript.strip() or not self.user_is_speaking:
                                break

                        new_input = self.current_transcript.strip()
                        if new_input:
                            self.current_transcript = ""
                            transcript = f"{transcript} {new_input}"
                            logger.info(f"🔄 Combined: '{transcript[:60]}...'")
                            if self.messages and self.messages[-1].role == "user":
                                self.messages.pop()
                        else:
                            if self.messages and self.messages[-1].role == "user":
                                self.messages.pop()

                        self.should_restart_thinking = False
                        self.is_thinking = True
                        self.should_stop_speaking = False

                    logger.info(f"👤 User: {transcript[:50]}...")

                    await self.client_ws.send_json({
                        "type": "transcript",
                        "role": "user",
                        "text": transcript,
                    })

                    # Add to conversation - combine with last user message if exists
                    if self.messages and self.messages[-1].role == "user":
                        combined = self.messages[-1].content + " " + transcript
                        self.messages[-1] = Message(role="user", content=combined)
                        logger.info(f"🔗 Combined user messages: '{combined[:60]}...'")
                    else:
                        self.messages.append(Message(role="user", content=transcript))

                    try:
                        await self._process_streaming_response()
                    except Exception as stream_err:
                        logger.error(f"Streaming failed: {stream_err}")
                        await self._process_non_streaming_response()

                    if not self.should_restart_thinking:
                        break

            else:
                await self.client_ws.send_json({"type": "no_speech"})

        except Exception as e:
            logger.error(f"Error processing audio: {e}")
            await self.client_ws.send_json({
                "type": "error",
                "message": str(e),
            })

        finally:
            self.is_processing = False
            self.is_thinking = False
            total_time = int((time.time() - process_start) * 1000)
            logger.info(f"⏱️ Turn complete: {total_time}ms")

    async def _process_streaming_response(self):
        """
        🚀 ULTRA-LOW LATENCY PIPELINE v4 - FIXED SENTENCE SPLITTING

        Problem: Previous version sent incomplete sentences to TTS
        Fix: Only send COMPLETE sentences (up to last sentence ending)
        """
        logger.info("🚀 ULTRA-LOW LATENCY v4 - Fixed sentence splitting")
        await self.client_ws.send_json({"type": "thinking"})

        full_response = ""
        spoken_text = ""  # 🎯 Track ONLY what was actually sent as audio
        token_count = 0
        sentence_buffer = ""
        last_stream_time = 0  # For throttling text_stream

        # Sentence endings - Arabic and English
        SENTENCE_ENDINGS = ('.', '!', '?', '؟', '。', '،', ',')  # 🚀 Added comma for earlier splits
        MIN_CHARS = 8  # 🚀 Reduced for faster TTS start (was 10)
        MAX_WAIT_CHARS = 80  # 🚀 Force send sooner (was 150) - faster first audio

        # Don't set is_speaking yet - wait until TTS actually starts
        self.should_stop_speaking = False

        # 🎯 Reset sequence tracking and first audio flag for this new response
        self.reset_sequence_tracking()
        self.first_audio_sent_this_turn = False  # Reset for new turn

        # Sentence queue for ordered TTS
        sentence_queue: asyncio.Queue[str | None] = asyncio.Queue()
        tts_done = asyncio.Event()
        first_audio_sent = False
        spoken_sentences: list[str] = []  # Track sentences that were sent (backup)

        async def tts_worker():
            """Process TTS in order - ALWAYS send first audio before checking interruption"""
            nonlocal first_audio_sent, spoken_sentences
            seq = 0

            while True:  # Changed from 'not self.should_stop_speaking' to always process first chunk
                try:
                    text = await asyncio.wait_for(sentence_queue.get(), timeout=0.05)
                except asyncio.TimeoutError:
                    # Check if we should exit ONLY after first audio was sent
                    if self.should_stop_speaking and self.first_audio_sent_this_turn:
                        break
                    continue

                if text is None:
                    break

                seq += 1
                tts_start = time.time()

                try:
                    if not first_audio_sent:
                        # NOW we're actually speaking - set the flag
                        self.is_speaking = True
                        self.is_thinking = False  # Done thinking, now speaking
                        await self.client_ws.send_json({"type": "speaking"})
                        first_audio_sent = True

                    # Get MP3 for playback
                    audio_mp3 = await self.tts.synthesize(text.strip(), output_format="mp3")

                    tts_ms = int((time.time() - tts_start) * 1000)
                    logger.info(f"🔊 [{seq}] '{text[:30]}...' → {tts_ms}ms")

                    # 🎯 KEY FIX: ALWAYS send first audio chunk, even if interrupted
                    # This ensures user hears at least something before interruption takes effect
                    is_first_chunk = not self.first_audio_sent_this_turn

                    if is_first_chunk or not self.should_stop_speaking:
                        audio_b64 = base64.b64encode(audio_mp3).decode()
                        await self.client_ws.send_json({
                            "type": "audio",
                            "data": audio_b64,
                            "sequence": seq,
                        })
                        # 🎯 Map sequence to text for tracking what was ACTUALLY played
                        self.sequence_to_text[seq] = text.strip()
                        # Also track in backup list (for fallback)
                        spoken_sentences.append(text.strip())
                        logger.info(f"✅ Sentence sent seq={seq}: '{text[:30]}...'")

                        # 🎯 Mark first audio as sent AFTER successfully sending
                        if is_first_chunk:
                            self.first_audio_sent_this_turn = True
                            logger.info(f"🎯 First audio chunk sent - interruptions now allowed")
                    else:
                        logger.info(f"🛑 Skipping TTS chunk (interrupted): '{text[:30]}...'")
                        break  # Exit after skipping

                    # Record AI audio in BACKGROUND (doesn't block playback)
                    if self.recording_enabled and text.strip():
                        asyncio.create_task(self._record_ai_audio_chunk(text.strip()))

                except Exception as e:
                    logger.error(f"TTS error: {e}")

            tts_done.set()

        # Start TTS worker
        tts_task = asyncio.create_task(tts_worker())

        try:
            llm_start = time.time()
            first_token_time = None
            llm_stream = None  # Store generator reference for proper cleanup

            # 🚫 DISABLED: unspoken_text feature was causing AI to speak from middle of sentence
            # When user interrupts, AI would save unspoken text and speak it first next turn
            # This was confusing - better to just start fresh each turn
            # if self.unspoken_text:
            #     logger.info(f"📢 Speaking unspoken text first: '{self.unspoken_text[:50]}...'")
            #     await sentence_queue.put(self.unspoken_text)
            #     self.unspoken_text = ""
            self.unspoken_text = ""  # Clear any saved unspoken text - start fresh

            logger.info(f"📡 LLM: {self.llm_provider}/{self.llm_model}")

            # Create the stream generator and store reference
            llm_stream = self.llm.generate_stream(
                messages=self.messages,
                system_prompt=self.system_prompt,
                max_tokens=300,
                temperature=self.llm_temperature,
            )

            should_abort = False
            tts_stopped = False  # Track if TTS was stopped (audio_only_stop)
            last_text_update = ""  # Track what we sent to frontend

            async for token in llm_stream:
                # 🎯 VAPI-style interruption handling:
                # - audio_only_stop = True → stop TTS but CONTINUE LLM (user interrupted while speaking)
                # - audio_only_stop = False → full abort (user interrupted while thinking)

                if self.should_stop_speaking:
                    if self.audio_only_stop:
                        # AUDIO ONLY STOP - continue LLM, just stop sending to TTS
                        if not tts_stopped:
                            logger.info("🛑 Audio-only stop: continuing LLM, stopping TTS")
                            tts_stopped = True
                            await sentence_queue.put(None)  # Stop TTS worker
                        # Continue processing tokens below (don't skip!)
                    else:
                        # FULL ABORT - skip everything
                        if not should_abort:
                            logger.info("🛑 Full abort: skipping remaining tokens")
                            should_abort = True
                        continue  # Skip this token

                # 🔄 Check if user added more input while we're thinking
                if self.should_restart_thinking and not self.is_speaking:
                    if not should_abort:
                        logger.info("🔄 Restart thinking: skipping remaining tokens")
                        should_abort = True
                    continue  # Skip this token

                # If aborting, just consume without processing
                if should_abort:
                    continue

                token_count += 1
                if first_token_time is None:
                    first_token_time = time.time()
                    logger.info(f"⚡ First token: {int((first_token_time - llm_start) * 1000)}ms")

                full_response += token
                sentence_buffer += token

                # 📝 LIVE TEXT STREAMING - Throttled for performance (every 30ms)
                now = time.time()
                if token and (now - last_stream_time) >= 0.03:  # 30ms throttle
                    await self.client_ws.send_json({
                        "type": "text_stream",
                        "delta": full_response[len(last_text_update):],  # All new chars since last update
                        "text": full_response,
                        "final": False,
                    })
                    last_text_update = full_response
                    last_stream_time = now

                # Skip TTS if stopped (but we already built the response above)
                if tts_stopped:
                    continue

                # Only send COMPLETE sentences to TTS
                if len(sentence_buffer) >= MIN_CHARS:
                    # Find the last sentence ending
                    last_end_pos = -1
                    for ending in SENTENCE_ENDINGS:
                        pos = sentence_buffer.rfind(ending)
                        if pos > last_end_pos:
                            last_end_pos = pos

                    # If we found a sentence ending, send up to that point
                    if last_end_pos >= 0:
                        complete_sentence = sentence_buffer[:last_end_pos + 1].strip()
                        sentence_buffer = sentence_buffer[last_end_pos + 1:]

                        if complete_sentence:
                            await sentence_queue.put(complete_sentence)
                            logger.info(f"📤 Complete sentence: '{complete_sentence[:40]}...'")

                # Force send if buffer too long (but try to break at space)
                if len(sentence_buffer) >= MAX_WAIT_CHARS:
                    # Find last space to avoid cutting words
                    last_space = sentence_buffer.rfind(' ')
                    if last_space > MIN_CHARS:
                        to_send = sentence_buffer[:last_space].strip()
                        sentence_buffer = sentence_buffer[last_space:]
                    else:
                        to_send = sentence_buffer.strip()
                        sentence_buffer = ""

                    if to_send:
                        await sentence_queue.put(to_send)
                        logger.info(f"📤 Forced send: '{to_send[:40]}...'")

            # 🔄 If aborted (full stop), handle based on WHY we aborted
            if should_abort:
                # 🎯 Use played sequences if available, otherwise fall back to sent
                actually_played = self.get_played_text()
                spoken_text = actually_played if actually_played else " ".join(spoken_sentences).strip()

                # If we're restarting (user added more input), DON'T save partial response
                # The restart loop will handle everything fresh
                if self.should_restart_thinking:
                    logger.info(f"🔄 Aborting for restart - NOT saving partial response")
                    # Clear streaming text on frontend
                    await self.client_ws.send_json({
                        "type": "text_stream",
                        "text": "",
                        "final": True,
                        "interrupted": True,
                    })
                    # DON'T save to messages - restart loop will handle it
                else:
                    # Normal abort (interruption) - save what was spoken
                    await self.client_ws.send_json({
                        "type": "text_stream",
                        "text": full_response,
                        "final": True,
                        "interrupted": True,
                    })
                    if spoken_text:
                        await self.client_ws.send_json({
                            "type": "transcript",
                            "role": "assistant",
                            "text": spoken_text,
                            "partial": True,
                        })
                        self.messages.append(Message(role="assistant", content=spoken_text))

                await sentence_queue.put(None)
                tts_task.cancel()
                return

            # 🎯 If TTS was stopped (audio_only_stop), LLM completed but audio didn't
            if tts_stopped:
                # 🎯 Use played sequences if available, otherwise fall back to sent
                actually_played = self.get_played_text()
                spoken_text = actually_played if actually_played else " ".join(spoken_sentences).strip()

                # Send final text stream
                await self.client_ws.send_json({
                    "type": "text_stream",
                    "text": full_response,
                    "final": True,
                    "interrupted": True,
                })

                # Save to history
                if spoken_text:
                    await self.client_ws.send_json({
                        "type": "transcript",
                        "role": "assistant",
                        "text": spoken_text,
                        "partial": True,
                    })
                    self.messages.append(Message(role="assistant", content=spoken_text))

                    # 🚫 DISABLED: Don't save unspoken text - start fresh each turn
                    # This was causing AI to speak from middle of sentence
                    self.unspoken_text = ""

                    # Track costs
                    input_tokens = len(self.system_prompt) // 4 + sum(len(m.content) for m in self.messages) // 4
                    output_tokens = len(spoken_text) // 4
                    self.cost_tracker.add_llm(input_tokens, output_tokens, self.llm_provider, self.llm_model)
                    self.cost_tracker.add_tts(len(spoken_text), self.tts_provider)

                tts_task.cancel()
                return

            # Send remaining text (normal flow - no interruption)
            if sentence_buffer.strip():
                await sentence_queue.put(sentence_buffer.strip())
                logger.info(f"📤 Final: '{sentence_buffer[:40]}...'")

            # Signal done
            await sentence_queue.put(None)
            await asyncio.wait_for(tts_done.wait(), timeout=30.0)

            total_ms = int((time.time() - llm_start) * 1000)
            logger.info(f"✅ Total: {total_ms}ms, {token_count} tokens")

            # Send final text stream (complete)
            await self.client_ws.send_json({
                "type": "text_stream",
                "text": full_response,
                "final": True,
                "interrupted": False,
            })

            # 🎯 Determine what to save: spoken_text (if interrupted) or full_response
            spoken_text = " ".join(spoken_sentences).strip()
            was_interrupted = self.should_stop_speaking or len(spoken_sentences) < len(full_response.split('.'))

            # Use spoken_text if we were interrupted, otherwise use full response
            text_to_save = spoken_text if (was_interrupted and spoken_text) else full_response.strip()

            if was_interrupted and spoken_text:
                logger.info(f"🛑 Interrupted! Saving only spoken: '{spoken_text[:50]}...' (vs full: '{full_response[:50]}...')")
            else:
                logger.info(f"✅ Complete response: '{text_to_save[:50]}...'")
            # 🚫 DISABLED: Don't save unspoken text - start fresh each turn
            self.unspoken_text = ""

            # Send transcript (for history display)
            if text_to_save:
                await self.client_ws.send_json({
                    "type": "transcript",
                    "role": "assistant",
                    "text": text_to_save,
                })

                # Track costs BEFORE adding to messages (to avoid counting output as input)
                # Input = system prompt + all messages so far (not including this response)
                input_tokens = len(self.system_prompt) // 4 + sum(len(m.content) for m in self.messages) // 4
                output_tokens = len(text_to_save) // 4
                self.cost_tracker.add_llm(input_tokens, output_tokens, self.llm_provider, self.llm_model)
                self.cost_tracker.add_tts(len(text_to_save), self.tts_provider)

                # NOW add to conversation history
                self.messages.append(Message(role="assistant", content=text_to_save))

        except Exception as e:
            logger.error(f"Pipeline error: {e}")
            import traceback
            traceback.print_exc()

            # Send user-friendly error message
            error_msg = str(e).lower()
            if "credit balance" in error_msg or "insufficient" in error_msg:
                await self.client_ws.send_json({
                    "type": "error",
                    "message": f"⚠️ رصيد API غير كافي ({self.llm_provider}). الرجاء شحن الحساب أو استخدام provider آخر.",
                })
            elif "401" in error_msg or "unauthorized" in error_msg or "invalid api key" in error_msg:
                await self.client_ws.send_json({
                    "type": "error",
                    "message": f"⚠️ مفتاح API غير صحيح ({self.llm_provider}). الرجاء التحقق من الإعدادات.",
                })
            elif "rate limit" in error_msg or "429" in error_msg:
                await self.client_ws.send_json({
                    "type": "error",
                    "message": f"⚠️ تجاوزت حد الطلبات ({self.llm_provider}). انتظر قليلاً وحاول مرة أخرى.",
                })
            else:
                await self.client_ws.send_json({
                    "type": "error",
                    "message": f"❌ خطأ: {str(e)[:100]}",
                })
            raise
        finally:
            self.is_speaking = False
            self.is_thinking = False
            self.should_stop_speaking = False
            self.audio_only_stop = False  # Reset audio_only_stop flag
            self.last_ai_speech_time = time.time()
            tts_task.cancel()

    async def _record_ai_audio_chunk(self, text: str):
        """Get PCM for recording in background - doesn't block main response"""
        try:
            # Use a shorter timeout for recording TTS - don't let it hang
            audio_pcm = await asyncio.wait_for(
                self.tts.synthesize(text, output_format="pcm"),
                timeout=10.0  # 10 second timeout for recording
            )
            segment_time = time.time() - self.recording_start_time
            self.recording_segments.append(("ai", audio_pcm, segment_time))
            logger.debug(f"📼 AI recorded: {len(audio_pcm)} bytes at {segment_time:.2f}s")
        except asyncio.TimeoutError:
            logger.warning(f"⏰ Recording TTS timeout for: {text[:30]}...")
        except Exception as e:
            # Don't let recording errors affect the call
            logger.warning(f"📼 Recording skipped: {e}")

    async def _send_tts_chunk(self, text: str, sequence: int, is_first: bool = False, llm_start: float = 0):
        """Send a TTS chunk with sequence number for frontend queuing"""
        if not text.strip() or self.should_stop_speaking:
            return

        try:
            tts_start = time.time()

            if is_first:
                await self.client_ws.send_json({"type": "speaking"})

            audio_mp3 = await self.tts.synthesize(text, output_format="mp3")

            tts_latency = int((time.time() - tts_start) * 1000)
            total_latency = int((time.time() - llm_start) * 1000) if llm_start else 0

            logger.info(f"🔊 TTS chunk {sequence}: '{text[:30]}...' → {tts_latency}ms (total: {total_latency}ms)")

            # Record PCM
            if self.recording_enabled:
                try:
                    audio_pcm = await self.tts.synthesize(text, output_format="pcm")
                    segment_time = time.time() - self.recording_start_time
                    self.recording_segments.append(("ai", audio_pcm, segment_time))
                except:
                    pass

            if not self.should_stop_speaking:
                audio_b64 = base64.b64encode(audio_mp3).decode()
                await self.client_ws.send_json({
                    "type": "audio",
                    "data": audio_b64,
                    "sequence": sequence,  # For frontend queuing
                    "is_last": False,
                })

        except Exception as e:
            logger.error(f"TTS chunk error: {e}")

    async def _stream_tts_sentence(self, text: str, is_first: bool = False):
        """Generate and send TTS for a single sentence"""
        if not text.strip() or self.should_stop_speaking:
            return

        try:
            tts_start = time.time()

            # Notify speaking start on first sentence
            if is_first:
                await self.client_ws.send_json({"type": "speaking"})

            # Generate MP3 for playback
            audio_mp3 = await self.tts.synthesize(text, output_format="mp3")

            tts_latency = int((time.time() - tts_start) * 1000)
            logger.info(f"⚡ TTS sentence ({len(text)} chars): {tts_latency}ms")

            # Get PCM for recording
            if self.recording_enabled:
                try:
                    audio_pcm = await self.tts.synthesize(text, output_format="pcm")
                    segment_time = time.time() - self.recording_start_time
                    self.recording_segments.append(("ai", audio_pcm, segment_time))
                except Exception as e:
                    logger.warning(f"Failed to get PCM for recording: {e}")

            # Send audio if not interrupted
            if not self.should_stop_speaking:
                audio_b64 = base64.b64encode(audio_mp3).decode()
                await self.client_ws.send_json({
                    "type": "audio",
                    "data": audio_b64,
                })
            else:
                logger.info("🔇 TTS cancelled due to interruption")

        except Exception as e:
            logger.error(f"TTS sentence error: {e}")

    async def _process_non_streaming_response(self):
        """Fallback non-streaming response (more reliable but slower)"""
        await self.client_ws.send_json({"type": "thinking"})

        try:
            # Generate full response at once
            response = await self.llm.generate(
                messages=self.messages,
                system_prompt=self.system_prompt,
                max_tokens=200,
                temperature=self.llm_temperature,
            )

            assistant_text = response.text.strip()
            logger.info(f"Assistant (non-streaming): {assistant_text}")

            if not assistant_text:
                logger.warning("Empty response from LLM")
                return

            # Track LLM cost
            input_tokens = sum(len(m.content) for m in self.messages) // 4 + len(self.system_prompt) // 4
            output_tokens = len(assistant_text) // 4
            self.cost_tracker.add_llm(input_tokens, output_tokens, self.llm_provider, self.llm_model)

            # Send transcript
            await self.client_ws.send_json({
                "type": "transcript",
                "role": "assistant",
                "text": assistant_text,
            })

            self.messages.append(Message(role="assistant", content=assistant_text))

            # 🔄 Check if we should restart before speaking
            if self.should_restart_thinking:
                logger.info("🔄 User added input - restart before speaking")
                # Remove the response we just added
                self.messages.pop()
                return

            # Generate TTS
            self.is_speaking = True
            self.is_thinking = False  # Done thinking, now speaking
            self.should_stop_speaking = False
            await self.client_ws.send_json({"type": "speaking"})

            if not self.should_stop_speaking:
                audio_mp3 = await self.tts.synthesize(assistant_text, output_format="mp3")

                # Record
                if self.recording_enabled:
                    try:
                        audio_pcm = await self.tts.synthesize(assistant_text, output_format="pcm")
                        segment_time = time.time() - self.recording_start_time
                        self.recording_segments.append(("ai", audio_pcm, segment_time))
                    except Exception as e:
                        logger.warning(f"Failed to get PCM: {e}")

                self.cost_tracker.add_tts(len(assistant_text), self.tts_provider)

                if not self.should_stop_speaking:
                    audio_b64 = base64.b64encode(audio_mp3).decode()
                    await self.client_ws.send_json({
                        "type": "audio",
                        "data": audio_b64,
                    })

            self.is_speaking = False
            self.last_ai_speech_time = time.time()  # Track when AI finished speaking

        except Exception as e:
            logger.error(f"Non-streaming response error: {e}")
            import traceback
            traceback.print_exc()

            # Send user-friendly error message
            error_msg = str(e).lower()
            if "credit balance" in error_msg or "insufficient" in error_msg:
                await self.client_ws.send_json({
                    "type": "error",
                    "message": f"⚠️ رصيد API غير كافي ({self.llm_provider}). الرجاء شحن الحساب أو استخدام provider آخر.",
                })
            elif "401" in error_msg or "unauthorized" in error_msg or "invalid api key" in error_msg:
                await self.client_ws.send_json({
                    "type": "error",
                    "message": f"⚠️ مفتاح API غير صحيح ({self.llm_provider}). الرجاء التحقق من الإعدادات.",
                })
            elif "rate limit" in error_msg or "429" in error_msg:
                await self.client_ws.send_json({
                    "type": "error",
                    "message": f"⚠️ تجاوزت حد الطلبات ({self.llm_provider}). انتظر قليلاً وحاول مرة أخرى.",
                })
            else:
                await self.client_ws.send_json({
                    "type": "error",
                    "message": f"❌ خطأ: {str(e)[:100]}",
                })

    def _get_stt_model(self) -> str:
        """Get the actual STT model being used based on provider and language"""
        is_arabic = self.language.lower().startswith("ar")

        if self.stt_provider == "deepgram":
            return "whisper-large" if is_arabic else "nova-2"
        elif self.stt_provider == "groq":
            return "whisper-large-v3-turbo"
        elif self.stt_provider == "openai":
            return "whisper-1"
        elif self.stt_provider == "azure":
            return "default"
        elif self.stt_provider == "munsit":
            return "munsit-1"
        return "unknown"

    async def transcribe_audio(self, audio_data: bytes) -> str:
        """Transcribe audio using configured STT provider"""
        # Calculate audio duration (16-bit PCM at 16kHz)
        audio_duration = len(audio_data) / (16000 * 2)  # bytes / (sample_rate * bytes_per_sample)

        try:
            if self.stt_provider == "deepgram":
                transcript = await self._transcribe_deepgram(audio_data)
            elif self.stt_provider == "azure":
                transcript = await self._transcribe_azure(audio_data)
            elif self.stt_provider == "openai":
                transcript = await self._transcribe_openai(audio_data)
            elif self.stt_provider == "groq":
                transcript = await self._transcribe_groq(audio_data)
            elif self.stt_provider == "munsit":
                transcript = await self._transcribe_munsit(audio_data)
            else:
                # Default to Deepgram
                transcript = await self._transcribe_deepgram(audio_data)

            # Track STT cost with model for accurate pricing
            stt_model = self._get_stt_model()
            self.cost_tracker.add_stt(audio_duration, self.stt_provider, stt_model)

            return transcript

        except Exception as e:
            logger.error(f"Transcription error: {e}")
            import traceback
            traceback.print_exc()
            return ""

    async def _transcribe_deepgram(self, audio_data: bytes) -> str:
        """Transcribe using Deepgram"""
        url = "https://api.deepgram.com/v1/listen"

        # Nova-2 doesn't support Arabic, so use Whisper for Arabic languages
        # Nova-2 is much faster for supported languages (en, es, fr, de, etc.)
        is_arabic = self.language.lower().startswith("ar")

        if is_arabic:
            # Use Whisper for Arabic - slower but accurate
            params = {
                "model": "whisper-large",
                "language": self.language,
                "punctuate": "true",
                "encoding": "linear16",
                "sample_rate": "16000",
                "channels": "1",
            }
            logger.debug(f"Using Whisper model for Arabic language: {self.language}")
        else:
            # Use Nova-2 for other languages - much faster
            params = {
                "model": "nova-2",
                "language": self.language,
                "punctuate": "true",
                "encoding": "linear16",
                "sample_rate": "16000",
                "channels": "1",
                "smart_format": "true",
            }
            logger.debug(f"Using Nova-2 model for language: {self.language}")

        headers = {
            "Authorization": f"Token {self.stt_api_key}",
            "Content-Type": "audio/raw",
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                params=params,
                headers=headers,
                content=audio_data,
                timeout=30.0,
            )

            if response.status_code != 200:
                logger.error(f"Deepgram error: {response.status_code} - {response.text}")
                return ""

            result = response.json()

        alternatives = result.get("results", {}).get("channels", [{}])[0].get("alternatives", [{}])
        if alternatives:
            return alternatives[0].get("transcript", "")
        return ""

    async def _transcribe_azure(self, audio_data: bytes) -> str:
        """Transcribe using Azure Speech - Best quality for Arabic"""
        # Validate and clean region
        region = self.stt_region.strip() if self.stt_region else "eastus"
        if not region or region == "undefined" or region == "null":
            region = "eastus"

        # Valid Azure regions (common ones)
        valid_regions = ["eastus", "eastus2", "westus", "westus2", "westus3",
                        "centralus", "northcentralus", "southcentralus",
                        "westeurope", "northeurope", "southeastasia", "eastasia",
                        "australiaeast", "brazilsouth", "canadacentral",
                        "japaneast", "japanwest", "koreacentral", "uksouth",
                        "francecentral", "germanywestcentral", "switzerlandnorth",
                        "uaenorth", "southafricanorth", "qatarcentral"]

        if region.lower() not in valid_regions:
            logger.warning(f"Unknown Azure region '{region}', using 'eastus'")
            region = "eastus"

        url = f"https://{region}.stt.speech.microsoft.com/speech/recognition/conversation/cognitiveservices/v1"
        logger.debug(f"Azure STT URL: {url}")

        # Comprehensive language mapping for Azure Speech
        lang_map = {
            # Arabic dialects
            "ar": "ar-EG",  # Egyptian Arabic (default)
            "ar-eg": "ar-EG",  # Egyptian Arabic
            "ar-sa": "ar-SA",  # Saudi Arabic
            "ar-ae": "ar-AE",  # UAE Arabic
            "ar-bh": "ar-BH",  # Bahraini Arabic
            "ar-dz": "ar-DZ",  # Algerian Arabic
            "ar-iq": "ar-IQ",  # Iraqi Arabic
            "ar-jo": "ar-JO",  # Jordanian Arabic
            "ar-kw": "ar-KW",  # Kuwaiti Arabic
            "ar-lb": "ar-LB",  # Lebanese Arabic
            "ar-ly": "ar-LY",  # Libyan Arabic
            "ar-ma": "ar-MA",  # Moroccan Arabic
            "ar-om": "ar-OM",  # Omani Arabic
            "ar-ps": "ar-PS",  # Palestinian Arabic
            "ar-qa": "ar-QA",  # Qatari Arabic
            "ar-sy": "ar-SY",  # Syrian Arabic
            "ar-tn": "ar-TN",  # Tunisian Arabic
            "ar-ye": "ar-YE",  # Yemeni Arabic
            # English
            "en": "en-US",
            "en-us": "en-US",
            "en-gb": "en-GB",
            "en-au": "en-AU",
            "en-ca": "en-CA",
            "en-in": "en-IN",
            "en-ie": "en-IE",
            "en-nz": "en-NZ",
            "en-sg": "en-SG",
            "en-za": "en-ZA",
            # French
            "fr": "fr-FR",
            "fr-fr": "fr-FR",
            "fr-ca": "fr-CA",
            "fr-be": "fr-BE",
            "fr-ch": "fr-CH",
            # German
            "de": "de-DE",
            "de-de": "de-DE",
            "de-at": "de-AT",
            "de-ch": "de-CH",
            # Spanish
            "es": "es-ES",
            "es-es": "es-ES",
            "es-mx": "es-MX",
            "es-ar": "es-AR",
            "es-co": "es-CO",
            # Italian
            "it": "it-IT",
            # Portuguese
            "pt": "pt-BR",
            "pt-br": "pt-BR",
            "pt-pt": "pt-PT",
            # Russian
            "ru": "ru-RU",
            # Chinese
            "zh": "zh-CN",
            "zh-cn": "zh-CN",
            "zh-tw": "zh-TW",
            "zh-hk": "zh-HK",
            # Japanese
            "ja": "ja-JP",
            # Korean
            "ko": "ko-KR",
            # Turkish
            "tr": "tr-TR",
            # Hindi
            "hi": "hi-IN",
            # Dutch
            "nl": "nl-NL",
            # Polish
            "pl": "pl-PL",
            # Indonesian
            "id": "id-ID",
            # Thai
            "th": "th-TH",
            # Vietnamese
            "vi": "vi-VN",
            # Hebrew
            "he": "he-IL",
            # Persian/Farsi
            "fa": "fa-IR",
            # Urdu
            "ur": "ur-PK",
        }
        azure_lang = lang_map.get(self.language.lower(), "ar-EG")
        logger.debug(f"Azure STT using language: {azure_lang}")

        params = {"language": azure_lang}

        headers = {
            "Ocp-Apim-Subscription-Key": self.stt_api_key,
            "Content-Type": "audio/raw; rate=16000; format=1channel-16bit-integer",
            "Accept": "application/json",
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                params=params,
                headers=headers,
                content=audio_data,
                timeout=30.0,
            )

            if response.status_code != 200:
                logger.error(f"Azure STT error: {response.status_code} - {response.text}")
                return ""

            result = response.json()

        return result.get("DisplayText", "")

    async def _transcribe_openai(self, audio_data: bytes) -> str:
        """Transcribe using OpenAI Whisper"""
        import io

        url = "https://api.openai.com/v1/audio/transcriptions"

        # Convert raw PCM to WAV format
        wav_data = self._pcm_to_wav(audio_data)

        headers = {
            "Authorization": f"Bearer {self.stt_api_key}",
        }

        files = {
            "file": ("audio.wav", io.BytesIO(wav_data), "audio/wav"),
        }
        data = {
            "model": "whisper-1",
            "language": self.language[:2],  # Whisper uses 2-letter codes
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers=headers,
                files=files,
                data=data,
                timeout=30.0,
            )

            if response.status_code != 200:
                logger.error(f"OpenAI Whisper error: {response.status_code} - {response.text}")
                return ""

            result = response.json()

        return result.get("text", "")

    async def _transcribe_groq(self, audio_data: bytes) -> str:
        """Transcribe using Groq Whisper - FASTEST option!
        Uses whisper-large-v3-turbo which is optimized for speed.
        Supports Arabic and many other languages.
        """
        import io

        url = "https://api.groq.com/openai/v1/audio/transcriptions"

        # Convert raw PCM to WAV format
        wav_data = self._pcm_to_wav(audio_data)

        headers = {
            "Authorization": f"Bearer {self.stt_api_key}",
        }

        files = {
            "file": ("audio.wav", io.BytesIO(wav_data), "audio/wav"),
        }
        data = {
            "model": "whisper-large-v3-turbo",  # Fastest Whisper model
            "language": self.language[:2],  # Use 2-letter codes
            "response_format": "json",
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers=headers,
                files=files,
                data=data,
                timeout=30.0,
            )

            if response.status_code != 200:
                logger.error(f"Groq Whisper error: {response.status_code} - {response.text}")
                return ""

            result = response.json()

        logger.debug(f"Groq transcription result: {result}")
        return result.get("text", "")

    async def _transcribe_munsit(self, audio_data: bytes) -> str:
        """
        Transcribe using Munsit (CNTXT) - BEST Arabic STT!

        Munsit is the world's most accurate Arabic speech recognition model.
        Supports Modern Standard Arabic and 25+ Arabic dialects.
        WER of 26.68% - outperforms OpenAI Whisper, Azure, and ElevenLabs.
        """
        import io

        url = "https://api.cntxt.tools/audio/transcribe"

        # Convert raw PCM to WAV format (Munsit accepts common audio formats)
        wav_data = self._pcm_to_wav(audio_data)

        headers = {
            "Authorization": f"Bearer {self.stt_api_key}",
            "accept": "*/*",
        }

        # Use multipart/form-data for file upload
        files = {
            "file": ("audio.wav", io.BytesIO(wav_data), "audio/wav"),
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers=headers,
                files=files,
                timeout=30.0,
            )

            if response.status_code not in [200, 201]:
                logger.error(f"Munsit error: {response.status_code} - {response.text}")
                return ""

            result = response.json()

        # Extract transcript from response
        # Munsit returns {"statusCode":201,"data":{"transcription":"..."},"message":"Success"}
        data = result.get("data", {})
        transcript = data.get("transcription", "") or result.get("text", "") or result.get("transcript", "")
        logger.info(f"🎤 Munsit transcription: '{transcript}'")
        return transcript

    def _pcm_to_wav(self, pcm_data: bytes) -> bytes:
        """Convert raw PCM to WAV format"""
        import struct

        sample_rate = 16000
        channels = 1
        bits_per_sample = 16
        byte_rate = sample_rate * channels * bits_per_sample // 8
        block_align = channels * bits_per_sample // 8
        data_size = len(pcm_data)

        # WAV header
        header = b"RIFF"
        header += struct.pack("<I", 36 + data_size)  # File size - 8
        header += b"WAVE"
        header += b"fmt "
        header += struct.pack("<I", 16)  # Subchunk1 size
        header += struct.pack("<H", 1)  # Audio format (PCM)
        header += struct.pack("<H", channels)
        header += struct.pack("<I", sample_rate)
        header += struct.pack("<I", byte_rate)
        header += struct.pack("<H", block_align)
        header += struct.pack("<H", bits_per_sample)
        header += b"data"
        header += struct.pack("<I", data_size)

        return header + pcm_data

    def get_cost_summary(self) -> dict:
        """Get cost summary for this session including waveform data"""
        cost_data = self.cost_tracker.calculate_cost()
        # Add waveform data and duration
        waveform = self.generate_waveform_data()
        duration = self.get_call_duration()
        cost_data["waveform"] = waveform
        cost_data["call_duration"] = round(duration, 2)
        logger.info(f"📊 Cost summary: waveform_points={len(waveform)}, duration={duration:.2f}s, segments={len(self.recording_segments)}")
        return cost_data

    def save_recording(self) -> Optional[str]:
        """Save the call recording with proper timing (including silences between segments)"""
        logger.info(f"📼 save_recording called: enabled={self.recording_enabled}, segments={len(self.recording_segments)}")

        if not self.recording_enabled:
            logger.info("Recording disabled, skipping save")
            return None

        if not self.recording_segments:
            logger.info("No audio segments to save")
            return None

        try:
            # Generate recording ID
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.recording_id = f"{self.session_id}_{timestamp}"

            # Audio parameters
            sample_rate = 16000
            bytes_per_sample = 2  # 16-bit

            # Sort segments by timestamp
            sorted_segments = sorted(self.recording_segments, key=lambda x: x[2])

            # Build timeline with silence gaps
            combined_pcm = b""
            current_time = 0.0  # Current position in the recording

            for i, (source, audio_data, segment_start) in enumerate(sorted_segments):
                # Calculate segment duration
                segment_duration = len(audio_data) / (sample_rate * bytes_per_sample)

                # Add silence if there's a gap
                gap = segment_start - current_time
                if gap > 0.1:  # Only add silence for gaps > 100ms
                    silence_samples = int(gap * sample_rate)
                    silence_bytes = silence_samples * bytes_per_sample
                    combined_pcm += b'\x00' * silence_bytes
                    logger.info(f"  Added {gap:.2f}s silence ({silence_bytes} bytes)")
                    current_time += gap

                # Add the audio segment
                combined_pcm += audio_data
                current_time += segment_duration
                logger.info(f"  Segment {i+1}: {source} at {segment_start:.2f}s - {len(audio_data)} bytes ({segment_duration:.2f}s)")

            if len(combined_pcm) > 0:
                # Convert combined PCM to WAV
                combined_wav = self._pcm_to_wav(combined_pcm)
                combined_path = RECORDINGS_DIR / f"{self.recording_id}.wav"

                # Ensure directory exists
                RECORDINGS_DIR.mkdir(exist_ok=True)

                with open(combined_path, "wb") as f:
                    f.write(combined_wav)

                total_duration = len(combined_pcm) / (sample_rate * bytes_per_sample)
                logger.info(f"💾 Saved recording with timing: {combined_path}")
                logger.info(f"   Size: {len(combined_wav)} bytes WAV")
                logger.info(f"   Duration: {total_duration:.2f}s")
                logger.info(f"   Segments: {len(self.recording_segments)}")

            return self.recording_id

        except Exception as e:
            logger.error(f"❌ Failed to save recording: {e}")
            import traceback
            traceback.print_exc()
            return None

    async def stop(self):
        """Stop processing and cleanup"""
        if self.process_task:
            self.process_task.cancel()

        # Close streaming STT (Deepgram)
        if self.streaming_stt:
            await self.streaming_stt.close()
            logger.info("🔌 Deepgram Streaming STT closed")

        # Close Azure streaming STT
        if self.azure_streaming_stt:
            await self.azure_streaming_stt.close()
            logger.info("🔌 Azure Streaming STT closed")

    def generate_waveform_data(self, samples_per_segment: int = 100) -> list[dict]:
        """Generate waveform data for visualization from recording segments"""
        if not self.recording_segments:
            return []

        waveform_data = []
        sample_rate = 16000  # 16kHz
        bytes_per_sample = 2  # 16-bit PCM

        # Sort segments by timestamp
        sorted_segments = sorted(self.recording_segments, key=lambda x: x[2])

        for source, audio_data, segment_start in sorted_segments:
            if len(audio_data) < bytes_per_sample:
                continue

            # Calculate duration of this segment
            num_samples = len(audio_data) // bytes_per_sample
            duration = num_samples / sample_rate

            # Calculate samples per chunk for desired number of samples
            chunk_size = max(1, num_samples // samples_per_segment)
            samples_per_chunk = chunk_size * bytes_per_sample

            # Process audio in chunks
            for i in range(0, len(audio_data), samples_per_chunk):
                chunk = audio_data[i:i + samples_per_chunk]
                if len(chunk) < bytes_per_sample:
                    continue

                # Calculate RMS amplitude for this chunk
                total = 0
                count = 0
                for j in range(0, len(chunk) - 1, 2):
                    sample = struct.unpack("<h", chunk[j:j+2])[0]
                    total += sample * sample
                    count += 1

                if count > 0:
                    rms = (total / count) ** 0.5
                    # Normalize to 0-1 range (max for 16-bit is 32767)
                    amplitude = min(1.0, rms / 32767.0 * 3)  # Scale up for visibility

                    # Use actual timestamp from segment
                    chunk_time = segment_start + (i / len(audio_data)) * duration

                    waveform_data.append({
                        "time": round(chunk_time, 3),
                        "amplitude": round(amplitude, 3),
                        "source": source
                    })

        return waveform_data

    def get_call_duration(self) -> float:
        """Calculate total call duration based on segment timestamps"""
        if not self.recording_segments:
            return 0.0

        sample_rate = 16000
        bytes_per_sample = 2

        # Find the end time of the last segment
        max_end_time = 0.0
        for source, audio_data, segment_start in self.recording_segments:
            segment_duration = len(audio_data) / (sample_rate * bytes_per_sample)
            segment_end = segment_start + segment_duration
            max_end_time = max(max_end_time, segment_end)

        return max_end_time

    def get_call_duration_old(self) -> float:
        """Calculate total call duration from recording segments (sum of audio only)"""
        total_bytes = sum(len(data) for _, data, _ in self.recording_segments)
        sample_rate = 16000
        bytes_per_sample = 2
        return total_bytes / (sample_rate * bytes_per_sample)


@router.websocket("/realtime/{session_id}")
async def realtime_voice_websocket(
    websocket: WebSocket,
    session_id: str,
):
    """
    Real-time voice conversation WebSocket

    Client sends:
    - {"type": "config", "data": {...}} - Configure session
    - {"type": "audio", "data": "<base64_pcm>"} - Audio chunk (PCM 16-bit, 16kHz)
    - {"type": "end"} - End session

    Server sends:
    - {"type": "ready"} - Ready to receive audio
    - {"type": "receiving_audio"} - Receiving audio
    - {"type": "processing"} - Processing speech
    - {"type": "transcript", "role": "user/assistant", "text": "..."} - Transcript
    - {"type": "thinking"} - AI is generating response
    - {"type": "speaking"} - AI is speaking
    - {"type": "audio", "data": "<base64>"} - Audio response
    - {"type": "no_speech"} - No speech detected
    - {"type": "error", "message": "..."} - Error
    """
    await websocket.accept()
    logger.info(f"Realtime WebSocket connected: {session_id}")

    session: Optional[RealtimeVoiceSession] = None
    process_task: Optional[asyncio.Task] = None

    try:
        while True:
            logger.debug(f"⏳ Waiting for message...")
            message = await websocket.receive()
            logger.debug(f"📨 Received message type: {message.get('type', 'unknown')}")

            if message["type"] == "websocket.disconnect":
                logger.info(f"🔌 Client disconnected (websocket.disconnect)")
                break

            if "text" in message:
                data = json.loads(message["text"])
                msg_type = data.get("type")

                if msg_type == "config":
                    config = data.get("data", {})

                    # STT config
                    stt_provider = config.get("stt_provider", "deepgram")
                    stt_api_key = config.get("stt_api_key", "")
                    stt_region = config.get("stt_region")

                    # LLM config
                    llm_provider = config.get("llm_provider", "anthropic")
                    llm_model = config.get("llm_model")
                    llm_temperature = config.get("llm_temperature", 0.7)

                    # Get interruption settings
                    interruption_enabled = config.get("interruption_enabled", True)
                    interruption_words_threshold = config.get("interruption_words_threshold", 0)
                    stop_on_hangup = config.get("stop_on_hangup", True)

                    # TTS settings
                    tts_voice_speed = config.get("tts_voice_speed", 1.0)
                    tts_voice_stability = config.get("tts_voice_stability", 0.5)

                    logger.info(f"🎙️ STT: {stt_provider}")
                    logger.info(f"🤖 LLM: {llm_provider} / {llm_model} / temp={llm_temperature}")
                    logger.info(f"🔊 TTS: {config.get('tts_provider')} / voice={config.get('tts_voice_id')} / speed={tts_voice_speed}")
                    logger.info(f"⚙️ Interruption: enabled={interruption_enabled}, words_threshold={interruption_words_threshold}")

                    session = RealtimeVoiceSession(
                        session_id=session_id,
                        client_ws=websocket,
                        # STT
                        stt_provider=stt_provider,
                        stt_api_key=stt_api_key,
                        stt_region=stt_region,
                        # LLM
                        llm_provider=llm_provider,
                        llm_api_key=config.get("llm_api_key", ""),
                        llm_model=llm_model,
                        llm_temperature=llm_temperature,
                        # TTS
                        tts_provider=config.get("tts_provider", "elevenlabs"),
                        tts_api_key=config.get("tts_api_key", ""),
                        tts_region=config.get("tts_region"),
                        tts_voice_id=config.get("tts_voice_id"),
                        tts_voice_speed=tts_voice_speed,
                        tts_voice_stability=tts_voice_stability,
                        # Other - combine base prompt with user's custom prompt
                        system_prompt=combine_prompts(
                            user_prompt=config.get("system_prompt"),
                            timezone=config.get("timezone", "Africa/Cairo"),
                            language=config.get("language", "ar"),
                        ),
                        language=config.get("language", "ar"),
                        interruption_enabled=interruption_enabled,
                        interruption_words_threshold=interruption_words_threshold,
                        stop_on_hangup=stop_on_hangup,
                    )

                    # 🚀 Initialize streaming STT for real-time transcription
                    streaming_stt_ok = await session.init_streaming_stt()
                    if streaming_stt_ok:
                        logger.info("✅ Streaming STT connected - real-time mode enabled")
                    else:
                        logger.warning("⚠️ Streaming STT not available - using batch mode")

                    # Start background processing task
                    process_task = asyncio.create_task(session.check_and_process())

                    await websocket.send_json({"type": "ready"})
                    logger.info(f"Session {session_id} ready")

                    # Handle first message if assistant speaks first
                    first_message = config.get("first_message", "")
                    first_message_mode = config.get("first_message_mode", "assistant-speaks-first")

                    if first_message_mode == "assistant-speaks-first" and first_message.strip():
                        logger.info(f"🎤 Assistant speaks first: {first_message[:50]}...")
                        try:
                            # 🎯 Split first message into sentences for proper tracking
                            # This allows us to know exactly what was spoken if interrupted
                            import re
                            sentences = re.split(r'([.!?؟])', first_message)
                            # Rejoin punctuation with sentences
                            sentence_list = []
                            for i in range(0, len(sentences)-1, 2):
                                sentence_list.append(sentences[i] + (sentences[i+1] if i+1 < len(sentences) else ''))
                            if len(sentences) % 2 == 1 and sentences[-1].strip():
                                sentence_list.append(sentences[-1])

                            # Filter empty sentences
                            sentence_list = [s.strip() for s in sentence_list if s.strip()]
                            if not sentence_list:
                                sentence_list = [first_message]

                            logger.info(f"📝 First message split into {len(sentence_list)} parts")

                            spoken_first_message = ""
                            session.is_speaking = True
                            await websocket.send_json({"type": "speaking"})

                            for i, sentence in enumerate(sentence_list):
                                # Check for interruption before each sentence
                                if session.should_stop_speaking:
                                    logger.info(f"🛑 First message interrupted at sentence {i+1}/{len(sentence_list)}")
                                    break

                                # Generate TTS for this sentence
                                audio_data = await session.tts.synthesize(sentence)

                                # Check again after TTS
                                if session.should_stop_speaking:
                                    logger.info(f"🛑 First message interrupted after TTS for sentence {i+1}")
                                    break

                                audio_b64 = base64.b64encode(audio_data).decode()

                                # Send audio
                                await websocket.send_json({
                                    "type": "audio",
                                    "data": audio_b64,
                                    "sequence": i + 1,
                                })

                                # Track what was actually sent
                                session.last_audio_sent_time = time.time()
                                spoken_first_message += " " + sentence
                                logger.info(f"📤 First message part {i+1}/{len(sentence_list)}: '{sentence[:30]}...'")

                                # Record in BACKGROUND
                                if session.recording_enabled:
                                    asyncio.create_task(session._record_ai_audio_chunk(sentence))

                            session.is_speaking = False

                            # 🎯 Save ONLY what was actually spoken
                            final_first_message = spoken_first_message.strip()
                            if final_first_message:
                                await websocket.send_json({
                                    "type": "transcript",
                                    "role": "assistant",
                                    "text": final_first_message
                                })
                                session.messages.append(Message(role="assistant", content=final_first_message))
                                session.cost_tracker.add_tts(len(final_first_message), session.tts.provider)

                                if session.should_stop_speaking:
                                    logger.info(f"💾 First message interrupted - saved: '{final_first_message[:50]}...'")
                                else:
                                    logger.info(f"✅ First message complete: '{final_first_message[:50]}...'")

                            # Reset flags
                            session.should_stop_speaking = False

                        except Exception as e:
                            logger.error(f"❌ Failed to send first message: {e}")
                            import traceback
                            traceback.print_exc()

                elif msg_type == "audio" and session:
                    # Decode PCM audio and add to buffer
                    audio_b64 = data.get("data", "")
                    audio_data = base64.b64decode(audio_b64)
                    # Log every ~2 seconds of audio
                    if len(session.audio_buffer) % 32000 < len(audio_data):
                        logger.info(f"🎙️ Audio buffer: {len(session.audio_buffer) // 1000}KB")
                    await session.add_audio_chunk(audio_data)

                elif msg_type == "speech_start" and session:
                    # 🎤 Client detected start of speech (from frontend VAD)
                    # This is important for batch STT providers (Azure, Groq, etc.)
                    session.user_is_speaking = True
                    session.speech_start_time = time.time()
                    logger.info("🎤 Speech started (frontend VAD)")

                elif msg_type == "speech_end" and session:
                    # Client detected end of speech - mark and maybe process
                    session.user_is_speaking = False
                    session.last_speech_end_time = time.time()
                    logger.info(f"🔇 Speech ended - buffer: {len(session.audio_buffer)} bytes")

                    # 🎯 DON'T process immediately! Let check_and_process handle it
                    # This gives time for user to continue speaking after a pause
                    # The check_and_process loop will pick it up after proper timeout

                elif msg_type == "barge_in" and session:
                    # 🛑 BARGE-IN: User interrupted while AI was speaking
                    # Frontend detected user speaking while AI audio was playing
                    logger.info("🛑🛑🛑 BARGE-IN received from frontend! Stopping AI...")

                    # Signal to stop speaking and restart thinking
                    session.should_stop_speaking = True
                    session.should_restart_thinking = True
                    # Note: Don't reset is_speaking/is_thinking/is_processing here
                    # The running process_transcript will handle these flags
                    # We just signal that it should restart

                    # Tell frontend to stop audio (in case it hasn't already)
                    await websocket.send_json({"type": "stop_audio"})

                    # Don't clear audio_buffer - let the restart logic handle the new audio
                    logger.info("✅ Barge-in signal sent - process_transcript will restart")

                elif msg_type == "audio_playing" and session:
                    # 🎯 Frontend is NOW playing this audio chunk
                    # This tells us what was ACTUALLY played (not just sent)
                    sequence = data.get("sequence", 0)
                    session.mark_sequence_played(sequence)
                    logger.debug(f"▶️ Audio sequence {sequence} confirmed playing")

                elif msg_type == "end":
                    logger.info(f"🔚 Session {session_id} ended by client")
                    # Save recording and send cost summary before closing
                    if session:
                        logger.info(f"📊 Session stats: {len(session.recording_segments)} segments, {len(session.messages)} messages")

                        # Save recording
                        recording_id = session.save_recording()
                        logger.info(f"📼 Recording ID: {recording_id}")

                        cost_summary = session.get_cost_summary()
                        # Add recording ID to summary
                        cost_summary["recording_id"] = recording_id

                        logger.info(f"💰 Session cost: ${cost_summary['total_cost']:.6f}")
                        logger.info(f"📤 Sending cost_summary to client...")
                        await websocket.send_json({
                            "type": "cost_summary",
                            "data": cost_summary,
                        })
                        logger.info(f"✅ cost_summary sent successfully")
                    break

    except WebSocketDisconnect:
        logger.info(f"Realtime WebSocket disconnected: {session_id}")
        # Save recording on disconnect
        if session:
            try:
                recording_id = session.save_recording()
                cost_summary = session.get_cost_summary()
                logger.info(f"💰 Session cost (disconnect): ${cost_summary['total_cost']:.6f}, Recording: {recording_id}")
            except Exception as e:
                logger.error(f"Error saving on disconnect: {e}")
    except Exception as e:
        logger.error(f"❌ Realtime WebSocket error: {e}")
        import traceback
        traceback.print_exc()
        # Try to save recording even on error
        if session:
            try:
                recording_id = session.save_recording()
                logger.info(f"📼 Recording saved on error: {recording_id}")
            except Exception as save_err:
                logger.error(f"Failed to save on error: {save_err}")
    finally:
        if process_task:
            process_task.cancel()
        if session:
            await session.stop()
