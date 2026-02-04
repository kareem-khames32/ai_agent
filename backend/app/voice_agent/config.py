"""
Voice Agent Configuration
"""
import os
from dataclasses import dataclass, field
from typing import Optional, Dict, Any


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

    # Barge-in (Interruption) Settings
    enable_interruption: bool = True    # Allow customer to interrupt
    interruption_words: int = 2         # Words required to trigger interruption
    interruption_cooldown_ms: int = 150 # Short cooldown - trust browser echo cancellation

    # STT Settings
    stt_provider: str = "deepgram"  # deepgram, openai (Whisper), azure, groq
    stt_api_key: Optional[str] = None   # Will use env if None
    stt_language: str = "ar"            # Arabic
    stt_model: str = "nova-2"
    stt_interim_results: bool = True
    stt_punctuate: bool = True
    stt_endpointing_ms: int = 500
    stt_region: Optional[str] = None    # For Azure

    # LLM Settings
    llm_provider: str = "openai"
    llm_api_key: Optional[str] = None   # Will use env if None
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.7
    llm_max_tokens: int = 200
    llm_context_turns: int = 10         # Keep last N turns

    # TTS Settings
    tts_provider: str = "openai"        # openai, elevenlabs, cartesia, azure
    tts_api_key: Optional[str] = None   # Will use env if None
    tts_voice: str = "alloy"
    tts_speed: float = 1.0
    tts_region: Optional[str] = None    # For Azure

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


def create_config_from_assistant(
    assistant: Dict[str, Any],
    credentials: Dict[str, Dict[str, str]]
) -> VoiceAgentConfig:
    """
    Create VoiceAgentConfig from assistant settings and credentials

    Args:
        assistant: Assistant configuration dict with:
            - model_provider: openai, anthropic, google, groq, etc.
            - model_name: gpt-4o-mini, claude-sonnet, etc.
            - voice_provider: elevenlabs, azure, openai, etc.
            - voice_id: Voice ID for TTS
            - transcriber_provider: deepgram, azure, openai, etc.
            - transcriber_language: ar, ar-SA, en, etc.
            - temperature, max_tokens, etc.

        credentials: Dict of provider credentials:
            {
                "openai": {"api_key": "sk-..."},
                "deepgram": {"api_key": "..."},
                "elevenlabs": {"api_key": "..."},
                "azure_speech": {"api_key": "...", "region": "eastus"},
                ...
            }

    Returns:
        VoiceAgentConfig with all settings
    """
    config = VoiceAgentConfig()

    # === STT Configuration ===
    stt_provider = assistant.get("transcriber_provider", "deepgram").lower()
    config.stt_provider = stt_provider
    config.stt_language = assistant.get("transcriber_language", "ar")

    # Get STT credentials
    if stt_provider == "deepgram":
        creds = credentials.get("deepgram", {})
        config.stt_api_key = creds.get("api_key")
        config.stt_model = "nova-2"
    elif stt_provider == "azure":
        creds = credentials.get("azure_speech", {})
        config.stt_api_key = creds.get("api_key")
        config.stt_region = creds.get("region", "eastus")
    elif stt_provider == "openai":
        creds = credentials.get("openai_whisper", {}) or credentials.get("openai", {})
        config.stt_api_key = creds.get("api_key")
    elif stt_provider == "groq":
        creds = credentials.get("groq_whisper", {}) or credentials.get("groq", {})
        config.stt_api_key = creds.get("api_key")

    # === LLM Configuration ===
    llm_provider = assistant.get("model_provider", "openai").lower()
    config.llm_provider = llm_provider
    config.llm_model = assistant.get("model_name", "gpt-4o-mini")
    config.llm_temperature = assistant.get("temperature", 0.7)
    config.llm_max_tokens = assistant.get("max_tokens", 200)

    # Get LLM credentials
    if llm_provider in ["openai"]:
        creds = credentials.get("openai", {})
        config.llm_api_key = creds.get("api_key")
    elif llm_provider == "anthropic":
        creds = credentials.get("anthropic", {})
        config.llm_api_key = creds.get("api_key")
    elif llm_provider == "google":
        creds = credentials.get("google", {})
        config.llm_api_key = creds.get("api_key")
    elif llm_provider == "groq":
        creds = credentials.get("groq", {})
        config.llm_api_key = creds.get("api_key")
    elif llm_provider == "together":
        creds = credentials.get("together", {})
        config.llm_api_key = creds.get("api_key")

    # === TTS Configuration ===
    tts_provider = assistant.get("voice_provider", "openai").lower()
    config.tts_provider = tts_provider
    config.tts_voice = assistant.get("voice_id", "alloy")

    # Get TTS credentials
    if tts_provider == "openai":
        creds = credentials.get("openai_tts", {}) or credentials.get("openai", {})
        config.tts_api_key = creds.get("api_key")
    elif tts_provider == "elevenlabs":
        creds = credentials.get("elevenlabs", {})
        config.tts_api_key = creds.get("api_key")
    elif tts_provider == "azure":
        creds = credentials.get("azure_tts", {})
        config.tts_api_key = creds.get("api_key")
        config.tts_region = creds.get("region", "eastus")
    elif tts_provider == "cartesia":
        creds = credentials.get("cartesia", {})
        config.tts_api_key = creds.get("api_key")
    elif tts_provider == "deepgram":
        creds = credentials.get("deepgram_tts", {}) or credentials.get("deepgram", {})
        config.tts_api_key = creds.get("api_key")
    elif tts_provider == "google":
        creds = credentials.get("google_tts", {}) or credentials.get("google", {})
        config.tts_api_key = creds.get("api_key")

    # Voice settings
    voice_settings = assistant.get("voice_settings", {})
    if voice_settings.get("speed"):
        config.tts_speed = voice_settings["speed"]

    # Transcriber settings
    transcriber_settings = assistant.get("transcriber_settings", {})
    if transcriber_settings.get("endpointing_ms"):
        config.stt_endpointing_ms = transcriber_settings["endpointing_ms"]

    # Barge-in (Interruption) settings
    stop_speaking_plan = assistant.get("stop_speaking_plan", {})
    if "enable_interruption" in stop_speaking_plan:
        config.enable_interruption = stop_speaking_plan["enable_interruption"]
    if "interruption_words" in stop_speaking_plan:
        config.interruption_words = stop_speaking_plan["interruption_words"]

    return config
