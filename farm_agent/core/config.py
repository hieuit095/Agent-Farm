"""Pydantic-based configuration system for Farm-Agent."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator

from farm_agent.core.exceptions import ConfigError


class GitHubConfig(BaseModel):
    """GitHub API configuration."""

    token: str = ""
    max_repos_per_run: int = 5
    max_prs_per_day: int = 10
    min_daily_prs: int = 4
    max_daily_prs: int = 10
    rate_limit_buffer: int = 3  # Stop API calls when remaining < 3 to prevent secondary rate limits
    dco_signoff: bool = True  # Auto-append Signed-off-by to commit messages
    secondary_tokens: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def resolve_token(self):
        """Fallback: $GITHUB_TOKEN env var → `gh auth token` CLI."""
        if not self.token:
            self.token = os.environ.get("GITHUB_TOKEN", "")
        if not self.token:
            try:
                result = subprocess.run(
                    ["gh", "auth", "token"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0 and result.stdout.strip():
                    self.token = result.stdout.strip()
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass
        if not self.secondary_tokens:
            env_tokens = os.environ.get("GITHUB_SECONDARY_TOKENS", "")
            if env_tokens:
                self.secondary_tokens = [t.strip() for t in env_tokens.split(",") if t.strip()]
        return self


class LLMConfig(BaseModel):
    """LLM provider configuration."""

    provider: Literal["minimax", "openrouter"] = "minimax"
    model: str = "MiniMax-M2.7"
    api_key: str = ""
    temperature: float = 0.3
    max_tokens: int = 8192
    base_url: str | None = None

    # Minimax
    minimax_group_id: str = ""

    # OpenRouter (Red Team engine for Bloodhound audits)
    openrouter_api_key: str = ""
    red_team_model: str = "cognitivecomputations/dolphin-mistral-24b-venice-edition:free"
    max_snippet_chars: int = 15000

    @model_validator(mode="after")
    def resolve_api_key_and_defaults(self):
        """Fallback: env vars for API keys."""
        if not self.api_key:
            self.api_key = os.environ.get("MINIMAX_API_KEY", "")
        if not self.minimax_group_id:
            self.minimax_group_id = os.environ.get("MINIMAX_GROUP_ID", "")
        if not self.openrouter_api_key:
            self.openrouter_api_key = os.environ.get("OPENROUTER_API_KEY", "")

        if self.model == "gemini-2.5-flash":
            self.model = "MiniMax-M2.7"
        return self


class AnalysisConfig(BaseModel):
    """Analysis engine configuration."""

    enabled_analyzers: list[str] = Field(
        default_factory=lambda: ["security", "code_quality", "docs", "ui_ux"]
    )
    severity_threshold: Literal["low", "medium", "high", "critical"] = "medium"
    max_file_size_kb: int = 500
    skip_patterns: list[str] = Field(
        default_factory=lambda: ["*.min.js", "*.min.css", "vendor/*", "node_modules/*", "*.lock"]
    )

    # Contextual Intelligence: directories that indicate non-production code.
    # Findings in these paths are tagged LOW_PRIORITY_CONTEXT and skipped
    # by the Orchestrator to prevent spam PRs against tests/examples/docs.
    forbidden_paths: list[str] = Field(
        default_factory=lambda: [
            "tests",
            "test",
            "testing",
            "examples",
            "example",
            "example_projects",
            "security_examples",
            "fixtures",
            "fixture",
            "mocks",
            "mock",
            "docs",
            "documentation",
            "doc",
            "benchmarks",
            "benchmark",
            "perf",
            "test_data",
            "testdata",
            "sample_data",
            "samples",
            "demo",
            "demos",
            "playground",
        ]
    )

    # Red Team engine (Bloodhound White-Hat audits via OpenRouter)
    red_team_model: str = "cognitivecomputations/dolphin-mistral-24b-venice-edition:free"
    red_team_daily_limit: int = 1000

    # Semgrep radar (runs concurrently with ast-grep in Bloodhound pipeline)
    use_semgrep: bool = True
    semgrep_rulesets: list[str] = Field(
        default_factory=lambda: ["p/security-audit", "p/cwe-top-25", "p/default"]
    )


class ContributionConfig(BaseModel):
    """Contribution generation configuration."""

    enabled_types: list[str] = Field(
        default_factory=lambda: [
            "security_fix",
            "docs_improve",
            "code_quality",
            "feature_add",
            "ui_ux_fix",
            "performance_opt",
            "refactor",
        ]
    )
    max_files_per_pr: int = 10
    run_tests_before_pr: bool = True
    commit_convention: Literal["conventional", "angular", "none"] = "conventional"
    pr_description_style: Literal["minimal", "detailed"] = "detailed"
    max_review_retries: int = 2


class DiscoveryConfig(BaseModel):
    """Repository discovery configuration."""

    languages: list[str] = Field(default_factory=lambda: ["python"])
    excluded_languages: list[str] = Field(default_factory=list)
    stars_range: list[int] = Field(default_factory=lambda: [50, 10000])
    min_last_activity_days: int = 30
    require_contributing_guide: bool = False
    topics: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def resolve_excluded_languages(self):
        """Parse excluded_languages from env var."""
        env_val = os.environ.get("EXCLUDED_LANGUAGES", "")
        if env_val:
            self.excluded_languages = [
                lang.strip().lower() for lang in env_val.split(",") if lang.strip()
            ]
        else:
            self.excluded_languages = [lang.lower() for lang in self.excluded_languages]
        return self


class StorageConfig(BaseModel):
    """Storage / memory configuration."""

    db_path: str = "data/memory.db"
    cache_ttl_hours: int = 24

    @property
    def resolved_db_path(self) -> Path:
        return Path(self.db_path).expanduser()


class PipelineConfig(BaseModel):
    """Pipeline execution configuration."""

    max_concurrent_repos: int = 3
    timeout_per_repo_sec: int = 300
    # Fail-safe killswitch limits (externalized from patrol.py / engine.py)
    max_ci_retries: int = 3
    max_discussion_replies: int = 3
    max_patch_retries: int = 2
    max_review_retries: int = 2
    # P0 FIX: Sandbox Guillotine — hardcoded ON, never bypassed
    sandbox_validation_enabled: bool = True


class NotificationConfig(BaseModel):
    """Notification channel configuration."""

    slack_webhook: str = ""
    discord_webhook: str = ""
    telegram_token: str = ""
    telegram_chat_id: str = ""


class LogConfig(BaseModel):
    """Daily rolling log configuration."""

    level: str = "INFO"
    log_dir: str = "logs"
    keep_days: int = 30


class MultiModelConfig(BaseModel):
    """Multi-model routing configuration."""

    enabled: bool = False
    strategy: str = "balanced"  # performance | balanced | economy
    # Per-task model overrides (task_type → model_name)
    model_overrides: dict[str, str] = Field(default_factory=dict)


class FarmAgentConfig(BaseModel):
    """Root configuration for FarmAgentConfig."""

    github: GitHubConfig = Field(default_factory=GitHubConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    analysis: AnalysisConfig = Field(default_factory=AnalysisConfig)
    contribution: ContributionConfig = Field(default_factory=ContributionConfig)
    discovery: DiscoveryConfig = Field(default_factory=DiscoveryConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    pipeline: PipelineConfig = Field(default_factory=PipelineConfig)
    notifications: NotificationConfig = Field(default_factory=NotificationConfig)
    logging: LogConfig = Field(default_factory=LogConfig)
    multi_model: MultiModelConfig = Field(default_factory=MultiModelConfig)


def load_config(path: str | Path | None = None) -> FarmAgentConfig:
    """Load configuration from YAML file.

    Priority: explicit path > ./config.yaml > ~/.farm_agent/config.yaml > defaults.
    Token fallback: GITHUB_TOKEN env var > gh auth token CLI (when token is empty in yaml).
    Automatically loads .env file from current working directory.
    """
    from dotenv import load_dotenv

    load_dotenv()

    search_paths = [
        Path(path) if path else None,
        Path("config.yaml"),
        Path.home() / ".farm_agent" / "config.yaml",
    ]

    for p in search_paths:
        if p and p.exists():
            try:
                raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
                config = FarmAgentConfig(**raw)
                config.github.resolve_token()
                return config
            except yaml.YAMLError as e:
                raise ConfigError(f"Invalid YAML in {p}: {e}") from e
            except Exception as e:
                raise ConfigError(f"Failed to load config from {p}: {e}") from e

    # No config file found - use defaults
    config = FarmAgentConfig()
    config.github.resolve_token()
    return config
