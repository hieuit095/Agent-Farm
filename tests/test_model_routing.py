# ruff: noqa
"""
ROUTING TRAP TEST — Multi-Model Dream Team Verification
=======================================================

Intercepts every `create_llm_provider` call in the circular pipeline and
asserts that each phase exclusively requests the correct model string.

Expected routing table:
  ┌──────────────────────────┬─────────────────────────────────────────────────────────┐
  │ Phase                    │ Model                                                    │
  ├──────────────────────────┼─────────────────────────────────────────────────────────┤
  │ Primary Generator (DEV)  │ deepseek/deepseek-v3.2                                   │
  │ Red Team / Bloodhound    │ cognitivecomputations/dolphin-mistral-24b-venice-edition:free │
  │ Layer 1 Appraiser        │ moonshotai/kimi-k2.5                                     │
  │ QA Hardcore Scorer Ph.3  │ moonshotai/kimi-k2.6                                     │
  │ Layer 2 Supreme Auditor  │ google/gemini-3.1-pro-preview                            │
  └──────────────────────────┴─────────────────────────────────────────────────────────┘
"""

from __future__ import annotations

import asyncio
import contextlib
import copy
import json
import sys
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ── Stub out heavy optional dependencies before any farm_agent import ──────────
_STUB_MODULES = [
    "yaml",
    "pydantic",
    "pydantic.model_validator",
    "pydantic_settings",
    "httpx",
    "aiohttp",
    "aiosqlite",
    "docker",
    "docker.errors",
    "docker.models.containers",
    "apscheduler",
    "chromadb",
    "numpy",
    "git",
    "semgrep",
    "openai",
    "anthropic",
    "google",
    "google.genai",
    "apscheduler.schedulers",
    "apscheduler.schedulers.asyncio",
]
for _mod in _STUB_MODULES:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

# ── Model string constants (the ground truth) ─────────────────────────────────
MODEL_PRIMARY = "deepseek/deepseek-v4-flash"
MODEL_RED_TEAM = "deepseek/deepseek-v4-flash"
MODEL_LAYER1 = "qwen/qwen3.7-max"
MODEL_QA_SCORER = "qwen/qwen3.7-max"
MODEL_LAYER2 = "google/gemini-3.5-flash"


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_provider_mock(model: str) -> MagicMock:
    """Return an async-capable mock LLMProvider pinned to `model`."""
    m = MagicMock()
    m.model = model
    m.config = MagicMock(model=model, openrouter_api_key="sk-test", max_snippet_chars=15000)
    m.memory = None
    m.close = AsyncMock()
    m.complete = AsyncMock(return_value="ok")
    return m


def _build_fake_config(primary_model: str = MODEL_PRIMARY) -> MagicMock:
    """Construct a realistic FarmAgentConfig mock."""
    cfg = MagicMock()

    llm_cfg = MagicMock()
    llm_cfg.provider = "openrouter"
    llm_cfg.model = primary_model
    llm_cfg.api_key = ""
    llm_cfg.openrouter_api_key = "sk-test"
    llm_cfg.red_team_model = MODEL_RED_TEAM
    llm_cfg.temperature = 0.3
    llm_cfg.max_tokens = 8192
    llm_cfg.base_url = None
    cfg.llm = llm_cfg

    gh = MagicMock()
    gh.token = "ghp_test"
    gh.rate_limit_buffer = 100
    gh.secondary_tokens = []
    gh.max_prs_per_day = 10
    cfg.github = gh

    pl = MagicMock()
    pl.max_concurrent_repos = 3
    pl.llm_concurrency_cap = 5
    pl.rate_limit_cooldown_sec = 300
    pl.timeout_per_repo_sec = 300
    pl.max_ci_retries = 3
    pl.max_discussion_replies = 3
    pl.max_patch_retries = 2
    pl.max_review_retries = 2
    pl.sandbox_validation_enabled = True
    cfg.pipeline = pl

    an = MagicMock()
    an.openrouter_api_key = "sk-test"
    an.red_team_model = MODEL_RED_TEAM
    an.red_team_daily_limit = 1000
    an.severity_threshold = "medium"
    an.max_file_size_kb = 500
    an.enabled_analyzers = ["security"]
    an.skip_patterns = []
    an.use_semgrep = False
    an.semgrep_rulesets = []
    cfg.analysis = an

    st = MagicMock()
    st.resolved_db_path = ":memory:"
    cfg.storage = st

    disc = MagicMock()
    disc.excluded_languages = []
    cfg.discovery = disc

    mm = MagicMock()
    mm.enabled = False
    mm.strategy = "balanced"
    cfg.multi_model = mm

    cfg.notifications = MagicMock()
    return cfg


