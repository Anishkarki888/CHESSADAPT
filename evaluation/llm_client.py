"""
LLM API client adapters for ChessAdapt benchmark evaluation.

Provides a unified ``LLMClient`` interface with concrete adapters for:
  • OpenAI  (GPT-4o, GPT-4o-mini)
  • Anthropic  (Claude 3.7 Sonnet)
  • Google  (Gemini 2.5 Pro)
  • OpenRouter  (Llama 3 70B, Mistral Large — OpenAI-compatible)

All clients: ``generate(prompt, temperature) → str``
with retry, rate-limit handling, and structured logging.
"""

from __future__ import annotations

import abc
import logging
import os
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("chessadapt.llm_client")

# ── Model configuration registry ────────────────────────────────────────────

@dataclass(frozen=True)
class ModelConfig:
    """Immutable model configuration."""
    name: str               # human-readable name
    provider: str            # openai | anthropic | google | openrouter
    model_id: str            # API model identifier
    max_tokens: int = 256    # response token limit (moves are short)
    tier: str = "frontier"   # frontier | mid | weak (for gradient analysis)
    env_key: str = ""        # environment variable for API key


MODEL_CONFIGS: dict[str, ModelConfig] = {
    "gpt-4o": ModelConfig(
        name="GPT-4o",
        provider="openai",
        model_id="gpt-4o",
        tier="frontier",
        env_key="OPENAI_API_KEY",
    ),
    "gpt-4o-mini": ModelConfig(
        name="GPT-4o Mini",
        provider="openai",
        model_id="gpt-4o-mini",
        tier="mid",
        env_key="OPENAI_API_KEY",
    ),
    "claude-3.7-sonnet": ModelConfig(
        name="Claude 3.7 Sonnet",
        provider="anthropic",
        model_id="claude-sonnet-4-20250514",
        tier="frontier",
        env_key="ANTHROPIC_API_KEY",
    ),
    "gemini-2.5-pro": ModelConfig(
        name="Gemini 2.5 Pro",
        provider="google",
        model_id="gemini-2.5-pro-preview-05-06",
        tier="frontier",
        env_key="GOOGLE_API_KEY",
    ),
    "llama-3-70b": ModelConfig(
        name="Llama 3 70B",
        provider="openrouter",
        model_id="meta-llama/llama-3-70b-instruct",
        tier="mid",
        env_key="OPENROUTER_API_KEY",
    ),
    "mistral-large": ModelConfig(
        name="Mistral Large",
        provider="openrouter",
        model_id="mistralai/mistral-large-latest",
        tier="mid",
        env_key="OPENROUTER_API_KEY",
    ),
    "qwen-2.5-72b": ModelConfig(
        name="Qwen 2.5 72B",
        provider="openrouter",
        model_id="qwen/qwen-2.5-72b-instruct",
        tier="mid",
        env_key="OPENROUTER_API_KEY",
    ),
    "gpt-4o-or": ModelConfig(
        name="GPT-4o (OpenRouter)",
        provider="openrouter",
        model_id="openai/gpt-4o",
        tier="frontier",
        env_key="OPENROUTER_API_KEY",
    ),
    "claude-3.7-sonnet-or": ModelConfig(
        name="Claude 3.7 Sonnet (OpenRouter)",
        provider="openrouter",
        model_id="anthropic/claude-3.7-sonnet",
        tier="frontier",
        env_key="OPENROUTER_API_KEY",
    ),
}


# ── Retry helper ─────────────────────────────────────────────────────────────

def _retry_with_backoff(
    fn,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
) -> Any:
    """Call ``fn()`` with exponential backoff on transient errors."""
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except Exception as exc:
            err_str = str(exc).lower()
            is_transient = any(
                kw in err_str
                for kw in ["rate", "limit", "timeout", "overloaded", "529", "429", "500", "503"]
            )
            if not is_transient or attempt == max_retries:
                raise
            delay = min(base_delay * (2 ** attempt), max_delay)
            logger.warning(
                "Transient error (attempt %d/%d), retrying in %.1fs: %s",
                attempt + 1, max_retries, delay, exc,
            )
            time.sleep(delay)


# ── Abstract base ────────────────────────────────────────────────────────────

