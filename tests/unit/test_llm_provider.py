"""Tests for LLM provider factory and mock interactions."""

from unittest.mock import AsyncMock, patch

import pytest

from contribai.core.config import LLMConfig
from contribai.core.exceptions import LLMError
from contribai.llm.provider import (
    MinimaxProvider,
    create_llm_provider,
)


class TestCreateProvider:
    def test_create_minimax(self):
        config = LLMConfig(provider="minimax", api_key="test")
        with patch("contribai.llm.provider.MinimaxProvider.__init__", return_value=None):
            provider = create_llm_provider(config)
            assert isinstance(provider, MinimaxProvider)

    def test_unknown_provider_raises(self):
        config = LLMConfig(provider="minimax", api_key="test")
        config.provider = "unknown"
        with pytest.raises(LLMError, match="Unknown LLM provider"):
            create_llm_provider(config)


class TestLLMConfigDefaults:
    def test_minimax_default_model(self):
        config = LLMConfig(provider="minimax")
        assert config.model == "MiniMax-M2.7"

    def test_custom_model_preserved(self):
        config = LLMConfig(provider="minimax", model="abab6.5s-chat")
        assert config.model == "abab6.5s-chat"

    def test_temperature_default(self):
        config = LLMConfig(provider="minimax")
        assert config.temperature == 0.3


class TestMinimaxProvider:
    @pytest.mark.asyncio
    async def test_provider_close(self):
        config = LLMConfig(provider="minimax", model="MiniMax-M2.7", api_key="test")
        provider = MinimaxProvider(config)
        await provider.close()  # Should not raise
