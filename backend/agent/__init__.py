"""
LLM Client Configuration
-------------------------
This project supports multiple LLM providers via the unified client in llm_client.py.

Set the LLM_PROVIDER environment variable to switch providers:
  - "anthropic" (default): Uses Anthropic API. Set ANTHROPIC_API_KEY, MODEL_ID.
  - "openai": Uses any OpenAI-compatible API (GPT-4o, DeepSeek, Ollama, vLLM).
              Set OPENAI_API_KEY, OPENAI_BASE_URL (optional), OPENAI_MODEL.

For Anthropic proxies, you can also set ANTHROPIC_BASE_URL to route requests.
"""

import time

from .llm_client import create_llm_client, LLMClient, LLMResponse  # noqa: F401

# --- Backward compatibility: keep call_with_retry / extract_text available ---
# These are deprecated; new code should use the LLMClient interface directly.

from anthropic import (
    Anthropic,
    APITimeoutError,
    APIConnectionError,
    RateLimitError,
    InternalServerError,
)

_TRANSIENT_ERRORS = (APITimeoutError, APIConnectionError, RateLimitError, InternalServerError)


def call_with_retry(client: Anthropic, max_retries: int = 2, **kwargs):
    """DEPRECATED: Use LLMClient.chat_completion() instead.
    Call client.messages.create with exponential backoff on transient errors."""
    for attempt in range(max_retries + 1):
        try:
            return client.messages.create(**kwargs)
        except _TRANSIENT_ERRORS:
            if attempt == max_retries:
                raise
            time.sleep(2 ** attempt)


def extract_text(response) -> str:
    """DEPRECATED: Use LLMResponse.text instead.
    Extract text from Anthropic response, skipping ThinkingBlocks."""
    for block in response.content:
        if hasattr(block, "text"):
            return block.text
    return ""