class LLMClient(abc.ABC):
    """Abstract LLM client interface."""

    def __init__(self, config: ModelConfig) -> None:
        self.config = config
        self._api_key = os.environ.get(config.env_key, "")
        if not self._api_key:
            logger.warning(
                "API key for %s not set (expected env var: %s)",
                config.name, config.env_key,
            )

    @abc.abstractmethod
    def _call_api(self, prompt: str, temperature: float) -> str:
        """Provider-specific API call. Returns raw text response."""

    def generate(self, prompt: str, temperature: float = 0.0) -> str:
        """
        Generate a response for the given prompt.

        Uses retry with exponential backoff for transient API errors.
        """
        logger.debug("Calling %s | temp=%.2f | prompt_len=%d", self.config.name, temperature, len(prompt))
        t0 = time.perf_counter()

        response = _retry_with_backoff(
            lambda: self._call_api(prompt, temperature)
        )

        elapsed = time.perf_counter() - t0
        logger.info(
            "%s responded in %.2fs | response_len=%d",
            self.config.name, elapsed, len(response),
        )
        return response

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(model={self.config.model_id!r})"


# ── OpenAI adapter ───────────────────────────────────────────────────────────

class OpenAIClient(LLMClient):
    """Adapter for OpenAI GPT models."""

    def __init__(self, config: ModelConfig) -> None:
        super().__init__(config)
        try:
            from openai import OpenAI
            self._client = OpenAI(api_key=self._api_key)
        except ImportError:
            raise ImportError("Install openai: pip install openai")

    def _call_api(self, prompt: str, temperature: float) -> str:
        response = self._client.chat.completions.create(
            model=self.config.model_id,
            messages=[
                {"role": "system", "content": "You are an expert chess analyst. Respond only with the requested move(s) in UCI format."},
                {"role": "user", "content": prompt},
            ],
            temperature=temperature,
            max_tokens=self.config.max_tokens,
        )
        return response.choices[0].message.content or ""


# ── Anthropic adapter ────────────────────────────────────────────────────────

class AnthropicClient(LLMClient):
    """Adapter for Anthropic Claude models."""

    def __init__(self, config: ModelConfig) -> None:
        super().__init__(config)
        try:
            import anthropic
            self._client = anthropic.Anthropic(api_key=self._api_key)
        except ImportError:
            raise ImportError("Install anthropic: pip install anthropic")

    def _call_api(self, prompt: str, temperature: float) -> str:
        response = self._client.messages.create(
            model=self.config.model_id,
            max_tokens=self.config.max_tokens,
            temperature=temperature,
            system="You are an expert chess analyst. Respond only with the requested move(s) in UCI format.",
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text if response.content else ""


# ── Google Gemini adapter ────────────────────────────────────────────────────

class GoogleClient(LLMClient):
    """Adapter for Google Gemini models."""

    def __init__(self, config: ModelConfig) -> None:
        super().__init__(config)
        try:
            from google import genai
            self._client = genai.Client(api_key=self._api_key)
        except ImportError:
            raise ImportError("Install google-genai: pip install google-genai")

    def _call_api(self, prompt: str, temperature: float) -> str:
        from google.genai import types

        response = self._client.models.generate_content(
            model=self.config.model_id,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=self.config.max_tokens,
                system_instruction="You are an expert chess analyst. Respond only with the requested move(s) in UCI format.",
            ),
        )
        return response.text or ""


# ── OpenRouter adapter (OpenAI-compatible) ───────────────────────────────────

class OpenRouterClient(LLMClient):
    """Adapter for OpenRouter (Llama 3, Mistral, etc.)."""

    OPENROUTER_BASE = "https://openrouter.ai/api/v1"

    def __init__(self, config: ModelConfig) -> None:
        super().__init__(config)
        try:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=self._api_key,
                base_url=self.OPENROUTER_BASE,
            )
        except ImportError:
            raise ImportError("Install openai: pip install openai")

    def _call_api(self, prompt: str, temperature: float) -> str:
        response = self._client.chat.completions.create(
            model=self.config.model_id,
            messages=[
                {"role": "system", "content": "You are an expert chess analyst. Respond only with the requested move(s) in UCI format."},
                {"role": "user", "content": prompt},
            ],
            temperature=temperature,
            max_tokens=self.config.max_tokens,
        )
        return response.choices[0].message.content or ""


# ── Factory ──────────────────────────────────────────────────────────────────

_PROVIDER_MAP = {
    "openai": OpenAIClient,
    "anthropic": AnthropicClient,
    "google": GoogleClient,
    "openrouter": OpenRouterClient,
}


def create_client(model_key: str) -> LLMClient:
    """
    Factory: create an LLM client from a model key.

    >>> client = create_client("gpt-4o")
    >>> response = client.generate("What is 2+2?")
    """
    if model_key not in MODEL_CONFIGS:
        available = ", ".join(sorted(MODEL_CONFIGS.keys()))
        raise ValueError(
            f"Unknown model: {model_key!r}. Available: {available}"
        )

    config = MODEL_CONFIGS[model_key]
    client_cls = _PROVIDER_MAP.get(config.provider)
    if client_cls is None:
        raise ValueError(f"Unknown provider: {config.provider!r}")

    return client_cls(config)
