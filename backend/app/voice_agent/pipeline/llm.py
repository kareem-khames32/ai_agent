"""
LLM Streaming Response
Generates AI responses with streaming tokens
Supports: OpenAI, Anthropic, Google, Groq, Together
"""
import os
import asyncio
from typing import Optional, Callable, Awaitable, AsyncGenerator, List, Any
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

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

    Supports multiple providers:
    - OpenAI (gpt-4o, gpt-4o-mini)
    - Anthropic (claude-sonnet, claude-haiku)
    - Google (gemini-pro, gemini-flash)
    - Groq (llama, mixtral)
    - Together (various open source models)
    """

    def __init__(self, config: VoiceAgentConfig):
        self.config = config
        self.client: Any = None
        self.context = LLMContext(max_turns=config.llm_context_turns)
        self.provider = config.llm_provider.lower()

        # State
        self.is_generating = False
        self.should_cancel = False

        # Callbacks
        self.on_token: Optional[Callable[[str], Awaitable[None]]] = None
        self.on_sentence: Optional[Callable[[str], Awaitable[None]]] = None
        self.on_complete: Optional[Callable[[str], Awaitable[None]]] = None

        logger.info(f"LLMStreamer initialized (provider={self.provider}, model={config.llm_model})")

    async def initialize(self) -> bool:
        """Initialize LLM client based on provider"""
        api_key = self.config.llm_api_key

        if self.provider == "openai":
            api_key = api_key or os.getenv("OPENAI_API_KEY")
            if not api_key:
                logger.error("OpenAI API key not set")
                return False
            from openai import AsyncOpenAI
            self.client = AsyncOpenAI(api_key=api_key)
            logger.info("✅ OpenAI client initialized")

        elif self.provider == "anthropic":
            api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                logger.error("Anthropic API key not set")
                return False
            try:
                from anthropic import AsyncAnthropic
                self.client = AsyncAnthropic(api_key=api_key)
                logger.info("✅ Anthropic client initialized")
            except ImportError:
                logger.error("anthropic package not installed")
                return False

        elif self.provider == "google":
            api_key = api_key or os.getenv("GOOGLE_API_KEY")
            if not api_key:
                logger.error("Google API key not set")
                return False
            try:
                import google.generativeai as genai
                genai.configure(api_key=api_key)
                self.client = genai.GenerativeModel(self.config.llm_model)
                logger.info("✅ Google AI client initialized")
            except ImportError:
                logger.error("google-generativeai package not installed")
                return False

        elif self.provider == "groq":
            api_key = api_key or os.getenv("GROQ_API_KEY")
            if not api_key:
                logger.error("Groq API key not set")
                return False
            try:
                from groq import AsyncGroq
                self.client = AsyncGroq(api_key=api_key)
                logger.info("✅ Groq client initialized")
            except ImportError:
                # Groq uses OpenAI-compatible API
                from openai import AsyncOpenAI
                self.client = AsyncOpenAI(
                    api_key=api_key,
                    base_url="https://api.groq.com/openai/v1"
                )
                logger.info("✅ Groq client initialized (OpenAI compatible)")

        elif self.provider == "together":
            api_key = api_key or os.getenv("TOGETHER_API_KEY")
            if not api_key:
                logger.error("Together API key not set")
                return False
            from openai import AsyncOpenAI
            self.client = AsyncOpenAI(
                api_key=api_key,
                base_url="https://api.together.xyz/v1"
            )
            logger.info("✅ Together client initialized")

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
        if not self.client:
            if not await self.initialize():
                logger.error("Failed to initialize LLM client")
                return

        self.add_user_message(user_input)
        self.is_generating = True
        self.should_cancel = False
        full_response = ""
        current_sentence = ""

        try:
            logger.info(f"🤖 LLM generating ({self.provider}): \"{user_input[:50]}...\"")

            if self.provider in ["openai", "groq", "together"]:
                async for token in self._stream_openai_compatible(user_input):
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
                async for token in self._stream_anthropic(user_input):
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
                async for token in self._stream_google(user_input):
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

            if full_response and not self.should_cancel:
                self.add_assistant_message(full_response)
                logger.info(f"✅ LLM complete: \"{full_response[:100]}...\"")
                if self.on_complete:
                    await self.on_complete(full_response)

        except Exception as e:
            logger.error(f"LLM generation error: {e}")
        finally:
            self.is_generating = False

    async def _stream_openai_compatible(self, user_input: str) -> AsyncGenerator[str, None]:
        """Stream from OpenAI-compatible API"""
        stream = await self.client.chat.completions.create(
            model=self.config.llm_model,
            messages=self.context.get_messages_for_api(),
            temperature=self.config.llm_temperature,
            max_tokens=self.config.llm_max_tokens,
            stream=True
        )
        first_token = True
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                if first_token:
                    logger.info("⚡ LLM first token received")
                    first_token = False
                yield chunk.choices[0].delta.content

    async def _stream_anthropic(self, user_input: str) -> AsyncGenerator[str, None]:
        """Stream from Anthropic API"""
        messages = []
        for msg in self.context.messages:
            messages.append({"role": msg.role, "content": msg.content})

        async with self.client.messages.stream(
            model=self.config.llm_model,
            max_tokens=self.config.llm_max_tokens,
            system=self.context.system_prompt,
            messages=messages,
        ) as stream:
            first_token = True
            async for text in stream.text_stream:
                if first_token:
                    logger.info("⚡ LLM first token received")
                    first_token = False
                yield text

    async def _stream_google(self, user_input: str) -> AsyncGenerator[str, None]:
        """Stream from Google AI API"""
        # Build conversation history
        history = []
        for msg in self.context.messages[:-1]:  # Exclude last message
            role = "user" if msg.role == "user" else "model"
            history.append({"role": role, "parts": [msg.content]})

        chat = self.client.start_chat(history=history)

        # Add system prompt to first message if set
        prompt = user_input
        if self.context.system_prompt and not history:
            prompt = f"{self.context.system_prompt}\n\n{user_input}"

        response = await chat.send_message_async(prompt, stream=True)
        first_token = True
        async for chunk in response:
            if chunk.text:
                if first_token:
                    logger.info("⚡ LLM first token received")
                    first_token = False
                yield chunk.text

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
