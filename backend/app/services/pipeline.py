"""
Voice Pipeline Service
Combines STT → LLM → TTS for real-time voice conversations
"""
import asyncio
import time
from typing import Optional, List, Dict, Any, AsyncGenerator, Callable
from dataclasses import dataclass, field
from uuid import UUID
import json
from loguru import logger

from app.services.stt import STTService, StreamingSTTService, TranscriptionResult
from app.services.llm import LLMService, Message, LLMResponse
from app.services.tts import TTSService, TTSConfig


@dataclass
class ConversationTurn:
    """A single turn in the conversation"""
    role: str  # "user" or "assistant"
    text: str
    audio: Optional[bytes] = None
    timestamp: float = field(default_factory=time.time)
    duration_ms: int = 0
    latency_ms: int = 0


@dataclass
class PipelineConfig:
    """Voice pipeline configuration"""
    # STT config
    stt_provider: str = "deepgram"
    stt_api_key: Optional[str] = None
    stt_region: Optional[str] = None
    stt_language: str = "ar"

    # LLM config
    llm_provider: str = "anthropic"
    llm_api_key: Optional[str] = None
    llm_model: Optional[str] = None

    # TTS config
    tts_provider: str = "elevenlabs"
    tts_api_key: Optional[str] = None
    tts_region: Optional[str] = None
    tts_voice_id: Optional[str] = None

    # Pipeline settings
    system_prompt: str = ""
    max_tokens: int = 300  # Keep responses short for voice
    temperature: float = 0.7
    interruption_enabled: bool = True
    silence_timeout_ms: int = 2000


