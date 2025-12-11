"""
LLM Service
Supports: Anthropic Claude, OpenAI GPT, Google Gemini, Groq, Together AI
With connection pooling for low latency and retry logic for rate limiting
"""
import asyncio
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any, AsyncGenerator
from dataclasses import dataclass
import httpx
from loguru import logger


# Retry configuration
MAX_RETRIES = 3
RETRY_DELAYS = [1, 2, 4]  # Exponential backoff: 1s, 2s, 4s


# Shared HTTP client pool for connection reuse (reduces latency significantly)
_http_clients: Dict[str, httpx.AsyncClient] = {}


def get_http_client(base_url: str) -> httpx.AsyncClient:
    """Get or create a persistent HTTP client for a base URL"""
    if base_url not in _http_clients:
        _http_clients[base_url] = httpx.AsyncClient(
            timeout=60.0,
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
            # Note: http2=True requires 'h2' package (pip install httpx[http2])
        )
    return _http_clients[base_url]


async def close_all_clients():
    """Close all HTTP clients (call on shutdown)"""
    for client in _http_clients.values():
        await client.aclose()
    _http_clients.clear()


async def retry_on_rate_limit(func, *args, **kwargs):
    """Retry a function on rate limit (429) errors with exponential backoff"""
    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            return await func(*args, **kwargs)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_DELAYS[attempt]
                    logger.warning(f"⚠️ Rate limited (429), retrying in {delay}s... (attempt {attempt + 1}/{MAX_RETRIES})")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"❌ Rate limit exceeded after {MAX_RETRIES} retries")
            else:
                raise
    raise last_error


@dataclass
class Message:
    """Chat message"""
    role: str  # "system", "user", "assistant"
    content: str


@dataclass
class LLMResponse:
    """Response from LLM"""
    text: str
    finish_reason: Optional[str] = None
    usage: Optional[Dict[str, int]] = None


