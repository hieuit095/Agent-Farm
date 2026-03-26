"""Unit tests for MinimaxProvider using respx to intercept httpx calls."""

from __future__ import annotations

import httpx
import pytest
import respx

from contribai.core.config import LLMConfig
from contribai.core.exceptions import LLMError, LLMRateLimitError
from contribai.llm.provider import MinimaxProvider, create_llm_provider

# Minimax API URL used by the provider
_MINIMAX_URL = "https://api.minimax.io/v1/text/chatcompletion_v2"


# ── Helper ────────────────────────────────────────────────────────────────────


def _make_config(**overrides) -> LLMConfig:
    """Create a minimal LLMConfig for Minimax tests."""
    defaults = {
        "provider": "minimax",
        "model": "MiniMax-M2.7",
        "api_key": "test-minimax-key-123",
        "base_url": "https://api.minimax.io/v1/text/chatcompletion_v2",
    }
    defaults.update(overrides)
    return LLMConfig(**defaults)


def _success_response(content: str = "Hello from Minimax!") -> httpx.Response:
    """Build a mock successful Minimax API response."""
    return httpx.Response(
        200,
        json={
            "id": "chat-001",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": content},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        },
    )


# ── Tests ─────────────────────────────────────────────────────────────────────


class TestMinimaxProviderInit:
    """Test MinimaxProvider initialization and factory wiring."""

    def test_factory_creates_minimax_provider(self):
        """create_llm_provider returns MinimaxProvider for minimax config."""
        config = _make_config()
        provider = create_llm_provider(config)
        assert isinstance(provider, MinimaxProvider)
        assert provider.model == "MiniMax-M2.7"

    def test_default_model_set_by_config(self):
        """LLMConfig auto-sets MiniMax-M2.7 when provider is minimax."""
        config = LLMConfig(provider="minimax", api_key="test-key")
        assert config.model == "MiniMax-M2.7"

    def test_group_id_in_headers(self):
        """minimax_group_id is included in client headers when set."""
        config = _make_config(minimax_group_id="grp-456")
        provider = MinimaxProvider(config)
        assert provider._client.headers["X-Minimax-Group-Id"] == "grp-456"

    def test_auth_header_set(self):
        """Bearer token is set in Authorization header."""
        config = _make_config()
        provider = MinimaxProvider(config)
        assert "Bearer test-minimax-key-123" in provider._client.headers["Authorization"]


class TestMinimaxComplete:
    """Test MinimaxProvider.complete() with mocked HTTP responses."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_complete_success(self):
        """Successful completion extracts content from choices[0].message.content."""
        respx.post(_MINIMAX_URL).mock(return_value=_success_response())

        config = _make_config()
        provider = MinimaxProvider(config)
        result = await provider.complete("Say hello")

        assert result == "Hello from Minimax!"
        await provider.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_complete_with_system_prompt(self):
        """System prompt is included in the messages payload."""
        route = respx.post(_MINIMAX_URL).mock(
            return_value=_success_response("I am a Python expert.")
        )

        config = _make_config()
        provider = MinimaxProvider(config)
        result = await provider.complete("What are you?", system="You are a Python expert.")

        assert result == "I am a Python expert."

        # Verify the payload included system message
        request = route.calls[0].request
        import json

        body = json.loads(request.content)
        roles = [m["role"] for m in body["messages"]]
        assert "system" in roles
        assert "user" in roles
        await provider.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_complete_strips_think_tags(self):
        """Provider should strip raw reasoning blocks from visible output."""
        respx.post(_MINIMAX_URL).mock(
            return_value=_success_response("<think>internal chain</think>\n\nOK")
        )

        config = _make_config()
        provider = MinimaxProvider(config)
        result = await provider.complete("Reply with OK")

        assert result == "OK"
        await provider.close()


class TestMinimaxChat:
    """Test MinimaxProvider.chat() with mocked HTTP responses."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_chat_multi_turn(self):
        """Multi-turn chat passes all messages and extracts response."""
        respx.post(_MINIMAX_URL).mock(return_value=_success_response("The answer is 42."))

        config = _make_config()
        provider = MinimaxProvider(config)
        result = await provider.chat(
            [
                {"role": "user", "content": "What is the meaning of life?"},
                {"role": "assistant", "content": "Let me think..."},
                {"role": "user", "content": "Please tell me."},
            ]
        )

        assert result == "The answer is 42."
        await provider.close()


class TestMinimaxErrorHandling:
    """Test MinimaxProvider error handling."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_rate_limit_raises_llm_rate_limit_error(self):
        """HTTP 429 raises LLMRateLimitError (caught by RetryMiddleware)."""
        from unittest.mock import AsyncMock, patch

        respx.post(_MINIMAX_URL).mock(
            return_value=httpx.Response(
                429, json={"error": {"message": "Rate limit exceeded"}}
            )
        )

        config = _make_config()
        provider = MinimaxProvider(config)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(LLMRateLimitError, match="429"):
                await provider.chat([{"role": "user", "content": "hello"}])

        await provider.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_auth_failure_raises_llm_error(self):
        """HTTP 401 raises LLMError with auth hint."""
        from unittest.mock import AsyncMock, patch

        respx.post(_MINIMAX_URL).mock(
            return_value=httpx.Response(
                401, json={"error": {"message": "Invalid API key"}}
            )
        )

        config = _make_config()
        provider = MinimaxProvider(config)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(LLMError, match="auth failed"):
                await provider.chat([{"role": "user", "content": "hello"}])

        await provider.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_empty_choices_raises_llm_error(self):
        """Response with no choices raises LLMError."""
        from unittest.mock import AsyncMock, patch

        respx.post(_MINIMAX_URL).mock(
            return_value=httpx.Response(200, json={"choices": []})
        )

        config = _make_config()
        provider = MinimaxProvider(config)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(LLMError, match="empty choices"):
                await provider.chat([{"role": "user", "content": "hello"}])

        await provider.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_server_error_raises_llm_error(self):
        """HTTP 500 raises LLMError."""
        from unittest.mock import AsyncMock, patch

        respx.post(_MINIMAX_URL).mock(
            return_value=httpx.Response(
                500, json={"error": {"message": "Internal server error"}}
            )
        )

        config = _make_config()
        provider = MinimaxProvider(config)

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(LLMError, match="500"):
                await provider.chat([{"role": "user", "content": "hello"}])

        await provider.close()


class TestMinimaxModelRegistry:
    """Test Minimax models are properly registered."""

    def test_models_in_registry(self):
        from contribai.llm.models import MODELS_BY_NAME

        assert "MiniMax-M2.7" in MODELS_BY_NAME
        assert "abab6.5s-chat" in MODELS_BY_NAME

    def test_model_specs_correct(self):
        from contribai.llm.models import MINIMAX_M27, MINIMAX_ABAB65S_CHAT, ModelTier

        assert MINIMAX_M27.tier == ModelTier.FLASH
        assert MINIMAX_ABAB65S_CHAT.tier == ModelTier.LITE
        assert MINIMAX_M27.context_window == 245_760
        assert MINIMAX_ABAB65S_CHAT.speed > MINIMAX_M27.speed

    def test_models_found_by_task_type(self):
        from contribai.llm.models import TaskType, get_models_for_task

        code_gen_models = get_models_for_task(TaskType.CODE_GEN)
        model_names = [m.name for m in code_gen_models]
        assert "MiniMax-M2.7" in model_names

        bulk_models = get_models_for_task(TaskType.BULK)
        bulk_names = [m.name for m in bulk_models]
        assert "abab6.5s-chat" in bulk_names