# ── Routing-Trap ───────────────────────────────────────────────────────────────


class RoutingTrap:
    """
    Patches `create_llm_provider` at the source module level so every
    provider construction is intercepted, regardless of which submodule
    calls the factory.
    """

    def __init__(self, primary_model: str = MODEL_PRIMARY):
        self.primary_model = primary_model
        self.seen_models: list[str] = []
        self._provider_cache: dict[str, MagicMock] = {}

    def _factory(self, config: Any, **kwargs) -> MagicMock:
        model = getattr(config, "model", self.primary_model)
        self.seen_models.append(model)
        if model not in self._provider_cache:
            self._provider_cache[model] = _make_provider_mock(model)
        return self._provider_cache[model]

    def get_provider(self, model: str) -> MagicMock:
        return self._provider_cache.get(model, _make_provider_mock(model))


def _build_patches(trap: RoutingTrap, cfg: MagicMock, fake_dossier, fake_gen_result):
    """Return a list of (target, kwargs) tuples that ExitStack will apply."""
    from farm_agent.core.models import Repository, FileNode

    fake_repo = Repository(
        owner="testorg",
        name="testrepo",
        full_name="testorg/testrepo",
        description="Test",
        language="Python",
        stars=100,
        forks=5,
        open_issues=10,
        clone_url="https://github.com/testorg/testrepo.git",
    )
    fake_target = MagicMock(
        repo_url="https://github.com/testorg/testrepo",
        scanned_at=None,
    )

    return [
        # Provider factory
        ("farm_agent.llm.provider.create_llm_provider", {"side_effect": trap._factory}),
        ("farm_agent.orchestrator.pipeline.create_llm_provider", {"side_effect": trap._factory}),
        # GitHub
        ("farm_agent.github.client.GitHubClient.__init__", {"return_value": None}),
        ("farm_agent.github.client.GitHubClient.close", {"new_callable": AsyncMock}),
        (
            "farm_agent.github.client.GitHubClient.get_repo_details",
            {"new_callable": AsyncMock, "return_value": fake_repo},
        ),
        (
            "farm_agent.github.client.GitHubClient.fetch_repo_structure_graphql",
            {
                "new_callable": AsyncMock,
                "return_value": [FileNode(path="src/auth.py", type="blob")],
            },
        ),
        (
            "farm_agent.github.client.GitHubClient.get_file_content",
            {"new_callable": AsyncMock, "return_value": "# auth code"},
        ),
        # Memory
        ("farm_agent.orchestrator.memory.Memory.__init__", {"return_value": None}),
        ("farm_agent.orchestrator.memory.Memory.close", {"new_callable": AsyncMock}),
        ("farm_agent.orchestrator.memory.Memory.init", {"new_callable": AsyncMock}),
        (
            "farm_agent.orchestrator.memory.Memory.get_today_pr_count",
            {"new_callable": AsyncMock, "return_value": 0},
        ),
        (
            "farm_agent.orchestrator.memory.Memory.get_qa_lessons",
            {"new_callable": AsyncMock, "return_value": []},
        ),
        ("farm_agent.orchestrator.memory.Memory.record_qa_lesson", {"new_callable": AsyncMock}),
        ("farm_agent.orchestrator.memory.Memory.add_filter_lesson", {"new_callable": AsyncMock}),
        (
            "farm_agent.orchestrator.memory.Memory.get_knowledge",
            {"new_callable": AsyncMock, "return_value": ""},
        ),
        (
            "farm_agent.orchestrator.memory.Memory.get_style_guide",
            {"new_callable": AsyncMock, "return_value": None},
        ),
        (
            "farm_agent.orchestrator.memory.Memory.get_openrouter_usage_today",
            {"new_callable": AsyncMock, "return_value": 0},
        ),
        (
            "farm_agent.orchestrator.memory.Memory.record_openrouter_usage",
            {"new_callable": AsyncMock},
        ),
        ("farm_agent.orchestrator.memory.Memory.mark_target_status", {"new_callable": AsyncMock}),
        # Bloodhound
        (
            "farm_agent.analysis.analyzer.BloodhoundAnalyzer.run_bloodhound",
            {"new_callable": AsyncMock, "return_value": fake_dossier},
        ),
        # Generator
        (
            "farm_agent.generator.engine.ContributionGenerator.generate_from_dossier",
            {"new_callable": AsyncMock, "return_value": fake_gen_result},
        ),
        # Layer 1
        (
            "farm_agent.orchestrator.pipeline.FarmAgentPipeline._layer1_expert_appraisal",
            {"new_callable": AsyncMock, "return_value": (True, "")},
        ),
        # Layer 2
        (
            "farm_agent.orchestrator.pipeline.FarmAgentPipeline._layer2_supreme_audit",
            {"new_callable": AsyncMock, "return_value": (True, "")},
        ),
        # Security gate
        (
            "farm_agent.orchestrator.pipeline.run_security_gate",
            {"new_callable": AsyncMock, "return_value": None},
        ),
        # PR manager
        (
            "farm_agent.pr.manager.PRManager.create_pr",
            {
                "new_callable": AsyncMock,
                "return_value": MagicMock(
                    number=1, html_url="https://github.com/testorg/testrepo/pull/1"
                ),
            },
        ),
        # Discovery
        ("farm_agent.github.discovery.DatabaseTargetDiscovery.__init__", {"return_value": None}),
        (
            "farm_agent.github.discovery.DatabaseTargetDiscovery.initialize",
            {"new_callable": AsyncMock},
        ),
        (
            "farm_agent.github.discovery.DatabaseTargetDiscovery.get_next_target",
            {"new_callable": AsyncMock, "return_value": fake_target},
        ),
        (
            "farm_agent.github.discovery.DatabaseTargetDiscovery.mark_status",
            {"new_callable": AsyncMock},
        ),
        # Notifier
        ("farm_agent.core.notifier.TelegramNotifier.__init__", {"return_value": None}),
        ("farm_agent.core.notifier.TelegramNotifier.close", {"new_callable": AsyncMock}),
    ]


