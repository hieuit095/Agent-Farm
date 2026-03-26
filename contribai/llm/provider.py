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

from contribai.core.exceptions import LLMError, LLMRateLimitError

if TYPE_CHECKING:
    from contribai.core.config import LLMConfig

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
        for match in re.finditer(r"TOOL_CALL:\s*(\{.*?\})", text):
            try:
                data = json.loads(match.group(1))
                calls.append(ToolCallRequest(
                    tool_name=data.get("name", ""),
                    arguments=data.get("arguments", {}),
                ))
            except (json.JSONDecodeError, AttributeError):
                pass

        return calls

    async def close(self):  # noqa: B027
        """Clean up any resources."""


# ── Minimax ─────────────────────────────────────────────────────────────────────


class MinimaxProvider(LLMProvider):
    """Minimax provider (ABAB models) via direct REST API.

    Uses httpx to call the Minimax Chat Completion v2 endpoint.
    Auth: Bearer token via api_key. Optional group_id in header.
    """

    API_URL = "https://api.minimax.io/v1/text/chatcompletion_v2"

    def __init__(self, config: LLMConfig):
        super().__init__(config)
        import httpx

        headers = {
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        }
        if config.minimax_group_id:
            headers["X-Minimax-Group-Id"] = config.minimax_group_id

        self._chat_url = (config.base_url or self.API_URL).rstrip("/")
        self._client = httpx.AsyncClient(
            headers=headers,
            timeout=120.0,
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
        if getattr(self, "memory", None):
            import asyncio
            while not await self.memory.check_minimax_quota():
                logger.warning("Minimax quota exhausted. Pausing execution for 60s...")
                await asyncio.sleep(60)
            await self.memory.log_api_request("minimax")

        import httpx

        temp = temperature if temperature is not None else self.temperature
        max_tok = max_tokens if max_tokens is not None else self.max_tokens

        all_messages = list(messages)
        if system and not any(m["role"] == "system" for m in all_messages):
            all_messages.insert(0, {"role": "system", "content": system})

        payload = {
            "model": self.model,
            "messages": all_messages,
            "temperature": temp,
            "max_tokens": max_tok,
            "stream": False,
        }

        try:
            response = await self._client.post(self._chat_url, json=payload)
            response.raise_for_status()
            data = response.json()

            # Minimax v2 response: {"choices": [{"message": {"content": "..."}}]}
            choices = data.get("choices", [])
            if not choices:
                raise LLMError(f"Minimax returned empty choices: {data}")
            content = choices[0].get("message", {}).get("content", "")
            return _strip_reasoning_artifacts(content)

        except httpx.TimeoutException as e:
            raise LLMError(f"Minimax timeout: {e}") from e
        except httpx.HTTPStatusError as e:
            status = e.response.status_code
            if status == 429:
                raise LLMRateLimitError(f"Minimax rate limit (429): {e}") from e
            if status == 401:
                raise LLMError("Minimax auth failed (401): check api_key") from e
            raise LLMError(f"Minimax HTTP {status}: {e}") from e
        except (LLMError, LLMRateLimitError):
            raise
        except Exception as e:
            raise LLMError(f"Minimax error: {e}") from e

    async def close(self):
        await self._client.aclose()


# ── Factory ────────────────────────────────────────────────────────────────────


_PROVIDERS: dict[str, type[LLMProvider]] = {
    "minimax": MinimaxProvider,
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
