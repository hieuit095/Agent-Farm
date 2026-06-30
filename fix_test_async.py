from unittest.mock import MagicMock
import os
import tempfile
from farm_agent.core.models import FileChange
from farm_agent.orchestrator.pipeline import FarmAgentPipeline

config = MagicMock()
config.pipeline.max_concurrent_repos = 10
config.pipeline.llm_concurrency_cap = 5
config.pipeline.rate_limit_cooldown_sec = 300
config.llm.provider = "openrouter"
pipeline = FarmAgentPipeline(config)