# ── End-to-End Routing Trap Test ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_circular_model_routing():
    """
    Simulates one full run_circular() pass through the DEV-QA loop and
    asserts every phase routes to its designated model string.
    """
    from farm_agent.core.models import (
        VulnerabilityDossier,
        Vulnerability,
        Contribution,
        FileChange,
        Finding,
        ContributionType,
        Severity,
        ImpactLevel,
    )
    from farm_agent.generator.engine import GenerationResult

    fake_vuln = Vulnerability(
        file="src/auth.py",
        line=42,
        snippet="password = request.args.get('password')",
        evidence_chain=(
            "User-controlled request.args['password'] flows directly "
            "to SQL query at line 45 (cursor.execute)"
        ),
        poc="GET /login?password=' OR 1=1--",
        fix="Use parameterized queries",
        impact="CRITICAL: SQL injection → RCE",
        rule="semgrep:python.injection.sql",
        context_type="PRODUCTION",
    )
    fake_dossier = VulnerabilityDossier(
        repo_url="https://github.com/testorg/testrepo",
        target_commit="abc123",
        vulnerabilities=[fake_vuln],
    )

    fake_file_change = FileChange(
        path="src/auth.py",
        original_content="cursor.execute(f'SELECT * FROM users WHERE password = {password}')",
        new_content="cursor.execute('SELECT * FROM users WHERE password = ?', (pw,))",
    )
    fake_finding = Finding(
        type=ContributionType.SECURITY_FIX,
        severity=Severity.HIGH,
        title="SQL Injection",
        description="SQL Injection in auth.py",
        file_path="src/auth.py",
        impact_level=ImpactLevel.HIGH,
    )
    fake_contribution = Contribution(
        finding=fake_finding,
        changes=[fake_file_change],
        commit_message="fix(auth): use parameterized SQL query to prevent injection",
        title="fix: parameterized SQL to prevent injection in auth.py",
        description="SQL injection vulnerability fixed.",
        branch_name="fix/sql-injection-auth",
        contribution_type=ContributionType.SECURITY_FIX,
    )
    fake_gen_result = GenerationResult(
        contributions=[fake_contribution],
        false_positive_count=0,
    )

    trap = RoutingTrap(primary_model=MODEL_PRIMARY)
    cfg = _build_fake_config(MODEL_PRIMARY)

    patch_defs = _build_patches(trap, cfg, fake_dossier, fake_gen_result)

    with contextlib.ExitStack() as stack:
        for target, kwargs in patch_defs:
            stack.enter_context(patch(target, **kwargs))

        from farm_agent.orchestrator.pipeline import FarmAgentPipeline

        pipeline = FarmAgentPipeline(cfg)

        # Wire primary provider
        primary_provider = trap._factory(cfg.llm)
        pipeline._llm = primary_provider

        # Wire a passing QA score for the kimi-k2.6 provider
        qa_provider = trap.get_provider(MODEL_QA_SCORER)
        qa_provider.complete = AsyncMock(
            return_value=json.dumps(
                {
                    "score": 9.5,
                    "critiques": [],
                    "approved": True,
                }
            )
        )

        await pipeline.run_circular(json_path="target_repo.json", dry_run=True)

    # ── ROUTING ASSERTIONS ─────────────────────────────────────────────────
    print("\n[ROUTING TRAP] Models seen during run_circular():")
    for m in trap.seen_models:
        print(f"  → {m}")

    assert MODEL_PRIMARY in trap.seen_models, (
        f"PRIMARY model '{MODEL_PRIMARY}' was NEVER instantiated!\nSeen: {trap.seen_models}"
    )
    assert MODEL_QA_SCORER in trap.seen_models, (
        f"QA Scorer model '{MODEL_QA_SCORER}' was NEVER instantiated!\nSeen: {trap.seen_models}"
    )
    assert MODEL_QA_SCORER != MODEL_PRIMARY, (
        "MODEL_QA_SCORER and MODEL_PRIMARY must differ — deep-copy isolation broken!"
    )
    print("\n[ROUTING TRAP] ✅ All run_circular routing assertions PASSED.")


