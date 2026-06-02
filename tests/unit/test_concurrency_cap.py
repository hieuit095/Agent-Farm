import sys
from unittest.mock import MagicMock

# Mock missing dependencies to allow importing farm_agent
sys.modules["yaml"] = MagicMock()
sys.modules["pydantic"] = MagicMock()
sys.modules["pydantic.model_validator"] = MagicMock()
sys.modules["pydantic_settings"] = MagicMock()
sys.modules["httpx"] = MagicMock()
sys.modules["aiohttp"] = MagicMock()
sys.modules["aiosqlite"] = MagicMock()
sys.modules["google"] = MagicMock()
sys.modules["google.genai"] = MagicMock()
sys.modules["openai"] = MagicMock()
sys.modules["anthropic"] = MagicMock()
sys.modules["docker"] = MagicMock()
sys.modules["apscheduler"] = MagicMock()
sys.modules["chromadb"] = MagicMock()
sys.modules["numpy"] = MagicMock()
sys.modules["git"] = MagicMock()

from farm_agent.orchestrator.pipeline import FarmAgentPipeline


def test_get_max_concurrency_provider_capped():
    config = MagicMock()
    config.pipeline.max_concurrent_repos = 10
    config.pipeline.llm_concurrency_cap = 5
    config.llm.provider = "openrouter"

    pipeline = FarmAgentPipeline(config)
    assert pipeline._get_max_concurrency() == 5

def test_get_max_concurrency_under_cap():
    config = MagicMock()
    config.pipeline.max_concurrent_repos = 3
    config.pipeline.llm_concurrency_cap = 5
    config.llm.provider = "openrouter"

    pipeline = FarmAgentPipeline(config)
    assert pipeline._get_max_concurrency() == 3
