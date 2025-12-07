"""
Ultra-Low Latency Real-Time Voice Pipeline
Target: < 500ms total response time (human-like conversation)

Architecture:
1. Deepgram WebSocket STT (real-time transcription)
2. Groq LLM (fastest - ~100ms first token)
3. Streaming TTS (sentence-by-sentence)
4. All running in parallel
"""
import asyncio
import json
import base64
import time
from typing import Optional, Callable, Awaitable, List
from dataclasses import dataclass
import websockets
import httpx
from loguru import logger


@dataclass
class LatencyMetrics:
    """Track latency for each component"""
    stt_ms: int = 0
    llm_first_token_ms: int = 0
    tts_first_chunk_ms: int = 0
    total_ms: int = 0


class UltraFastPipeline:
    """
    Ultra-low latency voice pipeline optimized for Arabic

    Key optimizations:
    - Deepgram WebSocket with fast endpointing (300ms)
    - Groq LLM streaming (fastest available)
    - Sentence-based TTS (don't wait for full response)
    - Connection pooling (reuse connections)
    """

    def __init__(
        self,
        # STT
        stt_api_key: str,
        stt_language: str = "ar",
        # LLM
        llm_api_key: str,
        llm_provider: str = "groq",  # Default to fastest
        llm_model: str = "llama-3.3-70b-versatile",
        # TTS
        tts_api_key: str,
        tts_provider: str = "azure",  # Best Arabic + fast
        tts_voice_id: str = "ar-SA-HamedNeural",
        tts_region: str = "eastus",
        # System
        system_prompt: str = "أنت مساعد صوتي ذكي. كن مختصراً جداً في ردودك.",
        on_transcript: Optional[Callable[[str, str], Awaitable[None]]] = None,
        on_audio: Optional[Callable[[bytes], Awaitable[None]]] = None,
        on_latency: Optional[Callable[[LatencyMetrics], Awaitable[None]]] = None,
    ):
        self.stt_api_key = stt_api_key
        self.stt_language = stt_language
        self.llm_api_key = llm_api_key
        self.llm_provider = llm_provider
        self.llm_model = llm_model
        self.tts_api_key = tts_api_key
        self.tts_provider = tts_provider
        self.tts_voice_id = tts_voice_id
        self.tts_region = tts_region
        self.system_prompt = system_prompt

        # Callbacks
        self.on_transcript = on_transcript
        self.on_audio = on_audio
        self.on_latency = on_latency

        # State
        self.messages: List[dict] = []
        self.is_processing = False
        self.should_stop = False

        # Shared HTTP client for connection reuse
        self._http_client: Optional[httpx.AsyncClient] = None

        # Deepgram WebSocket
        self._stt_ws: Optional[websockets.WebSocketClientProtocol] = None
        self._stt_connected = False

        # Metrics
        self.last_metrics = LatencyMetrics()

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create shared HTTP client"""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                timeout=30.0,
                http2=True,
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
            )
        return self._http_client

    async def connect_stt(self) -> bool:
        """Connect to Deepgram WebSocket for real-time STT"""
        try:
            # Use Whisper for Arabic (Nova-2 doesn't support it)
            is_arabic = self.stt_language.lower().startswith("ar")
            model = "whisper-large" if is_arabic else "nova-2"

            params = [
                f"model={model}",
                f"language={self.stt_language}",
                "encoding=linear16",
                "sample_rate=16000",
                "channels=1",
                "punctuate=true",
                "interim_results=true",
                "endpointing=300",  # Fast endpointing!
                "utterance_end_ms=1000",
                "vad_events=true",
            ]

            url = f"wss://api.deepgram.com/v1/listen?{'&'.join(params)}"
            headers = {"Authorization": f"Token {self.stt_api_key}"}

            self._stt_ws = await websockets.connect(
                url,
                extra_headers=headers,
                ping_interval=5,
                ping_timeout=20,
            )
            self._stt_connected = True
            logger.info("✅ Deepgram STT WebSocket connected")
            return True

        except Exception as e:
            logger.error(f"Failed to connect STT: {e}")
            return False

    async def send_audio(self, audio_chunk: bytes):
        """Send audio to Deepgram for transcription"""
        if self._stt_ws and self._stt_connected:
            try:
                await self._stt_ws.send(audio_chunk)
            except Exception as e:
                logger.error(f"Failed to send audio: {e}")
                self._stt_connected = False

    async def receive_transcripts(self, on_final: Callable[[str], Awaitable[None]]):
        """Receive transcripts from Deepgram"""
        if not self._stt_ws:
            return

        try:
            async for message in self._stt_ws:
                if self.should_stop:
                    break

                data = json.loads(message)
                msg_type = data.get("type", "")

                if msg_type == "Results":
                    channel = data.get("channel", {})
                    alternatives = channel.get("alternatives", [])

                    if alternatives:
                        transcript = alternatives[0].get("transcript", "")
                        is_final = data.get("is_final", False)
                        speech_final = data.get("speech_final", False)

                        if transcript.strip():
                            if self.on_transcript:
                                await self.on_transcript("interim" if not is_final else "user", transcript)

                            # Process on final transcript
                            if is_final and speech_final:
                                await on_final(transcript)

                elif msg_type == "UtteranceEnd":
                    logger.debug("Utterance ended")

        except websockets.exceptions.ConnectionClosed:
            logger.info("STT WebSocket closed")
        except Exception as e:
            logger.error(f"STT receive error: {e}")
        finally:
            self._stt_connected = False

    async def process_user_input(self, text: str):
        """Process user input and generate response"""
        if self.is_processing or not text.strip():
            return

        self.is_processing = True
        speech_end_time = time.time()

        try:
            # Add user message
            self.messages.append({"role": "user", "content": text})

            if self.on_transcript:
                await self.on_transcript("user", text)

            # Generate response with streaming
            full_response = ""
            sentence_buffer = ""
            first_token_time = None
            first_audio_time = None

            # Sentence endings for Arabic and English (NOT commas!)
            # Arabic comma ، causes fragmented speech if included
            sentence_endings = {'.', '!', '?', '؟'}

            async for token in self._stream_llm():
                if self.should_stop:
                    break

                # Track first token latency
                if first_token_time is None:
                    first_token_time = time.time()
                    llm_latency = int((first_token_time - speech_end_time) * 1000)
                    logger.info(f"⚡ LLM first token: {llm_latency}ms")
                    self.last_metrics.llm_first_token_ms = llm_latency

                full_response += token
                sentence_buffer += token

                # Check for complete sentence
                for ending in sentence_endings:
                    if ending in sentence_buffer:
                        parts = sentence_buffer.split(ending, 1)
                        sentence = parts[0] + ending
                        sentence_buffer = parts[1] if len(parts) > 1 else ""

                        # Synthesize and send immediately
                        if sentence.strip():
                            audio = await self._synthesize_tts(sentence.strip())
                            if audio and self.on_audio:
                                if first_audio_time is None:
                                    first_audio_time = time.time()
                                    tts_latency = int((first_audio_time - first_token_time) * 1000)
                                    total_latency = int((first_audio_time - speech_end_time) * 1000)
                                    logger.info(f"⚡ TTS first chunk: {tts_latency}ms, Total: {total_latency}ms")
                                    self.last_metrics.tts_first_chunk_ms = tts_latency
                                    self.last_metrics.total_ms = total_latency

                                    if self.on_latency:
                                        await self.on_latency(self.last_metrics)

                                await self.on_audio(audio)
                        break

            # Send remaining text
            if sentence_buffer.strip() and not self.should_stop:
                audio = await self._synthesize_tts(sentence_buffer.strip())
                if audio and self.on_audio:
                    await self.on_audio(audio)

            # Add assistant response
            if full_response.strip():
                self.messages.append({"role": "assistant", "content": full_response.strip()})
                if self.on_transcript:
                    await self.on_transcript("assistant", full_response.strip())

        except Exception as e:
            logger.error(f"Process error: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.is_processing = False

    async def _stream_llm(self):
        """Stream LLM response (Groq is fastest)"""
        client = await self._get_http_client()

        if self.llm_provider == "groq":
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.llm_api_key}",
                "Content-Type": "application/json",
            }
        elif self.llm_provider == "anthropic":
            url = "https://api.anthropic.com/v1/messages"
            headers = {
                "x-api-key": self.llm_api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            }
        else:
            # OpenAI-compatible
            url = "https://api.openai.com/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {self.llm_api_key}",
                "Content-Type": "application/json",
            }

        # Build messages
        messages = [{"role": "system", "content": self.system_prompt}]
        messages.extend(self.messages[-10:])  # Last 10 messages for context

        if self.llm_provider == "anthropic":
            payload = {
                "model": self.llm_model,
                "max_tokens": 150,
                "temperature": 0.7,
                "messages": [m for m in messages if m["role"] != "system"],
                "system": self.system_prompt,
                "stream": True,
            }
        else:
            payload = {
                "model": self.llm_model,
                "max_tokens": 150,
                "temperature": 0.7,
                "messages": messages,
                "stream": True,
            }

        try:
            async with client.stream("POST", url, headers=headers, json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: ") and line != "data: [DONE]":
                        try:
                            data = json.loads(line[6:])

                            if self.llm_provider == "anthropic":
                                if data.get("type") == "content_block_delta":
                                    yield data.get("delta", {}).get("text", "")
                            else:
                                delta = data.get("choices", [{}])[0].get("delta", {})
                                if "content" in delta:
                                    yield delta["content"]
                        except:
                            continue
        except Exception as e:
            logger.error(f"LLM streaming error: {e}")
            # Fallback to non-streaming
            try:
                payload["stream"] = False
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                result = response.json()

                if self.llm_provider == "anthropic":
                    text = result.get("content", [{}])[0].get("text", "")
                else:
                    text = result.get("choices", [{}])[0].get("message", {}).get("content", "")

                if text:
                    yield text
            except Exception as e2:
                logger.error(f"LLM fallback error: {e2}")

    async def _synthesize_tts(self, text: str) -> Optional[bytes]:
        """Synthesize TTS (Azure is best for Arabic)"""
        if not text.strip():
            return None

        client = await self._get_http_client()

        try:
            if self.tts_provider == "azure":
                url = f"https://{self.tts_region}.tts.speech.microsoft.com/cognitiveservices/v1"
                headers = {
                    "Ocp-Apim-Subscription-Key": self.tts_api_key,
                    "Content-Type": "application/ssml+xml",
                    "X-Microsoft-OutputFormat": "audio-16khz-128kbitrate-mono-mp3",
                }

                ssml = f"""
                <speak version='1.0' xmlns='http://www.w3.org/2001/10/synthesis' xml:lang='ar-SA'>
                    <voice name='{self.tts_voice_id}'>
                        <prosody rate='1.1'>{text}</prosody>
                    </voice>
                </speak>
                """

                response = await client.post(url, headers=headers, content=ssml.strip())
                response.raise_for_status()
                return response.content

            elif self.tts_provider == "elevenlabs":
                url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.tts_voice_id}"
                headers = {
                    "xi-api-key": self.tts_api_key,
                    "Content-Type": "application/json",
                }
                payload = {
                    "text": text,
                    "model_id": "eleven_multilingual_v2",
                    "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
                }

                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                return response.content

            elif self.tts_provider == "openai":
                url = "https://api.openai.com/v1/audio/speech"
                headers = {
                    "Authorization": f"Bearer {self.tts_api_key}",
                    "Content-Type": "application/json",
                }
                payload = {
                    "model": "tts-1",
                    "input": text,
                    "voice": self.tts_voice_id or "nova",
                    "response_format": "mp3",
                }

                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                return response.content

        except Exception as e:
            logger.error(f"TTS error: {e}")
            return None

    async def close(self):
        """Close all connections"""
        self.should_stop = True

        if self._stt_ws:
            try:
                await self._stt_ws.send(json.dumps({"type": "CloseStream"}))
                await self._stt_ws.close()
            except:
                pass

        if self._http_client:
            await self._http_client.aclose()

        logger.info("Pipeline closed")
