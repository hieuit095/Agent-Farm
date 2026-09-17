"""LLM Provider abstraction with multi-provider support.

Gemini is the primary/default provider. All providers implement
the same async interface for easy swapping.
"""

from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from farm_agent.core.exceptions import LLMError, LLMRateLimitError

if TYPE_CHECKING:
    from farm_agent.core.config import LLMConfig

logger = logging.getLogger(__name__)


def _strip_reasoning_artifacts(text: str) -> str:
    """Remove provider-emitted reasoning blocks from returned content."""
    if not text:
        return text

    cleaned = re.sub(
        r"<think>.*?</think>\s*",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    cleaned = re.sub(
        r"<thinking>.*?</thinking>\s*",
        "",
        cleaned,
        flags=re.DOTALL | re.IGNORECASE,
    )
    return cleaned.strip()


# ── Tool calling data models ──────────────────────────────────────────────────


@dataclass
class ToolCallRequest:
    """A tool call requested by the LLM."""

    tool_name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    call_id: str = ""


@dataclass
class LLMToolResponse:
    """Response from complete_with_tools — either text or a tool call."""

    text: str | None = None
    tool_calls: list[ToolCallRequest] = field(default_factory=list)

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)


# ── Abstract base ──────────────────────────────────────────────────────────────


class LLMProvider(ABC):
    """Abstract LLM provider interface."""

    def __init__(self, config: LLMConfig):
        self.config = config
        self.model = config.model
        self.temperature = config.temperature
        self.max_tokens = config.max_tokens

    @abstractmethod
    async def complete(
        self,
        prompt: str,
        *,
        system: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Single-turn completion."""

    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        system: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Multi-turn chat completion."""

    async def complete_with_tools(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        system: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> LLMToolResponse:
        """Completion with tool/function calling support.

        Default implementation: ignores tools and falls back to text
        completion only.  Providers that support native function calling
        (OpenAI, Gemini, Anthropic) can override this.

        The ``messages`` list follows the OpenAI message format::

            [
                {"role": "system", "content": "..."},
                {"role": "user",   "content": "..."},
                {"role": "assistant", "content": "...", "tool_calls": [...]},
                {"role": "tool", "tool_call_id": "...", "content": "..."},
            ]

        Returns an ``LLMToolResponse`` with either ``text`` or
        ``tool_calls`` populated.
        """
        # Flatten messages into a single prompt for the fallback path
        parts: list[str] = []
        for msg in messages:
            if msg["role"] == "tool":
                parts.append(f"[Tool Response]\n{msg.get('content', '')}")
            elif msg.get("content"):
                parts.append(msg["content"])

        prompt = "\n\n".join(parts)
        text = await self.complete(
            prompt,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        # Attempt to detect inline tool-call JSON in the text response
        # (for providers that don't support native function calling)
        tool_calls = self._parse_inline_tool_calls(text)
        if tool_calls:
            return LLMToolResponse(tool_calls=tool_calls)

        return LLMToolResponse(text=text)

    @staticmethod
    def _parse_inline_tool_calls(text: str) -> list[ToolCallRequest]:
        """Parse tool calls emitted inline as JSON by non-FC providers.

        Detects blocks like::

            ```tool_call
            {"name": "read_file", "arguments": {"filepath": "src/x.py"}}
            ```

        Also detects bare ``TOOL_CALL:`` prefixed JSON.
        """
        calls: list[ToolCallRequest] = []

        # Pattern 1: fenced tool_call block
        for match in re.finditer(
            r"```tool_call\s*\n(.*?)\n\s*```", text, re.DOTALL,
        ):
            try:
                data = json.loads(match.group(1).strip())
                calls.append(ToolCallRequest(
                    tool_name=data.get("name", ""),
                    arguments=data.get("arguments", {}),
                ))
            except (json.JSONDecodeError, AttributeError):
                pass

        # Pattern 2: TOOL_CALL: {...} on a single line
        # Use rfind to correctly handle nested JSON (non-greedy regex fails on nested braces)
        start_marker = text.rfind("TOOL_CALL: {")
        if start_marker != -1:
            start = text.find("{", start_marker)
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    data = json.loads(text[start:end+1])
                    calls.append(ToolCallRequest(
                        tool_name=data.get("name", ""),
                        arguments=data.get("arguments", {}),
                    ))
                except (json.JSONDecodeError, AttributeError):
                    pass

        return calls

    async def close(self):  # noqa: B027
        """Clean up any resources."""


# ── OpenRouter ──────────────────────────────────────────────────────────────────



class OpenRouterProvider(LLMProvider):
    """OpenRouter provider for Red Team (Bloodhound) audits.

    Uses the OpenRouter API (https://openrouter.ai/api/v1) which provides
    access to multiple models including free ones. Used exclusively for
    vulnerability validation to conserve Minimax quota.
    """

    API_URL = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(self, config: LLMConfig):
        super().__init__(config)

        import httpx

        headers = {
            "Authorization": f"Bearer {config.openrouter_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/farm-agent",
            "X-Title": "Farm-Agent Bloodhound",
        }

        self._model = config.model
        self._client = httpx.AsyncClient(
            headers=headers,
            timeout=300.0,
            follow_redirects=True,
        )

    async def complete(self, prompt: str, *, system: str | None = None, **kwargs) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return await self.chat(messages, **kwargs)

    async def chat(
        self,
        messages: list[dict[str, str]],
        *,
        system: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs,
    ) -> str:
        import httpx

        temp = temperature if temperature is not None else self.temperature
        max_tok = max_tokens if max_tokens is not None else self.max_tokens

        all_messages = list(messages)
        if system and not any(m["role"] == "system" for m in all_messages):
            all_messages.insert(0, {"role": "system", "content": system})

        payload = {
            "model": self._model,
            "messages": all_messages,
            "temperature": temp,
            "max_tokens": max_tok,
        }

        last_error: Exception | None = None
        for attempt in range(3):
            try:
                response = await self._client.post(self.API_URL, json=payload)
                response.raise_for_status()
                data = response.json()

                choices = data.get("choices", [])
                if not choices:
                    last_error = LLMError(f"OpenRouter returned empty choices (attempt {attempt + 1}/3)")
                    if attempt < 2:
                        import asyncio as _asyncio
                        await _asyncio.sleep(5 * (attempt + 1))
                        continue
                    raise last_error

                content = choices[0].get("message", {}).get("content", "")
                return _strip_reasoning_artifacts(content)

            except httpx.TimeoutException as e:
                last_error = LLMError(f"OpenRouter timeout (attempt {attempt + 1}/3): {e}")
                if attempt < 2:
                    import asyncio as _asyncio
                    await _asyncio.sleep(5 * (attempt + 1))
                    continue
                raise last_error from e
            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                # ── Exponential backoff for rate limits and server overload ──
                # 429 (Rate Limit), 529 (Overloaded), 402 (Payment Required),
                # and 403 (Forbidden/Quota) trigger retries with backoff.
                if status == 401:
                    raise LLMError("OpenRouter auth failed (401): check openrouter_api_key") from e
                if status in (429, 529, 402, 403):
                    backoff = min(5 * (2 ** attempt), 60)
                    logger.warning(
                        "OpenRouter HTTP %d (attempt %d/3) — backing off %.1fs before retry: %s",
                        status, attempt + 1, backoff, e,
                    )
                    import asyncio as _asyncio
                    await _asyncio.sleep(backoff)
                    last_error = LLMRateLimitError(
                        f"OpenRouter HTTP {status} (attempt {attempt+1}/3): {e}"
                    )
                    if attempt < 2:
                        continue
                    raise last_error from e
                if status >= 500:
                    backoff = min(5 * (2 ** attempt), 60)
                    logger.warning(
                        "OpenRouter server error %d (attempt %d/3) — backing off %.1fs: %s",
                        status, attempt + 1, backoff, e,
                    )
                    import asyncio as _asyncio
                    await _asyncio.sleep(backoff)
                    last_error = LLMRateLimitError(
                        f"OpenRouter server error {status} (attempt {attempt+1}/3): {e}"
                    )
                    if attempt < 2:
                        continue
                    raise last_error from e
                raise LLMError(f"OpenRouter HTTP {status}: {e}") from e
            except (LLMError, LLMRateLimitError):
                raise
            except Exception as e:
                raise LLMError(f"OpenRouter error: {e}") from e

        raise last_error or LLMError("OpenRouter: all retries exhausted")

    async def close(self):
        if hasattr(self, "_client") and self._client is not None:
            import inspect

            aclose = getattr(self._client, "aclose", None)
            if callable(aclose):
                ret = aclose()
                if inspect.isawaitable(ret):
                    await ret


# ── Factory ────────────────────────────────────────────────────────────────────


_PROVIDERS: dict[str, type[LLMProvider]] = {
    "openrouter": OpenRouterProvider,
}


def create_llm_provider(
    config: LLMConfig,
    multi_model: bool = False,
    strategy: str = "balanced",
) -> LLMProvider:
    """Create an LLM provider instance from config."""
    provider_cls = _PROVIDERS.get(config.provider)
    if not provider_cls:
        raise LLMError(
            f"Unknown LLM provider: {config.provider}. Available: {', '.join(_PROVIDERS.keys())}"
        )

    logger.info(
        "Using LLM provider: %s (model: %s)",
        config.provider,
        config.model,
    )
    return provider_cls(config)
