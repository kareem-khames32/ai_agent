"""
LLM Streaming Response
Generates AI responses with streaming tokens
"""
import os
import asyncio
from typing import Optional, Callable, Awaitable, AsyncGenerator, List
from dataclasses import dataclass, field
from openai import AsyncOpenAI

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

        # Keep only last N turns (user + assistant pairs)
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

    Features:
    - Streaming token generation
    - Sentence-level chunking for TTS
    - Conversation context management
    - Cancellation support for barge-in
    """

    def __init__(self, config: VoiceAgentConfig):
        self.config = config
        self.client: Optional[AsyncOpenAI] = None
        self.context = LLMContext(max_turns=config.llm_context_turns)

        # State
        self.is_generating = False
        self.should_cancel = False

        # Callbacks
        self.on_token: Optional[Callable[[str], Awaitable[None]]] = None
        self.on_sentence: Optional[Callable[[str], Awaitable[None]]] = None
        self.on_complete: Optional[Callable[[str], Awaitable[None]]] = None

        logger.info(f"LLMStreamer initialized (model={config.llm_model})")

    async def initialize(self):
        """Initialize OpenAI client"""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.error("OPENAI_API_KEY not set")
            return False

        self.client = AsyncOpenAI(api_key=api_key)
        logger.info("✅ OpenAI client initialized")
        return True

    def set_system_prompt(self, prompt: str):
        """Set the system prompt"""
        self.context.system_prompt = prompt
        logger.debug(f"System prompt set ({len(prompt)} chars)")

    def add_user_message(self, content: str):
        """Add user message to context"""
        self.context.add_message("user", content)
        logger.debug(f"User message added: \"{content[:50]}...\"")

    def add_assistant_message(self, content: str):
        """Add assistant message to context"""
        self.context.add_message("assistant", content)
        logger.debug(f"Assistant message added: \"{content[:50]}...\"")

    async def generate_stream(self, user_input: str) -> AsyncGenerator[str, None]:
        """
        Generate streaming response

        Args:
            user_input: User's message

        Yields:
            Tokens as they arrive
        """
        if not self.client:
            await self.initialize()
            if not self.client:
                logger.error("Failed to initialize OpenAI client")
                return

        # Add user message
        self.add_user_message(user_input)

        self.is_generating = True
        self.should_cancel = False
        full_response = ""
        current_sentence = ""

        try:
            logger.info(f"🤖 LLM generating response for: \"{user_input[:50]}...\"")

            stream = await self.client.chat.completions.create(
                model=self.config.llm_model,
                messages=self.context.get_messages_for_api(),
                temperature=self.config.llm_temperature,
                max_tokens=self.config.llm_max_tokens,
                stream=True
            )

            first_token = True
            async for chunk in stream:
                if self.should_cancel:
                    logger.info("🛑 LLM generation cancelled")
                    break

                if chunk.choices and chunk.choices[0].delta.content:
                    token = chunk.choices[0].delta.content
                    full_response += token
                    current_sentence += token

                    if first_token:
                        logger.info(f"⚡ LLM first token received")
                        first_token = False

                    # Invoke token callback
                    if self.on_token:
                        await self.on_token(token)

                    # Check for sentence boundary
                    if self._is_sentence_end(current_sentence):
                        sentence = current_sentence.strip()
                        if sentence:
                            logger.debug(f"📝 Sentence: \"{sentence}\"")
                            if self.on_sentence:
                                await self.on_sentence(sentence)
                        current_sentence = ""

                    yield token

            # Handle remaining text
            if current_sentence.strip() and not self.should_cancel:
                if self.on_sentence:
                    await self.on_sentence(current_sentence.strip())

            # Add assistant response to context
            if full_response and not self.should_cancel:
                self.add_assistant_message(full_response)
                logger.info(f"✅ LLM complete: \"{full_response[:100]}...\"")

                if self.on_complete:
                    await self.on_complete(full_response)

        except Exception as e:
            logger.error(f"LLM generation error: {e}")
        finally:
            self.is_generating = False

    async def generate(self, user_input: str) -> str:
        """
        Generate complete response (non-streaming)

        Args:
            user_input: User's message

        Returns:
            Complete response text
        """
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

        # Sentence ending punctuation (Arabic and English)
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