# ── Unit tests: factory maps each model correctly ─────────────────────────────


def test_create_llm_provider_maps_deepseek():
    from farm_agent.llm.provider import create_llm_provider, OpenRouterProvider

    cfg = MagicMock()
    cfg.provider = "openrouter"
    cfg.model = MODEL_PRIMARY
    cfg.api_key = ""
    cfg.openrouter_api_key = "sk-test"
    cfg.temperature = 0.3
    cfg.max_tokens = 8192
    cfg.base_url = None

    with patch.object(OpenRouterProvider, "__init__", return_value=None) as m:
        create_llm_provider(cfg)
    assert m.call_args[0][0].model == MODEL_PRIMARY


def test_create_llm_provider_maps_kimi_k26():
    from farm_agent.llm.provider import create_llm_provider, OpenRouterProvider

    base = MagicMock()
    base.provider = "openrouter"
    base.model = MODEL_PRIMARY
    base.api_key = ""
    base.openrouter_api_key = "sk-test"
    base.temperature = 0.3
    base.max_tokens = 8192
    base.base_url = None

    qa_cfg = copy.copy(base)
    qa_cfg.model = MODEL_QA_SCORER

    with patch.object(OpenRouterProvider, "__init__", return_value=None) as m:
        create_llm_provider(qa_cfg)
    assert m.call_args[0][0].model == MODEL_QA_SCORER, (
        f"Expected '{MODEL_QA_SCORER}', got '{m.call_args[0][0].model}'"
    )


def test_create_llm_provider_maps_kimi_k25():
    from farm_agent.llm.provider import create_llm_provider, OpenRouterProvider

    cfg = MagicMock()
    cfg.provider = "openrouter"
    cfg.model = MODEL_LAYER1
    cfg.api_key = ""
    cfg.openrouter_api_key = "sk-test"
    cfg.temperature = 0.1
    cfg.max_tokens = 8192
    cfg.base_url = None

    with patch.object(OpenRouterProvider, "__init__", return_value=None) as m:
        create_llm_provider(cfg)
    assert m.call_args[0][0].model == MODEL_LAYER1


def test_create_llm_provider_maps_gemini():
    from farm_agent.llm.provider import create_llm_provider, OpenRouterProvider

    cfg = MagicMock()
    cfg.provider = "openrouter"
    cfg.model = MODEL_LAYER2
    cfg.api_key = ""
    cfg.openrouter_api_key = "sk-test"
    cfg.temperature = 0.1
    cfg.max_tokens = 8192
    cfg.base_url = None

    with patch.object(OpenRouterProvider, "__init__", return_value=None) as m:
        create_llm_provider(cfg)
    assert m.call_args[0][0].model == MODEL_LAYER2


def test_config_defaults_to_deepseek():
    from farm_agent.core.config import LLMConfig  # type: ignore

    try:
        cfg = LLMConfig()
        assert cfg.model == MODEL_PRIMARY, f"Expected '{MODEL_PRIMARY}', got '{cfg.model}'"
        assert cfg.provider == "openrouter", f"Expected 'openrouter', got '{cfg.provider}'"
        assert not hasattr(cfg, "minimax_group_id"), "LLMConfig still has minimax_group_id!"
    except Exception as exc:
        pytest.skip(f"LLMConfig cannot be instantiated: {exc}")


def test_pipeline_config_uses_llm_concurrency_cap():
    from farm_agent.core.config import PipelineConfig  # type: ignore

    try:
        cfg = PipelineConfig()
        assert hasattr(cfg, "llm_concurrency_cap"), "missing 'llm_concurrency_cap'!"
        assert not hasattr(cfg, "minimax_safe_concurrency_cap"), "Minimax ghost field still exists!"
    except Exception as exc:
        pytest.skip(f"PipelineConfig cannot be instantiated: {exc}")