class VoicePipeline:
    """
    Voice Pipeline that processes:
    Audio Input → STT → LLM → TTS → Audio Output
    """

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.conversation_history: List[ConversationTurn] = []
        self.messages: List[Message] = []
        self._is_speaking = False
        self._interrupted = False

        # Initialize services
        self.stt = STTService(
            provider=config.stt_provider,
            api_key=config.stt_api_key,
            region=config.stt_region,
            language=config.stt_language,
        )

        self.llm = LLMService(
            provider=config.llm_provider,
            api_key=config.llm_api_key,
            model=config.llm_model,
        )

        self.tts = TTSService(
            provider=config.tts_provider,
            api_key=config.tts_api_key,
            region=config.tts_region,
            voice_id=config.tts_voice_id,
        )

    async def process_audio(
        self,
        audio_data: bytes,
        sample_rate: int = 16000,
        encoding: str = "linear16",
    ) -> Dict[str, Any]:
        """
        Process audio input and return audio response

        Returns:
            Dict with:
            - user_text: What the user said
            - assistant_text: What the assistant said
            - audio: Audio bytes of the response
            - latency: Processing time in ms
        """
        start_time = time.time()

        # Step 1: STT - Convert speech to text
        logger.info("Starting STT...")
        stt_start = time.time()
        transcription = await self.stt.transcribe(audio_data, sample_rate, encoding)
        stt_time = (time.time() - stt_start) * 1000

        user_text = transcription.text.strip()
        if not user_text:
            return {
                "user_text": "",
                "assistant_text": "",
                "audio": None,
                "error": "No speech detected",
            }

        logger.info(f"User said: {user_text}")

        # Add to conversation history
        self.messages.append(Message(role="user", content=user_text))
        self.conversation_history.append(ConversationTurn(
            role="user",
            text=user_text,
            duration_ms=int(stt_time),
        ))

        # Step 2: LLM - Generate response
        logger.info("Starting LLM...")
        llm_start = time.time()
        response = await self.llm.generate(
            messages=self.messages,
            system_prompt=self.config.system_prompt,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
        )
        llm_time = (time.time() - llm_start) * 1000

        assistant_text = response.text.strip()
        logger.info(f"Assistant says: {assistant_text}")

        # Add to conversation
        self.messages.append(Message(role="assistant", content=assistant_text))

        # Step 3: TTS - Convert text to speech
        logger.info("Starting TTS...")
        tts_start = time.time()
        audio = await self.tts.synthesize(assistant_text)
        tts_time = (time.time() - tts_start) * 1000

        total_latency = (time.time() - start_time) * 1000

        self.conversation_history.append(ConversationTurn(
            role="assistant",
            text=assistant_text,
            audio=audio,
            duration_ms=int(tts_time),
            latency_ms=int(total_latency),
        ))

        logger.info(f"Pipeline complete. Latency: {total_latency:.0f}ms (STT: {stt_time:.0f}ms, LLM: {llm_time:.0f}ms, TTS: {tts_time:.0f}ms)")

        return {
            "user_text": user_text,
            "assistant_text": assistant_text,
            "audio": audio,
            "latency": {
                "total_ms": int(total_latency),
                "stt_ms": int(stt_time),
                "llm_ms": int(llm_time),
                "tts_ms": int(tts_time),
            },
            "usage": response.usage,
        }

    async def process_audio_stream(
        self,
        audio_data: bytes,
        sample_rate: int = 16000,
        encoding: str = "linear16",
        on_text: Optional[Callable[[str], None]] = None,
        on_audio: Optional[Callable[[bytes], None]] = None,
    ) -> AsyncGenerator[bytes, None]:
        """
        Process audio with streaming response

        Yields audio chunks as they are generated
        """
        start_time = time.time()

        # Step 1: STT
        transcription = await self.stt.transcribe(audio_data, sample_rate, encoding)
        user_text = transcription.text.strip()

        if not user_text:
            return

        self.messages.append(Message(role="user", content=user_text))

        if on_text:
            on_text(f"User: {user_text}")

        # Step 2: LLM with streaming
        full_response = ""
        buffer = ""

        self._is_speaking = True

        async for chunk in self.llm.generate_stream(
            messages=self.messages,
            system_prompt=self.config.system_prompt,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
        ):
            if self._interrupted:
                logger.info("Response interrupted by user")
                break

            full_response += chunk
            buffer += chunk

            if on_text:
                on_text(chunk)

            # Generate TTS for complete sentences
            if any(p in buffer for p in [".", "!", "?", "،", "؟", "。"]):
                # Find sentence boundary
                for punct in [".", "!", "?", "،", "؟", "。"]:
                    if punct in buffer:
                        idx = buffer.index(punct) + 1
                        sentence = buffer[:idx]
                        buffer = buffer[idx:].strip()

                        if sentence.strip():
                            async for audio_chunk in self.tts.synthesize_stream(sentence):
                                if self._interrupted:
                                    break
                                if on_audio:
                                    on_audio(audio_chunk)
                                yield audio_chunk
                        break

        # Handle remaining buffer
        if buffer.strip() and not self._interrupted:
            async for audio_chunk in self.tts.synthesize_stream(buffer):
                if on_audio:
                    on_audio(audio_chunk)
                yield audio_chunk

        self._is_speaking = False

        if not self._interrupted:
            self.messages.append(Message(role="assistant", content=full_response))

        self._interrupted = False

    def interrupt(self):
        """Interrupt current response (for barge-in support)"""
        if self._is_speaking:
            self._interrupted = True
            logger.info("Pipeline interrupted")

    def reset(self):
        """Reset conversation history"""
        self.conversation_history = []
        self.messages = []
        self._is_speaking = False
        self._interrupted = False

    def get_transcript(self) -> List[Dict[str, Any]]:
        """Get conversation transcript"""
        return [
            {
                "role": turn.role,
                "text": turn.text,
                "timestamp": turn.timestamp,
                "duration_ms": turn.duration_ms,
            }
            for turn in self.conversation_history
        ]

    def get_messages(self) -> List[Dict[str, str]]:
        """Get messages in LLM format"""
        return [{"role": m.role, "content": m.content} for m in self.messages]


class PipelineManager:
    """Manage multiple voice pipelines for different calls"""

    def __init__(self):
        self.pipelines: Dict[str, VoicePipeline] = {}

    def create_pipeline(
        self,
        call_id: str,
        config: PipelineConfig,
    ) -> VoicePipeline:
        """Create a new pipeline for a call"""
        pipeline = VoicePipeline(config)
        self.pipelines[call_id] = pipeline
        return pipeline

    def get_pipeline(self, call_id: str) -> Optional[VoicePipeline]:
        """Get pipeline for a call"""
        return self.pipelines.get(call_id)

    def remove_pipeline(self, call_id: str):
        """Remove pipeline when call ends"""
        if call_id in self.pipelines:
            del self.pipelines[call_id]

    def get_active_calls(self) -> List[str]:
        """Get list of active call IDs"""
        return list(self.pipelines.keys())


# Global pipeline manager
pipeline_manager = PipelineManager()