class LLMService:
    """LLM service with multiple provider support and connection pooling"""

    def __init__(
        self,
        provider: str = "anthropic",
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.provider = provider
        self.api_key = api_key
        self.model = model or self._default_model()

    def _default_model(self) -> str:
        """Get default model for provider"""
        defaults = {
            "anthropic": "claude-sonnet-4-20250514",
            "openai": "gpt-4o-mini",
            "google": "gemini-1.5-flash",
            "groq": "llama-3.3-70b-versatile",
            "together": "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        }
        return defaults.get(self.provider, "claude-sonnet-4-20250514")

    async def generate(
        self,
        messages: List[Message],
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Generate a response from the LLM"""
        if self.provider == "anthropic":
            return await self._anthropic_generate(messages, system_prompt, max_tokens, temperature)
        elif self.provider == "openai":
            return await self._openai_generate(messages, system_prompt, max_tokens, temperature)
        elif self.provider == "google":
            return await self._google_generate(messages, system_prompt, max_tokens, temperature)
        elif self.provider == "groq":
            return await self._groq_generate(messages, system_prompt, max_tokens, temperature)
        elif self.provider == "together":
            return await self._together_generate(messages, system_prompt, max_tokens, temperature)
        else:
            raise ValueError(f"Unknown LLM provider: {self.provider}")

    async def generate_stream(
        self,
        messages: List[Message],
        system_prompt: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> AsyncGenerator[str, None]:
        """Stream response from the LLM"""
        try:
            if self.provider == "anthropic":
                async for chunk in self._anthropic_stream(messages, system_prompt, max_tokens, temperature):
                    yield chunk
            elif self.provider == "openai":
                async for chunk in self._openai_stream(messages, system_prompt, max_tokens, temperature):
                    yield chunk
            elif self.provider == "google":
                async for chunk in self._google_stream(messages, system_prompt, max_tokens, temperature):
                    yield chunk
            elif self.provider == "groq":
                async for chunk in self._groq_stream(messages, system_prompt, max_tokens, temperature):
                    yield chunk
            elif self.provider == "together":
                async for chunk in self._together_stream(messages, system_prompt, max_tokens, temperature):
                    yield chunk
            else:
                raise ValueError(f"Unknown LLM provider: {self.provider}")
        except GeneratorExit:
            logger.debug("generate_stream: closed by caller")
            return

    async def _anthropic_generate(
        self,
        messages: List[Message],
        system_prompt: Optional[str],
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        """Generate using Anthropic Claude"""
        url = "https://api.anthropic.com/v1/messages"

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

        # Convert messages to Anthropic format
        anthropic_messages = []
        for msg in messages:
            if msg.role != "system":
                anthropic_messages.append({
                    "role": msg.role,
                    "content": msg.content,
                })

        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": anthropic_messages,
        }

        if system_prompt:
            payload["system"] = system_prompt

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers=headers,
                json=payload,
                timeout=60.0,
            )
            if response.status_code != 200:
                logger.error(f"❌ Anthropic API error: {response.status_code} - {response.text}")
            response.raise_for_status()
            result = response.json()

        return LLMResponse(
            text=result["content"][0]["text"],
            finish_reason=result.get("stop_reason"),
            usage={
                "input_tokens": result.get("usage", {}).get("input_tokens", 0),
                "output_tokens": result.get("usage", {}).get("output_tokens", 0),
            },
        )

    async def _anthropic_stream(
        self,
        messages: List[Message],
        system_prompt: Optional[str],
        max_tokens: int,
        temperature: float,
    ) -> AsyncGenerator[str, None]:
        """Stream using Anthropic Claude"""
        url = "https://api.anthropic.com/v1/messages"

        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

        anthropic_messages = []
        for msg in messages:
            if msg.role != "system":
                anthropic_messages.append({
                    "role": msg.role,
                    "content": msg.content,
                })

        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": anthropic_messages,
            "stream": True,
        }

        if system_prompt:
            payload["system"] = system_prompt

        logger.info(f"📤 Anthropic stream: model={self.model}, messages={len(anthropic_messages)}")
        if not anthropic_messages:
            logger.error("❌ No messages to send to Anthropic!")

        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST",
                url,
                headers=headers,
                json=payload,
            ) as response:
                if response.status_code != 200:
                    error_text = await response.aread()
                    logger.error(f"❌ Anthropic API error: {response.status_code} - {error_text.decode()}")
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        try:
                            import json
                            data = json.loads(line[6:])
                            if data["type"] == "content_block_delta":
                                yield data["delta"].get("text", "")
                        except:
                            continue

    async def _openai_generate(
        self,
        messages: List[Message],
        system_prompt: Optional[str],
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        """Generate using OpenAI GPT"""
        url = "https://api.openai.com/v1/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # Convert messages to OpenAI format
        openai_messages = []
        if system_prompt:
            openai_messages.append({"role": "system", "content": system_prompt})
        for msg in messages:
            openai_messages.append({
                "role": msg.role,
                "content": msg.content,
            })

        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": openai_messages,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers=headers,
                json=payload,
                timeout=60.0,
            )
            response.raise_for_status()
            result = response.json()

        choice = result["choices"][0]
        return LLMResponse(
            text=choice["message"]["content"],
            finish_reason=choice.get("finish_reason"),
            usage=result.get("usage"),
        )

    async def _openai_stream(
        self,
        messages: List[Message],
        system_prompt: Optional[str],
        max_tokens: int,
        temperature: float,
    ) -> AsyncGenerator[str, None]:
        """Stream using OpenAI GPT"""
        url = "https://api.openai.com/v1/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        openai_messages = []
        if system_prompt:
            openai_messages.append({"role": "system", "content": system_prompt})
        for msg in messages:
            openai_messages.append({
                "role": msg.role,
                "content": msg.content,
            })

        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": openai_messages,
            "stream": True,
        }

        # Use async with for automatic cleanup - no finally block needed
        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST",
                url,
                headers=headers,
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: ") and line != "data: [DONE]":
                        try:
                            import json
                            data = json.loads(line[6:])
                            delta = data["choices"][0].get("delta", {})
                            if "content" in delta:
                                yield delta["content"]
                        except:
                            continue

    async def _google_generate(
        self,
        messages: List[Message],
        system_prompt: Optional[str],
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        """Generate using Google Gemini with retry on rate limit"""
        return await self._google_generate_with_retry(messages, system_prompt, max_tokens, temperature)

    async def _google_generate_with_retry(
        self,
        messages: List[Message],
        system_prompt: Optional[str],
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        """Generate using Google Gemini with retry logic"""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"

        headers = {
            "Content-Type": "application/json",
        }

        params = {
            "key": self.api_key,
        }

        # Convert messages to Gemini format
        contents = []
        for msg in messages:
            role = "user" if msg.role == "user" else "model"
            contents.append({
                "role": role,
                "parts": [{"text": msg.content}],
            })

        payload = {
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": temperature,
            },
        }

        if system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}

        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        url,
                        headers=headers,
                        params=params,
                        json=payload,
                        timeout=60.0,
                    )
                    response.raise_for_status()
                    result = response.json()
                    break
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    last_error = e
                    if attempt < MAX_RETRIES - 1:
                        delay = RETRY_DELAYS[attempt]
                        logger.warning(f"⚠️ Gemini rate limited, retrying in {delay}s... ({attempt + 1}/{MAX_RETRIES})")
                        await asyncio.sleep(delay)
                    else:
                        logger.error(f"❌ Gemini rate limit exceeded after {MAX_RETRIES} retries")
                        raise
                else:
                    raise
        else:
            raise last_error

        candidate = result["candidates"][0]
        return LLMResponse(
            text=candidate["content"]["parts"][0]["text"],
            finish_reason=candidate.get("finishReason"),
            usage=result.get("usageMetadata"),
        )

    async def _google_stream(
        self,
        messages: List[Message],
        system_prompt: Optional[str],
        max_tokens: int,
        temperature: float,
    ) -> AsyncGenerator[str, None]:
        """Stream using Google Gemini with retry on rate limit"""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:streamGenerateContent"

        headers = {
            "Content-Type": "application/json",
        }

        params = {
            "key": self.api_key,
            "alt": "sse",
        }

        contents = []
        for msg in messages:
            role = "user" if msg.role == "user" else "model"
            contents.append({
                "role": role,
                "parts": [{"text": msg.content}],
            })

        payload = {
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": temperature,
            },
        }

        if system_prompt:
            payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}

        # Retry loop for rate limiting
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    async with client.stream(
                        "POST",
                        url,
                        headers=headers,
                        params=params,
                        json=payload,
                    ) as response:
                        response.raise_for_status()
                        async for line in response.aiter_lines():
                            if line.startswith("data: "):
                                try:
                                    import json
                                    data = json.loads(line[6:])
                                    if "candidates" in data:
                                        parts = data["candidates"][0].get("content", {}).get("parts", [])
                                        for part in parts:
                                            if "text" in part:
                                                yield part["text"]
                                except:
                                    continue
                        return  # Success, exit retry loop
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:
                    last_error = e
                    if attempt < MAX_RETRIES - 1:
                        delay = RETRY_DELAYS[attempt]
                        logger.warning(f"⚠️ Gemini stream rate limited, retrying in {delay}s... ({attempt + 1}/{MAX_RETRIES})")
                        await asyncio.sleep(delay)
                    else:
                        logger.error(f"❌ Gemini stream rate limit exceeded after {MAX_RETRIES} retries")
                        raise
                else:
                    raise

    # ============== Groq (OpenAI-compatible) ==============

    async def _groq_generate(
        self,
        messages: List[Message],
        system_prompt: Optional[str],
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        """Generate using Groq (OpenAI-compatible API)"""
        url = "https://api.groq.com/openai/v1/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # Convert messages to OpenAI format
        openai_messages = []
        if system_prompt:
            openai_messages.append({"role": "system", "content": system_prompt})
        for msg in messages:
            openai_messages.append({
                "role": msg.role,
                "content": msg.content,
            })

        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": openai_messages,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers=headers,
                json=payload,
                timeout=60.0,
            )
            response.raise_for_status()
            result = response.json()

        choice = result["choices"][0]
        return LLMResponse(
            text=choice["message"]["content"],
            finish_reason=choice.get("finish_reason"),
            usage=result.get("usage"),
        )

    async def _groq_stream(
        self,
        messages: List[Message],
        system_prompt: Optional[str],
        max_tokens: int,
        temperature: float,
    ) -> AsyncGenerator[str, None]:
        """Stream using Groq"""
        url = "https://api.groq.com/openai/v1/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        openai_messages = []
        if system_prompt:
            openai_messages.append({"role": "system", "content": system_prompt})
        for msg in messages:
            openai_messages.append({
                "role": msg.role,
                "content": msg.content,
            })

        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": openai_messages,
            "stream": True,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST",
                url,
                headers=headers,
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: ") and line != "data: [DONE]":
                        try:
                            import json
                            data = json.loads(line[6:])
                            delta = data["choices"][0].get("delta", {})
                            if "content" in delta:
                                yield delta["content"]
                        except:
                            continue

    # ============== Together AI (OpenAI-compatible) ==============

    async def _together_generate(
        self,
        messages: List[Message],
        system_prompt: Optional[str],
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        """Generate using Together AI (OpenAI-compatible API)"""
        url = "https://api.together.xyz/v1/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # Convert messages to OpenAI format
        openai_messages = []
        if system_prompt:
            openai_messages.append({"role": "system", "content": system_prompt})
        for msg in messages:
            openai_messages.append({
                "role": msg.role,
                "content": msg.content,
            })

        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": openai_messages,
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers=headers,
                json=payload,
                timeout=60.0,
            )
            response.raise_for_status()
            result = response.json()

        choice = result["choices"][0]
        return LLMResponse(
            text=choice["message"]["content"],
            finish_reason=choice.get("finish_reason"),
            usage=result.get("usage"),
        )

    async def _together_stream(
        self,
        messages: List[Message],
        system_prompt: Optional[str],
        max_tokens: int,
        temperature: float,
    ) -> AsyncGenerator[str, None]:
        """Stream using Together AI"""
        url = "https://api.together.xyz/v1/chat/completions"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        openai_messages = []
        if system_prompt:
            openai_messages.append({"role": "system", "content": system_prompt})
        for msg in messages:
            openai_messages.append({
                "role": msg.role,
                "content": msg.content,
            })

        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": openai_messages,
            "stream": True,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            async with client.stream(
                "POST",
                url,
                headers=headers,
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: ") and line != "data: [DONE]":
                        try:
                            import json
                            data = json.loads(line[6:])
                            delta = data["choices"][0].get("delta", {})
                            if "content" in delta:
                                yield delta["content"]
                        except:
                            continue
