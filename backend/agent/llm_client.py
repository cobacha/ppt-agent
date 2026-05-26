"""
Unified LLM client — supports Anthropic (default) and OpenAI-compatible providers.

Configuration via environment variables:
  LLM_PROVIDER=anthropic (default) | openai

  For Anthropic:
    ANTHROPIC_API_KEY, MODEL_ID, ANTHROPIC_BASE_URL (optional)

  For OpenAI-compatible (GPT-4o, DeepSeek, Ollama, vLLM, etc.):
    OPENAI_API_KEY, OPENAI_BASE_URL (optional), OPENAI_MODEL (default: gpt-4o)
"""

import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Generator


@dataclass
class LLMResponse:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0


class LLMClient(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def chat_completion(
        self,
        system: str | list[dict],
        messages: list[dict],
        max_tokens: int = 8192,
        temperature: float = 0,
        timeout: float = 60.0,
        stream: bool = False,
    ) -> LLMResponse:
        """Send a chat completion request and return the response."""
        ...

    @abstractmethod
    def stream_completion(
        self,
        system: str | list[dict],
        messages: list[dict],
        max_tokens: int = 8192,
        temperature: float = 0,
        timeout: float = 60.0,
    ) -> Generator[str, None, None]:
        """Stream text chunks from a chat completion."""
        ...


class AnthropicClient(LLMClient):
    """Anthropic API client wrapping the existing call_with_retry logic."""

    def __init__(self):
        from anthropic import Anthropic
        self._client = Anthropic()
        self.model = os.environ.get("MODEL_ID", "claude-sonnet-4-6")

    def chat_completion(
        self,
        system: str | list[dict],
        messages: list[dict],
        max_tokens: int = 8192,
        temperature: float = 0,
        timeout: float = 60.0,
        stream: bool = False,
    ) -> LLMResponse:
        from anthropic import (
            APITimeoutError,
            APIConnectionError,
            RateLimitError,
            InternalServerError,
        )
        transient = (APITimeoutError, APIConnectionError, RateLimitError, InternalServerError)

        kwargs = dict(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=timeout,
            system=system,
            messages=messages,
        )

        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                response = self._client.messages.create(**kwargs)
                break
            except transient:
                if attempt == max_retries:
                    raise
                time.sleep(2 ** attempt)

        text = self._extract_text(response)
        return LLMResponse(
            text=text,
            input_tokens=getattr(response.usage, "input_tokens", 0),
            output_tokens=getattr(response.usage, "output_tokens", 0),
        )

    def stream_completion(
        self,
        system: str | list[dict],
        messages: list[dict],
        max_tokens: int = 8192,
        temperature: float = 0,
        timeout: float = 60.0,
    ) -> Generator[str, None, None]:
        with self._client.messages.stream(
            model=self.model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                yield text

    @staticmethod
    def _extract_text(response) -> str:
        """Extract text from Anthropic response, skipping ThinkingBlocks."""
        for block in response.content:
            if hasattr(block, "text"):
                return block.text
        return ""


class OpenAIClient(LLMClient):
    """OpenAI-compatible API client (GPT-4o, DeepSeek, Ollama, vLLM, etc.)."""

    def __init__(self):
        # Lazy import — only needed when LLM_PROVIDER=openai
        try:
            import openai
        except ImportError:
            raise ImportError(
                "The 'openai' package is required when LLM_PROVIDER=openai. "
                "Install it with: pip install openai>=1.40.0"
            )

        self.model = os.environ.get("OPENAI_MODEL", "gpt-4o")
        kwargs = {"api_key": os.environ.get("OPENAI_API_KEY", "")}
        base_url = os.environ.get("OPENAI_BASE_URL")
        if base_url:
            kwargs["base_url"] = base_url

        self._client = openai.OpenAI(**kwargs)

    def chat_completion(
        self,
        system: str | list[dict],
        messages: list[dict],
        max_tokens: int = 8192,
        temperature: float = 0,
        timeout: float = 60.0,
        stream: bool = False,
    ) -> LLMResponse:
        import openai

        transient = (
            openai.APITimeoutError,
            openai.APIConnectionError,
            openai.RateLimitError,
            openai.InternalServerError,
        )

        oai_messages = self._build_messages(system, messages)

        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                response = self._client.chat.completions.create(
                    model=self.model,
                    messages=oai_messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    timeout=timeout,
                )
                break
            except transient:
                if attempt == max_retries:
                    raise
                time.sleep(2 ** attempt)

        text = response.choices[0].message.content or ""
        usage = response.usage
        return LLMResponse(
            text=text,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
        )

    def stream_completion(
        self,
        system: str | list[dict],
        messages: list[dict],
        max_tokens: int = 8192,
        temperature: float = 0,
        timeout: float = 60.0,
    ) -> Generator[str, None, None]:
        oai_messages = self._build_messages(system, messages)

        stream = self._client.chat.completions.create(
            model=self.model,
            messages=oai_messages,
            max_tokens=max_tokens,
            temperature=temperature,
            timeout=timeout,
            stream=True,
        )

        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    @staticmethod
    def _build_messages(system: str | list[dict], messages: list[dict]) -> list[dict]:
        """Convert Anthropic-style system/messages to OpenAI format."""
        oai_messages = []

        # Handle system prompt
        if isinstance(system, str):
            system_text = system
        elif isinstance(system, list):
            # Structured system (e.g. [{"type": "text", "text": "...", "cache_control": ...}])
            # Extract text content, ignore cache_control (not supported by OpenAI)
            parts = []
            for block in system:
                if isinstance(block, dict) and "text" in block:
                    parts.append(block["text"])
                elif isinstance(block, str):
                    parts.append(block)
            system_text = "\n".join(parts)
        else:
            system_text = str(system)

        if system_text:
            oai_messages.append({"role": "system", "content": system_text})

        # Convert messages
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            oai_messages.append({"role": role, "content": content})

        return oai_messages


def create_llm_client() -> LLMClient:
    """Factory: create the configured LLM client based on LLM_PROVIDER env var."""
    provider = os.environ.get("LLM_PROVIDER", "anthropic").lower()
    if provider == "openai":
        return OpenAIClient()
    return AnthropicClient()
