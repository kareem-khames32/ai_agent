"""
LLM Streaming Response
Generates AI responses with streaming tokens
Supports: OpenAI, Anthropic, Google, Groq, Together
Uses HTTP directly - no SDK packages required
"""
import os
import asyncio
import json
import httpx
from typing import Optional, Callable, Awaitable, AsyncGenerator, List, Any
from dataclasses import dataclass, field

from ..utils.logger import get_logger
from ..config import VoiceAgentConfig

logger = get_logger(__name__)


@dataclass
class Message:
    """Chat message"""
    role: str  # "user", "assistant", "system"
    content: str


@dataclass
class LLMContext:
    """LLM conversation context"""
    system_prompt: str = ""
    messages: List[Message] = field(default_factory=list)
    max_turns: int = 10

    def add_message(self, role: str, content: str):
        """Add message and trim if needed"""
        self.messages.append(Message(role=role, content=content))
        while len(self.messages) > self.max_turns * 2:
            self.messages.pop(0)

    def get_messages_for_api(self) -> List[dict]:
        """Get messages in API format"""
        messages = []
        if self.system_prompt:
            messages.append({"role": "system", "content": self.system_prompt})
        for msg in self.messages:
            messages.append({"role": msg.role, "content": msg.content})
        return messages

    def clear(self):
        """Clear conversation history"""
        self.messages.clear()


