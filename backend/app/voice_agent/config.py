"""
Voice Agent Configuration
"""
import os
from dataclasses import dataclass
from typing import Optional

@dataclass
class VoiceAgentConfig:
    """Configuration for the voice agent pipeline"""

    # Audio Settings
    sample_rate_input: int = 16000      # Input from client (16kHz)
    sample_rate_output: int = 24000     # Output to client (24kHz)
    chunk_size_ms: int = 20             # 20ms chunks
    channels: int = 1                   # Mono

    # VAD Settings
    vad_threshold: float = 0.5          # Speech detection threshold
    vad_min_speech_ms: int = 250        # Minimum speech duration
    vad_silence_threshold_ms: int = 500 # Silence to end speech
    vad_padding_ms: int = 300           # Padding around speech

    # Turn Detection
    turn_silence_ms: int = 700          # Silence for turn end
    turn_max_wait_ms: int = 2000        # Max wait before forcing turn
    punctuation_reduces_silence: bool = True

    # STT Settings (Deepgram)
    stt_provider: str = "deepgram"
    stt_language: str = "ar"            # Arabic
    stt_model: str = "nova-2"
    stt_interim_results: bool = True
    stt_punctuate: bool = True
    stt_endpointing_ms: int = 500

    # LLM Settings
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.7
    llm_max_tokens: int = 200
    llm_context_turns: int = 10         # Keep last N turns

    # TTS Settings
    tts_provider: str = "openai"        # openai, elevenlabs, cartesia
    tts_voice: str = "alloy"
    tts_speed: float = 1.0

    # Latency Targets (ms)
    target_e2e_latency: int = 800
    target_stt_latency: int = 200
    target_llm_ttft: int = 300          # Time to first token
    target_tts_ttfb: int = 150          # Time to first byte
    target_bargein_response: int = 100

    @property
    def chunk_samples(self) -> int:
        """Number of samples per chunk"""
        return int(self.sample_rate_input * self.chunk_size_ms / 1000)

    @property
    def chunk_bytes(self) -> int:
        """Bytes per chunk (16-bit PCM)"""
        return self.chunk_samples * 2  # 2 bytes per sample


def get_config() -> VoiceAgentConfig:
    """Get configuration with environment overrides"""
    config = VoiceAgentConfig()

    # Override from environment
    if os.getenv("VAD_SILENCE_THRESHOLD_MS"):
        config.vad_silence_threshold_ms = int(os.getenv("VAD_SILENCE_THRESHOLD_MS"))
    if os.getenv("TURN_SILENCE_MS"):
        config.turn_silence_ms = int(os.getenv("TURN_SILENCE_MS"))
    if os.getenv("STT_LANGUAGE"):
        config.stt_language = os.getenv("STT_LANGUAGE")
    if os.getenv("LLM_MODEL"):
        config.llm_model = os.getenv("LLM_MODEL")
    if os.getenv("TTS_PROVIDER"):
        config.tts_provider = os.getenv("TTS_PROVIDER")
    if os.getenv("TTS_VOICE"):
        config.tts_voice = os.getenv("TTS_VOICE")

    return config