class LLMStreamer:
    """
    LLM Streaming Response Generator

    Supports multiple providers (via HTTP - no SDK required):
    - OpenAI (gpt-4o, gpt-4o-mini)
    - Anthropic (claude-sonnet, claude-haiku)
    - Google (gemini-pro, gemini-flash)
    - Groq (llama, mixtral)
    - Together (various open source models)
    """

    def __init__(self, config: VoiceAgentConfig):
        self.config = config
        self.context = LLMContext(max_turns=config.llm_context_turns)
        self.provider = (config.llm_provider or "openai").lower()
        self.api_key: Optional[str] = None

        # State
        self.is_generating = False
        self.should_cancel = False

        # Callbacks
        self.on_token: Optional[Callable[[str], Awaitable[None]]] = None
        self.on_sentence: Optional[Callable[[str], Awaitable[None]]] = None
        self.on_complete: Optional[Callable[[str], Awaitable[None]]] = None

        logger.info(f"LLMStreamer initialized (provider={self.provider}, model={config.llm_model})")

    async def initialize(self) -> bool:
        """Initialize LLM - just validate API key"""
        self.api_key = self.config.llm_api_key

        if self.provider == "openai":
            self.api_key = self.api_key or os.getenv("OPENAI_API_KEY")
            if not self.api_key:
                logger.error("OpenAI API key not set")
                return False
            logger.info("✅ OpenAI LLM ready")

        elif self.provider == "anthropic":
            self.api_key = self.api_key or os.getenv("ANTHROPIC_API_KEY")
            if not self.api_key:
                logger.error("Anthropic API key not set")
                return False
            logger.info("✅ Anthropic LLM ready")

        elif self.provider == "google":
            self.api_key = self.api_key or os.getenv("GOOGLE_API_KEY")
            if not self.api_key:
                logger.error("Google API key not set")
                return False
            logger.info("✅ Google LLM ready")

        elif self.provider == "groq":
            self.api_key = self.api_key or os.getenv("GROQ_API_KEY")
            if not self.api_key:
                logger.error("Groq API key not set")
                return False
            logger.info("✅ Groq LLM ready")

        elif self.provider == "together":
            self.api_key = self.api_key or os.getenv("TOGETHER_API_KEY")
            if not self.api_key:
                logger.error("Together API key not set")
                return False
            logger.info("✅ Together LLM ready")

        else:
            logger.error(f"Unknown LLM provider: {self.provider}")
            return False

        return True

    def set_system_prompt(self, prompt: str):
        """Set the system prompt"""
        self.context.system_prompt = prompt
        logger.debug(f"System prompt set ({len(prompt)} chars)")

    def add_user_message(self, content: str):
        """Add user message to context"""
        self.context.add_message("user", content)

    def add_assistant_message(self, content: str):
        """Add assistant message to context"""
        self.context.add_message("assistant", content)

    async def generate_stream(self, user_input: str) -> AsyncGenerator[str, None]:
        """Generate streaming response"""
        if not self.api_key:
            if not await self.initialize():
                logger.error("Failed to initialize LLM")
                return

        self.add_user_message(user_input)
        self.is_generating = True
        self.should_cancel = False
        full_response = ""
        current_sentence = ""

        try:
            logger.info(f"🤖 LLM generating ({self.provider}): \"{user_input[:50]}...\"")

            if self.provider in ["openai", "groq", "together"]:
                async for token in self._stream_openai_compatible():
                    if self.should_cancel:
                        break
                    full_response += token
                    current_sentence += token
                    if self.on_token:
                        await self.on_token(token)
                    if self._is_sentence_end(current_sentence):
                        if self.on_sentence and current_sentence.strip():
                            await self.on_sentence(current_sentence.strip())
                        current_sentence = ""
                    yield token

            elif self.provider == "anthropic":
                async for token in self._stream_anthropic():
                    if self.should_cancel:
                        break
                    full_response += token
                    current_sentence += token
                    if self.on_token:
                        await self.on_token(token)
                    if self._is_sentence_end(current_sentence):
                        if self.on_sentence and current_sentence.strip():
                            await self.on_sentence(current_sentence.strip())
                        current_sentence = ""
                    yield token

            elif self.provider == "google":
                async for token in self._stream_google():
                    if self.should_cancel:
                        break
                    full_response += token
                    current_sentence += token
                    if self.on_token:
                        await self.on_token(token)
                    if self._is_sentence_end(current_sentence):
                        if self.on_sentence and current_sentence.strip():
                            await self.on_sentence(current_sentence.strip())
                        current_sentence = ""
                    yield token

            # Handle remaining text
            if current_sentence.strip() and not self.should_cancel:
                if self.on_sentence:
                    await self.on_sentence(current_sentence.strip())

            # Always save response to history (even partial on barge-in)
            # This prevents the AI from repeating itself
            if full_response:
                self.add_assistant_message(full_response)
                if self.should_cancel:
                    logger.info(f"🛑 LLM interrupted, saved partial: \"{full_response[:50]}...\"")
                else:
                    logger.info(f"✅ LLM complete: \"{full_response[:100]}...\"")
                    if self.on_complete:
                        await self.on_complete(full_response)

        except Exception as e:
            logger.error(f"LLM generation error: {e}")
        finally:
            self.is_generating = False

    async def _stream_openai_compatible(self) -> AsyncGenerator[str, None]:
        """Stream from OpenAI-compatible API (OpenAI, Groq, Together)"""
        if self.provider == "openai":
            url = "https://api.openai.com/v1/chat/completions"
        elif self.provider == "groq":
            url = "https://api.groq.com/openai/v1/chat/completions"
        elif self.provider == "together":
            url = "https://api.together.xyz/v1/chat/completions"
        else:
            url = "https://api.openai.com/v1/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        data = {
            "model": self.config.llm_model,
            "messages": self.context.get_messages_for_api(),
            "temperature": self.config.llm_temperature,
            "max_tokens": self.config.llm_max_tokens,
            "stream": True
        }

        first_token = True
        async with httpx.AsyncClient() as client:
            async with client.stream("POST", url, headers=headers, json=data, timeout=60.0) as response:
                if response.status_code != 200:
                    error = await response.aread()
                    logger.error(f"LLM API error: {error}")
                    return

                async for line in response.aiter_lines():
                    if self.should_cancel:
                        break
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_str)
                            if chunk.get("choices") and chunk["choices"][0].get("delta", {}).get("content"):
                                token = chunk["choices"][0]["delta"]["content"]
                                if first_token:
                                    logger.info("⚡ LLM first token received")
                                    first_token = False
                                yield token
                        except json.JSONDecodeError:
                            continue

    async def _stream_anthropic(self) -> AsyncGenerator[str, None]:
        """Stream from Anthropic API"""
        url = "https://api.anthropic.com/v1/messages"

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }

        # Format messages for Anthropic
        messages = []
        for msg in self.context.messages:
            messages.append({"role": msg.role, "content": msg.content})

        data = {
            "model": self.config.llm_model,
            "max_tokens": self.config.llm_max_tokens,
            "system": self.context.system_prompt,
            "messages": messages,
            "stream": True
        }

        first_token = True
        async with httpx.AsyncClient() as client:
            async with client.stream("POST", url, headers=headers, json=data, timeout=60.0) as response:
                if response.status_code != 200:
                    error = await response.aread()
                    logger.error(f"Anthropic API error: {error}")
                    return

                async for line in response.aiter_lines():
                    if self.should_cancel:
                        break
                    if line.startswith("data: "):
                        data_str = line[6:]
                        try:
                            event = json.loads(data_str)
                            if event.get("type") == "content_block_delta":
                                delta = event.get("delta", {})
                                if delta.get("type") == "text_delta":
                                    token = delta.get("text", "")
                                    if token:
                                        if first_token:
                                            logger.info("⚡ LLM first token received")
                                            first_token = False
                                        yield token
                        except json.JSONDecodeError:
                            continue

    async def _stream_google(self) -> AsyncGenerator[str, None]:
        """Stream from Google AI API"""
        model = self.config.llm_model or "gemini-1.5-flash"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent"

        headers = {"Content-Type": "application/json"}
        params = {"key": self.api_key}

        # Build contents
        contents = []
        for msg in self.context.messages:
            role = "user" if msg.role == "user" else "model"
            contents.append({"role": role, "parts": [{"text": msg.content}]})

        data = {
            "contents": contents,
            "generationConfig": {
                "temperature": self.config.llm_temperature,
                "maxOutputTokens": self.config.llm_max_tokens
            }
        }

        if self.context.system_prompt:
            data["systemInstruction"] = {"parts": [{"text": self.context.system_prompt}]}

        first_token = True
        async with httpx.AsyncClient() as client:
            async with client.stream("POST", url, headers=headers, params=params, json=data, timeout=60.0) as response:
                if response.status_code != 200:
                    error = await response.aread()
                    logger.error(f"Google API error: {error}")
                    return

                buffer = ""
                async for chunk in response.aiter_bytes():
                    buffer += chunk.decode('utf-8')
                    # Parse JSON objects from buffer
                    while True:
                        try:
                            # Find complete JSON object
                            start = buffer.find('{')
                            if start == -1:
                                break
                            # Try to parse
                            end = start + 1
                            depth = 1
                            while end < len(buffer) and depth > 0:
                                if buffer[end] == '{':
                                    depth += 1
                                elif buffer[end] == '}':
                                    depth -= 1
                                end += 1
                            if depth == 0:
                                json_str = buffer[start:end]
                                buffer = buffer[end:]
                                obj = json.loads(json_str)
                                candidates = obj.get("candidates", [])
                                if candidates:
                                    content = candidates[0].get("content", {})
                                    parts = content.get("parts", [])
                                    for part in parts:
                                        text = part.get("text", "")
                                        if text:
                                            if first_token:
                                                logger.info("⚡ LLM first token received")
                                                first_token = False
                                            yield text
                            else:
                                break
                        except json.JSONDecodeError:
                            break

    async def generate(self, user_input: str) -> str:
        """Generate complete response (non-streaming)"""
        response = ""
        async for token in self.generate_stream(user_input):
            response += token
        return response

    def cancel(self):
        """Cancel current generation (for barge-in)"""
        if self.is_generating:
            self.should_cancel = True
            logger.info("🛑 LLM cancellation requested")

    def _is_sentence_end(self, text: str) -> bool:
        """Check if text ends with sentence boundary"""
        text = text.strip()
        if not text:
            return False
        endings = ['.', '!', '?', '؟', '،', ':', '؛', '\n']
        return any(text.endswith(e) for e in endings)

    def clear_context(self):
        """Clear conversation context"""
        self.context.clear()
        logger.debug("LLM context cleared")

    @property
    def conversation_length(self) -> int:
        """Get number of messages in context"""
        return len(self.context.messages)
