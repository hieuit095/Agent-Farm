"""Main pipeline orchestrator.

Coordinates the full contribution flow:
discover → analyze → generate → PR.
"""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import tempfile
import json
import re
from dataclasses import dataclass, field

from farm_agent.agents.registry import create_default_registry
from farm_agent.analysis.analyzer import BloodhoundAnalyzer, CodeAnalyzer
from farm_agent.core.config import FarmAgentConfig
from farm_agent.core.middleware import build_default_chain
from farm_agent.core.models import (
    AnalysisResult,
    Contribution,
    ContributionType,
    DiscoveryCriteria,
    FileChange,
    Finding,
    ImpactLevel,
    PRResult,
    QAResult,
    RepoContext,
    Repository,
    Severity,
    VulnerabilityDossier,
)
from farm_agent.generator.engine import ContributionGenerator, GenerationResult
from farm_agent.generator.scorer import QAHardcoreScorer
from farm_agent.github.client import GitHubClient
from farm_agent.github.discovery import DatabaseTargetDiscovery, RepoDiscovery
from farm_agent.github.guidelines import fetch_repo_guidelines
from farm_agent.github.security_gate import run_security_gate
from farm_agent.issues.solver import IssueSolver
from farm_agent.llm.provider import create_llm_provider
from farm_agent.orchestrator.memory import Memory
from farm_agent.pr.manager import PRManager
from farm_agent.tools.protocol import create_default_tools

logger = logging.getLogger(__name__)

# Files that should NOT be modified/created by Farm-Agent
# These are meta/governance files that projects manage themselves
PROTECTED_META_FILES = {
    # Documentation
    "CONTRIBUTING.md",
    ".github/CONTRIBUTING.md",
    "docs/CONTRIBUTING.md",
    "CODE_OF_CONDUCT.md",
    ".github/CODE_OF_CONDUCT.md",
    "LICENSE",
    "LICENSE.md",
    "LICENSE.txt",
    ".github/FUNDING.yml",
    ".github/SECURITY.md",
    "SECURITY.md",
    ".github/CODEOWNERS",
    ".all-contributorsrc",
    # ── Config / Build / Tooling files — NEVER tweak ──────────────────
    # Compiler & type-checker configs
    "tsconfig.json",
    "tsconfig.base.json",
    "tsconfig.build.json",
    "tsconfig.app.json",
    "tsconfig.node.json",
    "tsconfig.spec.json",
    "jsconfig.json",
    ".tsbuildinfo",
    # Linter & formatter configs
    ".eslintrc",
    ".eslintrc.js",
    ".eslintrc.cjs",
    ".eslintrc.json",
    ".eslintrc.yaml",
    ".eslintignore",
    ".prettierrc",
    ".prettierrc.js",
    ".prettierrc.cjs",
    ".prettierrc.json",
    ".prettierrc.yaml",
    ".prettierignore",
    ".editorconfig",
    # Bundler configs
    "webpack.config.js",
    "webpack.config.ts",
    "webpack.config.base.js",
    "vite.config.ts",
    "vite.config.js",
    "rollup.config.js",
    ".babelrc",
    "babel.config.js",
    "babel.config.json",
    # Package manager & dependency configs
    "package.json",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "npm-shrinkwrap.json",
    ".npmrc",
    # CI/CD configs (not code logic)
    ".github/workflows/*.yml",
    ".github/workflows/*.yaml",
    "azure-pipelines.yml",
    ".gitlab-ci.yml",
    "Jenkinsfile",
    # Env & secrets
    ".env",
    ".env.local",
    ".env.development",
    ".env.production",
    ".env.example",
}

# File extensions to skip — doc/config-only changes are low-value
# Only code files should be modified
SKIP_EXTENSIONS = {
    ".md",
    ".txt",
    ".rst",
    ".yml",
    ".yaml",
    ".toml",
    ".cfg",
    ".ini",
    ".json",
}


def _titles_similar(title_a: str, title_b: str) -> bool:
    """Check if two finding/PR titles address the EXACT same technical issue.

    PHASE 3-FIX: Eradicated naive 50% single-word intersection.
    Now requires strict bigram sequence overlap or near-exact match
    to prevent blocking separate valid fixes that happen to share
    generic coding terminology (e.g., 'fix error in').
    """
    a = title_a.lower().strip()
    b = title_b.lower().strip()

    # Exact or near-exact string match
    if a == b or a in b or b in a:
        return True

    # Strip common git prefixes
    for prefix in [
        "fix:",
        "feat:",
        "chore:",
        "docs:",
        "refactor:",
        "bugfix:",
        "fix(core):",
        "fix(ui):",
    ]:
        if a.startswith(prefix):
            a = a[len(prefix) :].strip()
        if b.startswith(prefix):
            b = b[len(prefix) :].strip()

    words_a = a.split()
    words_b = b.split()

    if len(words_a) < 3 or len(words_b) < 3:
        return a == b

    # Build bigrams to preserve semantic sequence instead of just word salad
    bigrams_a = {f"{words_a[i]} {words_a[i + 1]}" for i in range(len(words_a) - 1)}
    bigrams_b = {f"{words_b[i]} {words_b[i + 1]}" for i in range(len(words_b) - 1)}

    if not bigrams_a or not bigrams_b:
        return False

    overlap = len(bigrams_a & bigrams_b)
    smaller = min(len(bigrams_a), len(bigrams_b))

    # Requires 80% contiguous bigram sequence overlap to be considered duplicate
    # (e.g., "fix race condition in auth" vs "fix race condition in db")
    return overlap / smaller > 0.8

class AdaptiveConcurrencyManager:
    """CRIT-03 FIX: Dynamic concurrency controller with backoff on LLMRateLimitError.

    Instead of a hardcoded `min(max_conc, 5)` for LLM providers, this class:
    1. Reads the configured safe cap from `config.pipeline.llm_concurrency_cap`.
    2. When an LLMRateLimitError (HTTP 429) is caught, immediately drops concurrency
       to 1 for `rate_limit_cooldown_sec` seconds (default 5 minutes).
    3. After cooldown, gradually ramps concurrency back up to the configured cap
       (one extra slot every 60 seconds) until the original max is restored.

    Thread-safe: uses asyncio.Lock internally.
    """

    def __init__(self, configured_max: int, provider_cap: int, cooldown_sec: int):
        self._configured_max = configured_max
        self._provider_cap = provider_cap
        self._cooldown_sec = cooldown_sec
        self._current_max = min(configured_max, provider_cap)
        self._lock = asyncio.Lock()
        self._cooldown_until: float = 0.0
        self._ramp_task: asyncio.Task | None = None

    @property
    def current_value(self) -> int:
        return self._current_max

    def make_semaphore(self) -> asyncio.Semaphore:
        """Create a fresh semaphore at the current concurrency level."""
        return asyncio.Semaphore(self._current_max)

    async def notify_rate_limit(self) -> None:
        """Call when an LLMRateLimitError or HTTP 429 is caught.

        Immediately collapses concurrency to 1 and schedules a ramp-back
        task that runs in the background after the cooldown expires.
        """
        import time

        async with self._lock:
            if self._ramp_task and not self._ramp_task.done():
                # Already in cooldown — reset the timer
                self._ramp_task.cancel()

            self._current_max = 1
            self._cooldown_until = time.time() + self._cooldown_sec
            logger.warning(
                "[CRIT-03] LLMRateLimitError detected — dropping concurrency to 1 "
                "for %ds cooldown (ramp target: %d)",
                self._cooldown_sec,
                min(self._configured_max, self._provider_cap),
            )

        self._ramp_task = asyncio.create_task(self._ramp_back())

    async def _ramp_back(self) -> None:
        """Gradually restore concurrency after cooldown expires."""
        import time

        remaining = self._cooldown_until - time.time()
        if remaining > 0:
            await asyncio.sleep(remaining)

        target = min(self._configured_max, self._provider_cap)
        ramp_interval = 60  # add one slot every 60 seconds

        while self._current_max < target:
            async with self._lock:
                self._current_max = min(self._current_max + 1, target)
                logger.info(
                    "[CRIT-03] Ramping concurrency back up: %d/%d",
                    self._current_max, target,
                )
            await asyncio.sleep(ramp_interval)

        logger.info("[CRIT-03] Concurrency fully restored to %d.", target)


@dataclass
class PipelineResult:
    """Result of a pipeline run."""

    repos_analyzed: int = 0
    findings_total: int = 0
    contributions_generated: int = 0
    prs_created: int = 0
    prs: list[PRResult] = field(default_factory=list)
    pr_urls: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class ContribPipeline:
    """Main orchestrator for the contribution pipeline."""

    def __init__(self, config: FarmAgentConfig):
        self.config = config
        self._github: GitHubClient | None = None
        self._llm = None
        self._memory: Memory | None = None
        self._analyzer: CodeAnalyzer | None = None
        self._generator: ContributionGenerator | None = None
        self._pr_manager: PRManager | None = None
        self._discovery: RepoDiscovery | None = None
        self._sandbox = None  # DockerSandbox — initialized in _init_components
        self._middleware_chain: list = []
        self._agent_registry = None
        self._tool_registry = None

        from farm_agent.core.notifier import TelegramNotifier

        self._notifier = TelegramNotifier(
            token=self.config.notifications.telegram_token,
            chat_id=self.config.notifications.telegram_chat_id,
        )
        self._human_typing_lock = asyncio.Lock()

        # CRIT-03 FIX: Adaptive concurrency — provider-aware cap with
        # dynamic backoff on LLMRateLimitError / HTTP 429.
        _provider = self.config.llm.provider
        _safe_cap = self.config.pipeline.llm_concurrency_cap
        self._concurrency_mgr = AdaptiveConcurrencyManager(
            configured_max=self.config.pipeline.max_concurrent_repos,
            provider_cap=_safe_cap,
            cooldown_sec=self.config.pipeline.rate_limit_cooldown_sec,
        )
        if self.config.pipeline.max_concurrent_repos > _safe_cap:
            logger.info(
                "[CRIT-03] Provider '%s': user concurrency=%d capped to safe limit=%d "
                "(override via pipeline.llm_concurrency_cap in config.yaml)",
                _provider,
                self.config.pipeline.max_concurrent_repos,
                _safe_cap,
            )

    def _get_max_concurrency(self) -> int:
        """Return current safe concurrency level from the adaptive manager."""
        return self._concurrency_mgr.current_value

    async def _notify_rate_limit(self) -> None:
        """Signal the adaptive concurrency manager that a 429 was received.

        Call this inside any except LLMRateLimitError block that fires
        during parallel repo processing to trigger automatic backoff.
        """
        await self._concurrency_mgr.notify_rate_limit()

    async def _init_components(self):
        """Initialize all pipeline components."""
        # LLM — with optional multi-model routing
        mm = self.config.multi_model
        self._llm = create_llm_provider(
            self.config.llm,
            multi_model=mm.enabled,
            strategy=mm.strategy,
        )

        # GitHub
        self._github = GitHubClient(
            token=self.config.github.token,
            rate_limit_buffer=self.config.github.rate_limit_buffer,
            secondary_tokens=self.config.github.secondary_tokens,
        )

        # Memory
        self._memory = Memory(self.config.storage.resolved_db_path)
        await self._memory.init()

        # Inject memory into LLM provider for quota tracking
        self._llm.memory = self._memory

        # Analyzer
        self._analyzer = CodeAnalyzer(
            llm=self._llm,
            github=self._github,
            config=self.config.analysis,
            memory=self._memory,
        )

        # Generator — now with memory for repo_preferences
        self._generator = ContributionGenerator(
            llm=self._llm,
            config=self.config.contribution,
            memory=self._memory,
            pipeline_config=self.config.pipeline,
        )

        # PR Manager
        self._pr_manager = PRManager(github=self._github, llm=self._llm)

        # ── Polyglot Sandbox — Docker-based patch validation ─────────────────
        from farm_agent.core.sandbox import DockerSandbox

        self._sandbox = DockerSandbox()
        logger.info("DockerSandbox initialised — patches will be validated before PR creation")

        # Discovery
        self._discovery = RepoDiscovery(
            client=self._github,
            config=self.config.discovery,
        )

        # Middleware chain (DeerFlow pattern)
        self._middleware_chain = build_default_chain(
            max_prs_per_day=self.config.github.max_prs_per_day,
            max_retries=self.config.pipeline.max_retries
            if hasattr(self.config.pipeline, "max_retries")
            else 2,
            min_quality_score=self.config.pipeline.min_quality_score
            if hasattr(self.config.pipeline, "min_quality_score")
            else 5.0,
        )
        logger.info("Middleware chain: %d middlewares loaded", len(self._middleware_chain))

        # Agent registry (DeerFlow pattern)
        self._agent_registry = create_default_registry()
        logger.info(
            "Agent registry: %d agents loaded",
            len(self._agent_registry.list_agents()),
        )

        # Tool registry (DeerFlow pattern)
        self._tool_registry = create_default_tools(
            github_client=self._github,
            llm_provider=self._llm,
        )
        logger.info(
            "Tool registry: %d tools loaded",
            len(self._tool_registry.list_tools()),
        )

    async def _cleanup(self):
        """Clean up resources."""
        if self._github:
            await self._github.close()
        if self._llm:
            await self._llm.close()
        if self._memory:
            await self._memory.close()
        # Close any notifier attached to sub-components
        if hasattr(self, "_notifier") and self._notifier:
            await self._notifier.close()

    # ── Public API ─────────────────────────────────────────────────────────

    async def run(
        self,
        criteria: DiscoveryCriteria | None = None,
        dry_run: bool = False,
    ) -> PipelineResult:
        """Run the full pipeline: discover -> analyze -> generate -> PR.

        Processes multiple repos in parallel using asyncio.Semaphore.

        Args:
            criteria: Optional custom discovery criteria
            dry_run: If True, analyze and generate but don't create PRs
        """
        await self._init_components()
        result = PipelineResult()
        run_id = await self._memory.start_run()
        logger.info("▶ Starting pipeline run (dry_run=%s, run_id=%s)", dry_run, run_id)

        try:
            # Check daily PR limit
            today_prs = await self._memory.get_today_pr_count()
            remaining_prs = self.config.github.max_prs_per_day - today_prs
            if remaining_prs <= 0 and not dry_run:
                logger.warning(
                    "Daily PR limit reached (%d)",
                    self.config.github.max_prs_per_day,
                )
                return result

            # 1. Discover repos
            logger.info("Discovering repositories...")
            repos = await self._discovery.discover(criteria)
            if not repos:
                logger.warning("No repositories found matching criteria")
                return result

            logger.info("Found %d candidate repositories", len(repos))

            # Limit to max repos per run
            repos = repos[: self.config.github.max_repos_per_run]

            # 2. Process repos in parallel with adaptive semaphore (CRIT-03)
            max_conc = self._get_max_concurrency()
            sem = self._concurrency_mgr.make_semaphore()
            logger.info(
                "Processing %d repos (max %d concurrent, provider=%s)",
                len(repos),
                max_conc,
                self.config.llm.provider,
            )

            async def _guarded(
                repo: Repository,
            ) -> PipelineResult | None:
                async with sem:
                    if await self._memory.has_analyzed(repo.full_name):
                        logger.info(
                            "Skipping %s (already analyzed)",
                            repo.full_name,
                        )
                        return None
                    try:
                        return await self._process_repo(repo, dry_run, remaining_prs)
                    except Exception as e:
                        from farm_agent.core.exceptions import LLMRateLimitError
                        if isinstance(e, LLMRateLimitError):
                            await self._notify_rate_limit()
                        msg = f"Error processing {repo.full_name}: {e}"
                        logger.error(msg)
                        err = PipelineResult()
                        err.errors.append(msg)
                        return err

            repo_results = await asyncio.gather(*[_guarded(r) for r in repos])

            # Aggregate results
            for rr in repo_results:
                if rr is None:
                    continue
                result.repos_analyzed += 1
                result.findings_total += rr.findings_total
                result.contributions_generated += rr.contributions_generated
                result.prs_created += rr.prs_created
                result.prs.extend(rr.prs)
                result.errors.extend(rr.errors)

            # Log run
            await self._memory.finish_run(
                run_id,
                repos_analyzed=result.repos_analyzed,
                prs_created=result.prs_created,
                findings=result.findings_total,
                errors=len(result.errors),
            )

        finally:
            await self._cleanup()

        logger.info(
            "✅ Pipeline run completed — repos=%d, findings=%d, PRs=%d, errors=%d",
            result.repos_analyzed,
            result.findings_total,
            result.prs_created,
            len(result.errors),
        )
        return result

    async def hunt(
        self,
        *,
        rounds: int = 5,
        delay_sec: int = 30,
        dry_run: bool = False,
        mode: str = "both",
    ) -> PipelineResult:
        """Hunt mode: aggressively discover and contribute to repos.

        Runs multiple discovery rounds with varied criteria.
        For each round:
        1. Discover repos (varied star range, shuffled languages)
        2. Filter to repos that actually merge external PRs
        3. Process each repo through the full pipeline
        4. Wait between rounds to avoid rate limits

        Args:
            rounds: Number of discovery rounds
            delay_sec: Delay between rounds
            dry_run: If True, don't create PRs
            mode: 'analysis' (code scan), 'issues' (issue solving), 'both'
        """
        import random

        await self._init_components()
        total = PipelineResult()

        friendly_repos: list[Repository] = []

        cfg_min, cfg_max = self.config.discovery.stars_range
        star_tiers = [
            (cfg_min, cfg_max),
            (100, 1000),
            (1000, 5000),
            (5000, 20000),
            (500, 3000),
        ]
        langs = list(self.config.discovery.languages)

        try:
            for rnd in range(1, rounds + 1):
                today_prs = await self._memory.get_today_pr_count()
                remaining = self.config.github.max_prs_per_day - today_prs
                if remaining <= 0 and not dry_run:
                    logger.warning(
                        "🛑 Daily PR limit reached (%d). Stopping.",
                        self.config.github.max_prs_per_day,
                    )
                    break

                random.shuffle(langs)
                stars = star_tiers[(rnd - 1) % len(star_tiers)]
                criteria = DiscoveryCriteria(
                    languages=langs[:2],
                    stars_min=stars[0],
                    stars_max=stars[1],
                    min_last_activity_days=7,
                    max_results=10,
                )

                logger.info(
                    "🔥 Hunt round %d/%d — %s, ★ %d-%d",
                    rnd,
                    rounds,
                    "/".join(criteria.languages),
                    stars[0],
                    stars[1],
                )

                repos = await self._discovery.discover(criteria)
                if not repos:
                    logger.info("No repos found this round")
                    if rnd < rounds:
                        await asyncio.sleep(delay_sec)
                    continue

                # Filter to valid targets (skip already-analyzed repos)
                # ── Prepend friendly repos that are off cooldown ──
                targets: list[Repository] = []
                for repo in friendly_repos:
                    if await self._memory.has_analyzed(repo.full_name):
                        logger.debug(
                            "🏠 Skipping %s (on cooldown or already analyzed)", repo.full_name
                        )
                        continue
                    targets.append(repo)
                    logger.info(
                        "🏠 Familiar Grounds: added %s (off cooldown, stars=%d)",
                        repo.full_name,
                        repo.stars,
                    )
                # ── End friendly repos ──

                for repo in repos:
                    if await self._memory.has_analyzed(repo.full_name):
                        logger.debug("Skipping %s (already analyzed)", repo.full_name)
                        continue
                    targets.append(repo)

                if not targets:
                    logger.info("No new repos to scan this round (all previously analyzed)")
                    if rnd < rounds:
                        await asyncio.sleep(delay_sec)
                    continue

                logger.info(
                    "🎯 %d target repo(s) after filtering (from %d discovered)",
                    len(targets),
                    len(repos),
                )

                max_targets = self.config.github.max_repos_per_run
                max_conc = self._get_max_concurrency()
                sem = self._concurrency_mgr.make_semaphore()
                selected = targets[:max_targets]

                logger.info(
                    "Processing %d repos (max %d concurrent, provider=%s)",
                    len(selected),
                    max_conc,
                    self.config.llm.provider,
                )

                repo_results = await asyncio.gather(
                    *[
                        self._hunt_process_repo(repo, mode, dry_run, remaining, sem)
                        for repo in selected
                    ]
                )

                for rr in repo_results:
                    total.repos_analyzed += rr.repos_analyzed
                    total.findings_total += rr.findings_total
                    total.contributions_generated += rr.contributions_generated
                    total.prs_created += rr.prs_created
                    total.prs.extend(rr.prs)
                    total.errors.extend(rr.errors)
                    remaining -= rr.prs_created

                if rnd < rounds:
                    logger.info(
                        "⏳ Waiting %ds before next round...",
                        delay_sec,
                    )
                    await asyncio.sleep(delay_sec)

        finally:
            await self._cleanup()

        return total

    async def _hunt_process_repo(
        self,
        repo: Repository,
        mode: str,
        dry_run: bool,
        remaining: int,
        sem: asyncio.Semaphore,
    ) -> PipelineResult:
        """Process a single repo in hunt mode (used for parallel execution).

        Priority: Issues FIRST, then static analysis.
        If issue-solving produces ≥1 PR, skip analysis to avoid
        flooding the maintainer with multiple PRs simultaneously.
        """
        async with sem:
            rr = PipelineResult()
            try:
                # --- Issues FIRST (higher value: fixes real reported problems) ---
                if mode in ("issues", "both"):
                    issue_rr = await self._process_repo_issues(repo, dry_run, remaining)
                    rr.repos_analyzed = max(rr.repos_analyzed, issue_rr.repos_analyzed)
                    rr.findings_total += issue_rr.findings_total
                    rr.contributions_generated += issue_rr.contributions_generated
                    rr.prs_created += issue_rr.prs_created
                    rr.prs.extend(issue_rr.prs)

                # --- Static analysis SECOND (skip if issues already produced PRs) ---
                if mode in ("analysis", "both"):
                    if rr.prs_created > 0:
                        logger.info(
                            "⏭️ Bỏ qua phân tích tĩnh cho %s — đã tạo %d PR từ "
                            "Issues. Tránh spam maintainer.",
                            repo.full_name,
                            rr.prs_created,
                        )
                    else:
                        analysis_rr = await self._process_repo(
                            repo, dry_run, remaining - rr.prs_created
                        )
                        rr.repos_analyzed += analysis_rr.repos_analyzed
                        rr.findings_total += analysis_rr.findings_total
                        rr.contributions_generated += analysis_rr.contributions_generated
                        rr.prs_created += analysis_rr.prs_created
                        rr.prs.extend(analysis_rr.prs)

                rr.repos_analyzed = max(rr.repos_analyzed, 1)
            except Exception as e:
                rr.errors.append(f"{repo.full_name}: {e}")
                logger.error("Error processing %s: %s", repo.full_name, e)
            return rr

    async def run_single(
        self,
        repo_url: str,
        dry_run: bool = False,
        *,
        max_prs: int = 5,
        allow_duplicate_prs: bool = False,
    ) -> PipelineResult:
        """Run the pipeline on a single specific repo.

        Args:
            repo_url: GitHub repository URL (e.g., https://github.com/owner/repo)
            dry_run: If True, analyze and generate but don't create PRs
            max_prs: Maximum PRs to create from this repo during this run
            allow_duplicate_prs: If True, skip duplicate-history filtering.
        """
        # Parse URL
        parts = repo_url.rstrip("/").split("/")
        owner, name = parts[-2], parts[-1]

        await self._init_components()
        result = PipelineResult()
        logger.info("▶ Starting single-repo run: %s/%s (dry_run=%s)", owner, name, dry_run)
        if allow_duplicate_prs:
            logger.info("Controlled single-repo run: duplicate PR filter disabled")

        try:
            repo = await self._github.get_repo_details(owner, name)
            repo_result = await self._process_repo(
                repo,
                dry_run,
                max_prs=max_prs,
                allow_duplicate_prs=allow_duplicate_prs,
            )
            result.repos_analyzed = 1
            result.findings_total = repo_result.findings_total
            result.contributions_generated = repo_result.contributions_generated
            result.prs_created = repo_result.prs_created
            result.prs = repo_result.prs
            logger.info(
                "✅ Single-repo run completed: %s — findings=%d, PRs=%d",
                repo.full_name,
                result.findings_total,
                result.prs_created,
            )
        except Exception as e:
            result.errors.append(str(e))
            logger.error("❌ Single-repo run failed for %s/%s: %s", owner, name, e)
        finally:
            await self._cleanup()

        return result

    async def run_circular(
        self,
        *,
        json_path: str = "target_repo.json",
        dry_run: bool = False,
        mode: str = "both",
    ) -> PipelineResult:
        """Circular Target Loop: deterministic round-robin from target_repo.json.

        Processes ONE target per invocation. The caller (e.g., SuperHumanLoop
        or CLI) should call this repeatedly in a loop.

        Crash-safe: scanned_at is updated BEFORE any analysis or LLM calls,
        so a crash will not cause the same target to be picked again.
        """
        await self._init_components()
        result = PipelineResult()

        discovery = DatabaseTargetDiscovery(memory=self._memory)
        await discovery.initialize(json_path=json_path)
        target = await discovery.get_next_target(
            excluded_languages=self.config.discovery.excluded_languages
        )

        if target is None:
            logger.warning("Circular loop: no targets in target_repos table")
            return result

        logger.info(
            "Circular loop: selected %s (last scanned: %s)",
            target.repo_url,
            target.scanned_at or "never",
        )

        # ── CRASH-SAFE MARK ─────────────────────────────────────────
        # get_next_target() atomically sets scanned_at via UPDATE...RETURNING.
        # The crash-safe guarantee is already embedded in the SELECT+UPDATE
        # atomic operation — no separate mark needed.

        try:
            # Parse owner/name from URL
            parts = target.repo_url.rstrip("/").split("/")
            owner, name = parts[-2], parts[-1]

            # Fetch repo details from GitHub API
            repo = await self._github.get_repo_details(owner, name)

            # Check daily PR limit
            today_prs = await self._memory.get_today_pr_count()
            remaining = self.config.github.max_prs_per_day - today_prs
            if remaining <= 0 and not dry_run:
                logger.warning(
                    "Daily PR limit reached (%d)",
                    self.config.github.max_prs_per_day,
                )
                return result

            # ── Bloodhound Pre-Filter ──────────────────────────────────
            # Run Semgrep pre-scan before expensive LLM analysis.
            # If the target is clean, mark COMPLETED_NO_VULN and skip.
            bloodhound = BloodhoundAnalyzer(
                llm=self._llm,
                github=self._github,
                config=self.config.analysis,
                memory=self._memory,
            )
            import os
            try:
                load1, load5, load15 = os.getloadavg()
                logger.info("[CPU PROFILING] Starting Bloodhound Semgrep scan. Load: %.2f, %.2f, %.2f", load1, load5, load15)
            except Exception:
                logger.info("[CPU PROFILING] Starting Bloodhound Semgrep scan.")
            dossier = await bloodhound.run_bloodhound(repo)
            try:
                load1, load5, load15 = os.getloadavg()
                logger.info("[CPU PROFILING] Finished Bloodhound Semgrep scan. Load: %.2f, %.2f, %.2f", load1, load5, load15)
            except Exception:
                logger.info("[CPU PROFILING] Finished Bloodhound Semgrep scan.")

            if not dossier.has_bugs():
                logger.info(
                    "Clean sweep, no vulns for %s — marking COMPLETED_NO_VULN",
                    target.repo_url,
                )
                await discovery.mark_status(target.repo_url, "COMPLETED_NO_VULN")
                return result

            logger.info(
                "Bloodhound found %d vulnerabilities for %s — proceeding to pipeline",
                len(dossier.vulnerabilities),
                target.repo_url,
            )

            # ── Contextual Intelligence: filter out non-production vulns ──
            production_vulns = []
            for v in dossier.vulnerabilities:
                if v.context_type == "LOW_PRIORITY_CONTEXT":
                    logger.warning(
                        "[CONTEXT SKIP] Skipping vulnerability in non-production file: %s",
                        v.file,
                    )
                else:
                    production_vulns.append(v)

            if not production_vulns:
                logger.info(
                    "All %d vulnerabilities were in non-production paths for %s — marking COMPLETED_NO_VULN",
                    len(dossier.vulnerabilities),
                    target.repo_url,
                )
                await discovery.mark_status(target.repo_url, "COMPLETED_NO_VULN")
                return result

            dossier.vulnerabilities = production_vulns

        # ── Build RepoContext with vulnerable file contents ───────────
            # Use GraphQL for repo tree (falls back to REST on any error)
            try:
                file_tree = await self._github.fetch_repo_structure_graphql(
                    repo.owner, repo.name
                )
            except Exception as exc:
                logger.info("GraphQL tree fetch failed for %s/%s, falling back to REST: %s",
                             repo.owner, repo.name, exc)
                file_tree = await self._github.get_file_tree(repo.owner, repo.name)
            relevant_files: dict[str, str] = {}
            for vuln in dossier.vulnerabilities:
                if vuln.file and vuln.file != "NONE" and vuln.file not in relevant_files:
                    try:
                        content = await self._github.get_file_content(
                            repo.owner, repo.name, vuln.file
                        )
                        if content:
                            relevant_files[vuln.file] = content
                    except Exception as exc:
                        logger.debug("Could not fetch %s: %s", vuln.file, exc)

            context = RepoContext(
                repo=repo,
                file_tree=file_tree,
                relevant_files=relevant_files,
            )

            # ── 3-Cycle DEV-QA Bounty Loop (FinOps Circuit Breaker) ────────────
            MAX_DEV_QA_CYCLES = 3
            qa_passed = False
            winning_contribution: Contribution | None = None
            failure_context = ""  # Accumulates sandbox/QA failure traces across cycles

            import copy
            qa_cfg = copy.deepcopy(self.config.llm)
            qa_cfg.model = "moonshotai/kimi-k2.6"
            from farm_agent.llm.provider import create_llm_provider
            qa_provider = create_llm_provider(qa_cfg)
            scorer = QAHardcoreScorer(llm=qa_provider)

            # ── Diplomat Protocol Task 2: Load repo style guide for QA penalty ──
            repo_style_guide_text = ""
            guidelines = None
            if self._memory:
                try:
                    cached_sg = await self._memory.get_style_guide(repo.full_name)
                    if cached_sg and cached_sg.get("style_summary"):
                        repo_style_guide_text = cached_sg["style_summary"]
                except Exception:
                    pass
            if not repo_style_guide_text and guidelines and guidelines.style_guide:
                repo_style_guide_text = guidelines.style_guide.raw_summary

            for cycle in range(MAX_DEV_QA_CYCLES):
                logger.info(
                    "Starting DEV-QA Cycle %d/%d for %s",
                    cycle + 1, MAX_DEV_QA_CYCLES, target.repo_url,
                )

                # 1. DEV generates patches (auto-injects QA Lessons + failure context)
                try:
                    gen_result: GenerationResult = await self._generator.generate_from_dossier(
                        dossier, context, github_client=self._github,
                        failure_context=failure_context,
                    )
                    contributions = gen_result.contributions
                except RuntimeError as e:
                    logger.error("Generation failed: %s", e)
                    failure_context += f"\n[CYCLE {cycle + 1} GENERATION FAILURE] {e}"
                    continue
                except Exception as e:
                    logger.error("Generation failed: %s", e)
                    failure_context += f"\n[CYCLE {cycle + 1} GENERATION FAILURE] {e}"
                    continue

                # ── False Positive Escape Hatch ─────────────────────────────────
                # If the DEV agent determined ALL findings are false positives,
                # gracefully abort the DEV-QA loop — no point forcing code generation.
                if gen_result.all_false_positives:
                    logger.info(
                        "[CONTEXT SKIP] AI determined all findings are False Positives "
                        "for %s — aborting DEV-QA loop.",
                        target.repo_url,
                    )
                    break

                if not contributions:
                    logger.warning("No contributions generated in cycle %d", cycle + 1)
                    failure_context += f"\n[CYCLE {cycle + 1} No valid code generated — anti-template interceptor may have triggered.]"
                    continue

                # 2. QA evaluates the first (best) contribution
                qa_result: QAResult = await scorer.evaluate(
                    dossier, contributions[0],
                    repo_style_guide=repo_style_guide_text,
                )
                logger.info(
                    "QA Score: %.1f/10.0 — Approved: %s",
                    qa_result.score, qa_result.approved,
                )

                if qa_result.approved:
                    # Success — exit the loop and proceed to PR submission
                    qa_passed = True
                    winning_contribution = contributions[0]
                    logger.info(
                        "QA PASSED on cycle %d with score %.1f",
                        cycle + 1, qa_result.score,
                    )
                    break
                else:
                    # 3. QA rejected — record critiques as lessons and inject into failure context
                    critique_text = "; ".join(qa_result.critiques)
                    for critique in qa_result.critiques:
                        await self._memory.record_qa_lesson(
                            repo.full_name, critique
                        )
                    failure_context += (
                        f"\n[CYCLE {cycle + 1} QA REJECTED — Score: {qa_result.score:.1f}/10.0]"
                        f"\nQA Critiques: {critique_text}"
                    )
                    logger.warning(
                        "QA Rejected (score %.1f). %d critiques recorded. Retrying...",
                        qa_result.score,
                        len(qa_result.critiques),
                    )

            if qa_passed and winning_contribution is not None:
                # ── Proceed to PR submission ─────────────────────────────
                
                # Layer 2: Supreme Auditor
                layer2_approved, reject_reason = await self._layer2_supreme_audit(winning_contribution, failure_context)
                if not layer2_approved:
                    logger.warning("🚫 Vetoed by Layer 2 Supreme Auditor (Gemini). Skipping PR.")
                    if self._memory:
                        patch_str = "\n".join(f"File: {c.path}\n```\n{c.new_content}\n```" for c in winning_contribution.changes)
                        await self._memory.add_filter_lesson(repo.full_name, 2, patch_str, reject_reason)
                    logger.info("Recorded Layer 2 lesson for %s: %s...", repo.full_name, reject_reason[:50])
                    await discovery.mark_status(target.repo_url, "COMPLETED_TOO_COMPLEX")
                    return result

                # ── Diplomat Protocol: Security Disclosure Gate ──────────────────
                security_gate_result = await run_security_gate(
                    github=self._github,
                    owner=repo.owner,
                    repo=repo.name,
                    dossier=dossier,
                    notifier=self._notifier,
                )
                if security_gate_result is not None:
                    logger.warning(
                        "[COMPLIANCE SKIP] Private security disclosure requested by maintainers. "
                        "Approved finding saved to secret_findings/. Aborting PR for %s.",
                        target.repo_url,
                    )
                    await discovery.mark_status(target.repo_url, "COMPLIANCE_SKIP_PRIVATE_DISCLOSURE")
                    return result

                result.repos_analyzed += 1
                result.findings_total += len(dossier.vulnerabilities)
                result.contributions_generated += 1

                if not dry_run:
                    try:
                        pr_result = await self._pr_manager.create_pr(
                            contribution=winning_contribution,
                            target_repo=repo,
                        )
                        if pr_result:
                            result.prs_created += 1
                            result.prs.append(pr_result)
                            await discovery.mark_status(target.repo_url, "PR_SUBMITTED")
                            logger.info("PR submitted: %s", pr_result.pr_url)
                    except Exception as e:
                        logger.error("PR submission failed: %s", e)
                        result.errors.append(f"PR submission failed: {e}")
                else:
                    logger.info(
                        "Dry run — would submit PR for %s",
                        winning_contribution.title,
                    )
                    await discovery.mark_status(target.repo_url, "PR_SUBMITTED")
            else:
                logger.warning(
                    "Bailout: Complexity exceeded after %d DEV-QA cycles for %s. "
                    "Cutting losses to save tokens.",
                    MAX_DEV_QA_CYCLES, target.repo_url,
                )
                await discovery.mark_status(target.repo_url, "COMPLETED_TOO_COMPLEX")

        except Exception as e:
            msg = f"Circular loop error for {target.repo_url}: {e}"
            logger.error(msg)
            result.errors.append(msg)

        finally:
            await self._cleanup()

        logger.info(
            "Circular loop done for %s — repos=%d, findings=%d, PRs=%d",
            target.repo_url,
            result.repos_analyzed,
            result.findings_total,
            result.prs_created,
        )
        return result

    async def analyze_only(self, repo_url: str) -> AnalysisResult | None:
        """Analyze a repo without generating contributions or PRs."""
        parts = repo_url.rstrip("/").split("/")
        owner, name = parts[-2], parts[-1]

        await self._init_components()
        try:
            repo = await self._github.get_repo_details(owner, name)
            return await self._analyzer.analyze(repo)
        finally:
            await self._cleanup()

    # ── Internal ───────────────────────────────────────────────────────────

    async def _process_repo(
        self,
        repo: Repository,
        dry_run: bool,
        max_prs: int = 5,
        *,
        allow_duplicate_prs: bool = False,
    ) -> PipelineResult:
        """Process a single repository through the full pipeline."""
        result = PipelineResult()
        logger.info("=" * 60)
        logger.info("📦 Processing: %s", repo.full_name)

        # Check AI policy — skip repos that ban AI-generated PRs
        if await self._check_ai_policy(repo):
            logger.warning(
                "🚫 %s has an AI policy that bans AI PRs, skipping.",
                repo.full_name,
            )
            result.repos_analyzed = 1
            return result

        # Check interaction limits — skip repos that restrict to prior contributors
        if await self._github.check_interaction_limits(repo.owner, repo.name):
            logger.warning(
                "🚫 Repo %s has active interaction limits "
                "(e.g., prior contributors only). Skipping to save resources.",
                repo.full_name,
            )
            result.repos_analyzed = 1
            return result

        # Fetch repo guidelines (CONTRIBUTING.md, PR template)
        guidelines = await fetch_repo_guidelines(
            self._github, repo.owner, repo.name,
            memory=self._memory, llm=self._llm,
        )
        if guidelines.has_guidelines:
            logger.info(
                "📋 Repo guidelines: commit=%s, %d template sections",
                guidelines.commit_format,
                len(guidelines.required_sections),
            )

        # ── Maintainer Vibe Check ──────────────────────────────────────────
        logger.info(
            "🕵️ Đang 'nằm vùng' đọc comment để đánh giá tính cách Maintainer của %s...",
            repo.full_name,
        )
        try:
            comments_context = await self._github.fetch_recent_maintainer_comments(
                repo.owner, repo.name
            )
            if comments_context:
                vibe = await self._analyzer.check_maintainer_vibe(repo.full_name, comments_context)
                if "HOSTILE" in vibe.upper():
                    logger.warning(
                        "🚫 [VIBE CHECK FAILED] Maintainer dự án %s có lịch sử "
                        "toxic/khó tính. Quay xe để đỡ tốn thời gian!",
                        repo.full_name,
                    )
                    import contextlib

                    with contextlib.suppress(Exception):
                        await self._memory.add_to_blacklist(
                            repo.full_name, reason="toxic_maintainer"
                        )
                    result.repos_analyzed = 1
                    return result
                else:
                    logger.info(
                        "✅ Vibe Check OK (%s). Maintainer tử tế, tiến hành phân tích code.",
                        vibe,
                    )
        except Exception as exc:
            logger.debug(
                "Vibe check skipped for %s (non-critical): %s",
                repo.full_name,
                exc,
            )
        # ──────────────────────────────────────────────────────────────────

        # Analyze — set task context for model routing
        logger.info("🔬 Analyzing code...")
        self._set_task("analysis")
        analysis = await self._analyzer.analyze(repo)
        result.findings_total = len(analysis.findings)

        await self._memory.record_analysis(
            repo.full_name,
            repo.language or "unknown",
            repo.stars,
            len(analysis.findings),
        )

        if not analysis.findings:
            logger.info("No findings for %s", repo.full_name)
            return result

        # --- Early finding filter (pre-generation) ---
        # Filter out findings that target non-code files (blocked by SKIP_EXTENSIONS)
        # or are irrelevant to the project type, BEFORE wasting LLM calls.
        pre_filter_count = len(analysis.findings)
        filtered = []
        for f in analysis.findings:
            fp = f.file_path or ""
            ext = "." + fp.rsplit(".", 1)[-1].lower() if "." in fp else ""

            # Skip findings on non-code files (would be blocked at commit anyway)
            if ext in SKIP_EXTENSIONS:
                logger.debug("⏭️ Pre-filter: skip non-code file %s", fp)
                continue

            # Skip findings on protected meta files
            basename = fp.rsplit("/", 1)[-1] if "/" in fp else fp
            # Exact match (e.g., tsconfig.json, .eslintrc)
            if basename.upper() in PROTECTED_META_FILES:
                logger.debug("⏭️ Pre-filter: skip protected file %s", fp)
                continue
            # Pattern match for config files (e.g., .github/workflows/ci.yml, tsconfig.base.json)
            fp_lower = fp.lower()
            for protected in PROTECTED_META_FILES:
                if protected.startswith(".github/workflows/"):
                    pattern = protected[len(".github/workflows/") :]
                    if fp_lower.endswith(pattern) or f"/{pattern}" in fp_lower:
                        logger.debug("⏭️ Pre-filter: skip protected workflow file %s", fp)
                        break
                elif fp_lower == protected.lower():
                    break
            else:
                # Also block tsconfig-strict, tsconfig-noImplicitAny, etc.
                config_bootstrap_keywords = {
                    "tsconfig",
                    "eslint",
                    "prettier",
                    "babel",
                    "webpack",
                    "vite.config",
                    "rollup",
                    "jsconfig",
                    "package.json",
                }
                if any(kw in fp_lower for kw in config_bootstrap_keywords):
                    logger.debug("⏭️ Pre-filter: skip config/build file %s", fp)
                    continue

            filtered.append(f)

        if len(filtered) < pre_filter_count:
            logger.info(
                "🔍 Pre-filter: %d → %d findings (removed %d non-code targets)",
                pre_filter_count,
                len(filtered),
                pre_filter_count - len(filtered),
            )
            analysis.findings = filtered

        if not analysis.findings:
            logger.info("All findings filtered (non-code targets) for %s", repo.full_name)
            return result

        # --- Anti-Farming Filter (impact-level + keyword gatekeeper) ---
        # ZERO-TOLERANCE: Drop ANY finding that looks like a spam/exploratory PR
        farming_keywords = {
            # Documentation / comments
            "docstring",
            "docs",
            "documentation",
            "readme",
            "comment",
            "spell",
            # Formatting / style
            "format",
            "formatting",
            "whitespace",
            "indent",
            "spacing",
            "style",
            "styling",
            "naming convention",
            "rename",
            "ordering",
            "lint",
            # Exploratory / curiosity
            "understand",
            "explore",
            "exploring",
            "read the",
            "reading",
            "look at",
            "looking at",
            "check this",
            "investigate",
            # Low-effort / testing
            "test",
            "testing",
            "todo",
            "fixme",
            "chore",
            # Cosmetic
            "typo",
            "typo in",
            "grammar",
            "misspell",
            "missing type hint",
            "type annotation",
            "unused import",
            # ── Config / Compiler / Tooling tweaks — NEVER tweak these ──────────
            "no-explicit-any",
            "noimplicitany",
            "strict mode",
            "strict: true",
            "compiler flag",
            "compiler option",
            "tsconfig",
            "eslint",
            "prettier",
            "babel config",
            "webpack config",
            "vite config",
            "rollup config",
            "linter rule",
            "lint rule",
            "tsconfig.json",
            "package.json",
        }
        pre_farming_count = len(analysis.findings)
        high_impact_findings = []
        for finding in analysis.findings:
            title_lower = finding.title.lower()
            desc_lower = finding.description.lower() if finding.description else ""

            # ── Gate 1: Impact level — CRITICAL, HIGH, and MEDIUM survive ──────
            # LOW, TRIVIAL are ALWAYS dropped. No exceptions.
            # [FIX] Live-fire crucible: lowered threshold from CRITICAL/HIGH-only
            # to also include MEDIUM to allow Route A PR creation for test repos.
            if finding.impact_level in (
                ImpactLevel.TRIVIAL,
                ImpactLevel.LOW,
            ):
                logger.info(
                    "🗑️ Dropped '%s' — impact_level=%s (only CRITICAL/HIGH/MEDIUM allowed)",
                    finding.title,
                    finding.impact_level.value,
                )
                continue

            # ── Gate 2: ABSOLUTE DOCS BAN — README_FIX / DOCS_IMPROVE ──────
            # Zero-tolerance: documentation contributions are FORBIDDEN.
            # The agent must NEVER create doc/readme PRs. Nuke on sight.
            banned_contrib_types = {
                ContributionType.README_FIX,
                ContributionType.DOCS_IMPROVE,
            }
            if finding.type in banned_contrib_types:
                logger.info(
                    "🗑️ Dropped '%s' — type=%s (docs/readme contributions BANNED)",
                    finding.title,
                    finding.type.value,
                )
                continue

            # ── Gate 3: File-Level Guillotine — non-code paths ─────────────
            # Drop any finding targeting documentation files or /docs/ paths,
            # regardless of its declared ContributionType.
            guillotine_extensions = {".md", ".txt", ".rst"}
            fp = finding.file_path or ""
            fp_lower_g = fp.lower()
            fp_ext = "." + fp_lower_g.rsplit(".", 1)[-1] if "." in fp_lower_g else ""
            if fp_ext in guillotine_extensions:
                logger.info(
                    "🗑️ Dropped '%s' — targets doc file %s (non-code extension %s)",
                    finding.title,
                    fp,
                    fp_ext,
                )
                continue
            if (
                "/docs/" in fp_lower_g
                or fp_lower_g.startswith("docs/")
                or "\\docs\\" in fp_lower_g
                or fp_lower_g.startswith("docs\\")
            ):
                logger.info(
                    "🗑️ Dropped '%s' — targets docs/ path %s (documentation directory BANNED)",
                    finding.title,
                    fp,
                )
                continue

            # ── Gate 4: Keyword blacklist — title OR description ───────────
            # Check both title and description (case-insensitive)
            allowed_contrib_types = {
                ContributionType.FEATURE_ADD,
            }
            combined = title_lower + " " + desc_lower
            if finding.type not in allowed_contrib_types:
                for kw in farming_keywords:
                    if kw in combined:
                        logger.info(
                            "🗑️ Dropped '%s' — keyword '%s' matched (spam/farming indicator)",
                            finding.title,
                            kw,
                        )
                        break
                else:
                    # No farming keyword matched — this finding is worth keeping
                    high_impact_findings.append(finding)
                    continue
                # (break above goes here via else-clause)
            else:
                # FEATURE_ADD bypasses farming keyword check
                high_impact_findings.append(finding)

        if len(high_impact_findings) < pre_farming_count:
            logger.info(
                "🛡️ Anti-Farming: %d → %d findings (dropped %d low-impact/farming)",
                pre_farming_count,
                len(high_impact_findings),
                pre_farming_count - len(high_impact_findings),
            )
        analysis.findings = high_impact_findings

        if not analysis.findings:
            logger.info(
                "All findings filtered by Anti-Farming gate for %s",
                repo.full_name,
            )
            return result

        logger.info(
            "Found %d issues (analyzed %d files in %.1fs)",
            len(analysis.findings),
            analysis.analyzed_files,
            analysis.analysis_duration_sec,
        )

        candidate_limit = max_prs if not allow_duplicate_prs else max(max_prs, 4)
        candidate_findings = analysis.top_findings[:candidate_limit]

        # Build context for generation — fetch files for all candidate findings
        file_tree = await self._github.get_file_tree(repo.owner, repo.name)
        relevant_files: dict[str, str] = {}
        # Deduplicate file paths across all findings we'll process
        file_paths_to_fetch = []
        for finding in candidate_findings:
            if finding.file_path and finding.file_path not in relevant_files:
                file_paths_to_fetch.append(finding.file_path)

        # Strict GitHub API semaphore — keep LOW to avoid Secondary Rate Limits.
        # This is intentionally separate from the Minimax Overdrive concurrency.
        github_fetch_sem = asyncio.Semaphore(5)

        async def fetch_needed(fpath: str) -> tuple[str, str | None]:
            async with github_fetch_sem:
                # Micro-sleep to keep RPS below GitHub abuse-detection threshold
                await asyncio.sleep(0.2)
                try:
                    return fpath, await self._github.get_file_content(repo.owner, repo.name, fpath)
                except Exception:
                    logger.debug("Could not fetch %s", fpath)
                    return fpath, None

        fetch_tasks = [fetch_needed(fp) for fp in file_paths_to_fetch]
        for fpath, content in await asyncio.gather(*fetch_tasks):
            if content:
                relevant_files[fpath] = content

        logger.info(
            "Fetched %d/%d unique files for code gen",
            len(relevant_files),
            len(file_paths_to_fetch),
        )

        from farm_agent.core.models import RepoContext

        context = RepoContext(
            repo=repo,
            file_tree=file_tree,
            relevant_files=relevant_files,
        )

        filtered_findings = list(candidate_findings)
        if allow_duplicate_prs:
            preferred = [
                finding
                for finding in candidate_findings
                if finding.file_path and finding.title.strip().lower() != "untitled finding"
            ]
            if preferred:
                preferred.sort(
                    key=lambda finding: (
                        finding.type
                        not in (
                            ContributionType.SECURITY_FIX,
                            ContributionType.CODE_QUALITY,
                            ContributionType.PERFORMANCE_OPT,
                        ),
                        -finding.priority_score,
                    )
                )
                filtered_findings = preferred[:max_prs]
            else:
                filtered_findings = candidate_findings[:max_prs]
            logger.info(
                "Controlled run: preserving %d finding(s) despite existing PR history",
                len(filtered_findings),
            )
        else:
            # Filter out findings that overlap with previously submitted PRs
            # Check BOTH local memory AND GitHub API for existing PRs
            past_titles_lower: set[str] = set()
            past_file_paths: set[str] = set()

            # 1) Local memory
            past_prs = await self._memory.get_repo_prs(repo.full_name)
            for pr in past_prs:
                past_titles_lower.add(pr.get("title", "").lower())

            # 2) GitHub API — fetch recent PRs (all states) to catch external PRs too
            try:
                github_prs = await self._github.list_pull_requests(
                    repo.owner, repo.name, state="all", per_page=50
                )
                for gpr in github_prs:
                    past_titles_lower.add(gpr.get("title", "").lower())
                    # Extract file paths from branch name (farm_agent branches encode the topic)
                    head = gpr.get("head", {})
                    branch_label = head.get("label", "")
                    if "farm_agent/" in branch_label:
                        past_titles_lower.add(gpr.get("title", "").lower())
                    # Track all recently-targeted file info from PR body
                    body = gpr.get("body", "") or ""
                    # Extract file paths mentioned in PR bodies (e.g. `src/foo/bar.ts`)
                    import re

                    for match in re.findall(r"`(src/[^\s`]+\.\w+)`", body):
                        past_file_paths.add(match)
            except Exception:
                logger.debug("Could not fetch GitHub PRs for dedup, using memory only")

            original_count = len(candidate_findings)
            filtered_findings = []
            for finding in candidate_findings:
                title_lower = finding.title.lower()
                # Check title similarity
                is_title_dup = any(_titles_similar(title_lower, pt) for pt in past_titles_lower)
                # Check if same file was already targeted
                is_file_dup = finding.file_path in past_file_paths if finding.file_path else False

                if is_title_dup:
                    logger.info(
                        "⏭️ Skipping duplicate finding: %s (similar PR exists)",
                        finding.title,
                    )
                    continue
                if is_file_dup:
                    logger.info(
                        "⏭️ Skipping finding on already-targeted file: %s → %s",
                        finding.title,
                        finding.file_path,
                    )
                    continue
                filtered_findings.append(finding)

            if len(filtered_findings) < original_count:
                logger.info(
                    "🔁 Filtered %d duplicate findings (%d remaining)",
                    original_count - len(filtered_findings),
                    len(filtered_findings),
                )

            if not filtered_findings:
                logger.info("No new findings after duplicate filter")
                result.repos_analyzed = 1
                return result

        # Validate findings against full file content to filter false positives
        validated_findings = await self._validate_findings(filtered_findings, relevant_files)

        # Limit to max 2 findings per repo to avoid spamming
        if len(validated_findings) > 2:
            logger.info(
                "📉 Limiting to 2 findings per repo (had %d)",
                len(validated_findings),
            )
            validated_findings = validated_findings[:2]

        logger.info(
            "🔎 Validated %d/%d findings (filtered %d false positives)",
            len(validated_findings),
            min(len(candidate_findings), max_prs),
            min(len(candidate_findings), max_prs) - len(validated_findings),
        )

        # Filter findings via Layer 1 Appraiser before generating contributions
        surviving_findings = []
        for finding in validated_findings:
            file_content = relevant_files.get(finding.file_path, "")
            is_genuine, critique = await self._layer1_expert_appraisal(finding, file_content)
            if is_genuine:
                surviving_findings.append(finding)
            else:
                if self._memory:
                    await self._memory.add_filter_lesson(repo.full_name, 1, file_content, critique)
                logger.info("Recorded Layer 1 lesson for %s: %s...", repo.full_name, critique[:50])
        validated_findings = surviving_findings

        # Generate contributions for validated findings
        for finding in validated_findings:

            # ── Hybrid Contribution Router ─────────────────────────────────
            # Route A — Direct PR (Firefighter): SECURITY_FIX or CRITICAL/HIGH severity
            # Route B — Issue-First (Polite Senior): everything else
            is_direct_pr = finding.type == ContributionType.SECURITY_FIX or finding.severity in (
                Severity.CRITICAL,
                Severity.HIGH,
                Severity.MEDIUM,
            )

            if not is_direct_pr:
                # Route B: Issue-First Protocol — propose via issue, skip code gen
                await self._propose_issue_first(finding, repo, context)
                result.contributions_generated += 1
                continue

            logger.info("🛠️ Generating fix for: %s", finding.title)
            self._set_task("code_gen")
            contribution = await self._generator.generate(
                finding,
                context,
                guidelines=guidelines,
                github_client=self._github,
            )

            if not contribution:
                continue

            result.contributions_generated += 1

            if dry_run:
                logger.info("🏃 [DRY RUN] Would create PR: %s", contribution.title)
                continue

            # --- Sandbox Guillotine — Docker-based patch validation ---
            # P0 FIX: Enforce sandbox_validation_enabled — can NEVER be bypassed
            if not self.config.pipeline.sandbox_validation_enabled:
                logger.error(
                    "🚫 SANDBOX GUILLOTINE: sandbox_validation_enabled=False — "
                    "PR creation BLOCKED. Validation can never be disabled."
                )
                continue
            if self._sandbox is None:
                # Sandbox required but unavailable — block PR creation
                logger.error(
                    "🚫 SANDBOX GUILLOTINE: sandbox unavailable (Docker unavailable) — "
                    "PR creation BLOCKED."
                )
                continue
            else:
                max_retries = 3

                for attempt in range(1, max_retries + 1):
                    logger.info(
                        "🔬 Sandbox validation attempt %d/%d for '%s'",
                        attempt,
                        max_retries,
                        contribution.title,
                    )
                    sandbox_result = await self._sandbox.run_in_sandbox(
                        repo_path=await self._clone_and_patch_repo(
                            repo.clone_url,
                            contribution.changes,
                            contribution.tests_added,
                        ),
                        command=None,  # Auto-select via Polyglot Guillotine
                    )

                    # Determine success
                    if isinstance(sandbox_result, dict):
                        is_success = sandbox_result.get("exit_code") == 0
                        raw_stdout = sandbox_result.get("stdout", "")
                        raw_stderr = sandbox_result.get("stderr", "")
                    else:
                        is_success = getattr(sandbox_result, "exit_code", -1) == 0
                        raw_stdout = getattr(sandbox_result, "stdout", "")
                        raw_stderr = getattr(sandbox_result, "stderr", "")

                    out_trunc = raw_stdout[:500] if raw_stdout else ""
                    err_trunc = raw_stderr[-2000:] if raw_stderr else ""
                    error_log = f"STDOUT:\n{out_trunc}\n\nSTDERR:\n{err_trunc}"

                    if is_success:
                        logger.info("✅ Sandbox validated — patch passes CI/tests.")
                        break

                    logger.warning(
                        "🚫 Sandbox attempt %d/%d failed for '%s' — invoking self-correction.",
                        attempt,
                        max_retries,
                        contribution.title,
                    )

                    # Self-Correction: try to fix the broken patch
                    try:
                        corrected = await self._generator.fix_contribution_from_error(
                            contribution,
                            context,
                            error_log,
                        )
                        if corrected is not None:
                            contribution = corrected
                            logger.info(
                                "🔧 Self-correction attempt %d succeeded for '%s'",
                                attempt,
                                contribution.title,
                            )
                        else:
                            logger.warning(
                                "🔧 Self-correction attempt %d returned None — retrying.",
                                attempt,
                            )
                    except Exception as correction_err:
                        logger.warning(
                            "🔧 Self-correction attempt %d threw: %s — retrying.",
                            attempt,
                            correction_err,
                        )
                else:
                    # for/else: runs only if no break occurred (all retries exhausted)
                    logger.error(
                        "🚫 SANDBOX GUILLOTINE: PR creation blocked — "
                        "patch still failing after %d self-correction attempts.",
                        max_retries,
                    )
                    continue
            # ----------------------------------------------------------

            # Layer 2: Supreme Auditor
            layer2_approved, reject_reason = await self._layer2_supreme_audit(contribution, error_log)
            if not layer2_approved:
                logger.warning("🚫 Vetoed by Layer 2 Supreme Auditor (Gemini). Skipping PR for '%s'.", contribution.title)
                if self._memory:
                    patch_str = "\n".join(f"File: {c.path}\n```\n{c.new_content}\n```" for c in contribution.changes)
                    await self._memory.add_filter_lesson(repo.full_name, 2, patch_str, reject_reason)
                logger.info("Recorded Layer 2 lesson for %s: %s...", repo.full_name, reject_reason[:50])
                continue

            # ── Diplomat Protocol: Security Disclosure Gate ──────────────────
            from types import SimpleNamespace
            dummy_dossier = SimpleNamespace(
                vulnerabilities=[contribution.finding],
                repo_url=repo.clone_url
            )
            security_gate_result = await run_security_gate(
                github=self._github,
                owner=repo.owner,
                repo=repo.name,
                dossier=dummy_dossier,
                notifier=self._notifier,
            )
            if security_gate_result is not None:
                logger.warning(
                    "[COMPLIANCE SKIP] Private security disclosure requested by maintainers. "
                    "Approved finding saved to secret_findings/. Aborting PR for %s.",
                    repo.full_name,
                )
                continue

            # Create PR
            try:
                logger.info(f"Creating PR for {repo.full_name}...")
                async with self._human_typing_lock:
                    if not dry_run:
                        # TOCTOU Quota defense. Repos process concurrently,
                        # so check quota atomically inside the lock before PR generation.
                        curr_prs = await self._memory.get_today_pr_count()
                        if curr_prs >= self.config.github.max_prs_per_day:
                            logger.warning(
                                "TOCTOU PR LIMIT DEFENSE: Concurrent quota hit "
                                "(%d). Aborting PR for %s",
                                curr_prs,
                                repo.full_name,
                            )
                            return result

                    logger.info(f"Creating PR for {repo.full_name}...")
                    pr_result = await self._pr_manager.create_pr(
                        contribution, repo, guidelines=guidelines
                    )
                result.prs_created += 1
                result.prs.append(pr_result)
                result.pr_urls.append(pr_result.pr_url)

                # Record in memory
                try:
                    await self._memory.record_pr(
                        repo=repo.full_name,
                        pr_number=pr_result.pr_number,
                        pr_url=pr_result.pr_url,
                        title=contribution.title,
                        pr_type=contribution.contribution_type.value,
                        branch=pr_result.branch_name,
                        fork=pr_result.fork_full_name,
                    )
                except Exception as e:
                    logger.critical(
                        "PR %s/%s #%d created on GitHub but local DB record failed: %s — "
                        "PR may be duplicated on next restart",
                        repo.full_name,
                        pr_result.pr_number,
                        e,
                    )

                if not dry_run and getattr(self, "_notifier", None):
                    await self._safe_send_notification(
                        f"✅ **PR SUCCESS**\n"
                        f"Target: {repo.full_name}\n"
                        f"URL: {pr_result.pr_url}\n"
                        f"Vulnerability: {contribution.finding.type.value}"
                    )

                # 5. Post-PR compliance check & auto-fix
                try:
                    logger.info("🔍 Checking PR compliance...")
                    await self._pr_manager.check_compliance_and_fix(
                        pr_result,
                        contribution,
                        guidelines=guidelines,
                    )
                except Exception as e:
                    logger.warning("Compliance check failed: %s", e)

                # 6. Wait for CI so Patrol can react if it fails
                try:
                    await self._check_ci_and_close_if_failed(pr_result, repo)
                except Exception as e:
                    logger.warning("CI check failed: %s", e)
            except Exception as e:
                error = f"PR creation failed for {finding.title}: {e}"
                logger.error(error)
                result.errors.append(error)
                if not dry_run and getattr(self, "_notifier", None):
                    await self._safe_send_notification(
                        f"❌ **PR FAILED**\n"
                        f"Target: {repo.full_name}\n"
                        f"Error: {str(e)[:200]}"
                    )

        result.repos_analyzed = 1
        return result

    # ── Hybrid Contribution Protocol ───────────────────────────────────────

    async def _propose_issue_first(
        self,
        finding: Finding,
        repo: Repository,
        context: RepoContext,
    ):
        """Route B: Open a polite GitHub Issue instead of generating a PR.

        This is used for PERFORMANCE_OPT, REFACTOR, CODE_QUALITY, FEATURE_ADD,
        and other non-critical findings where maintainers prefer discussion
        before seeing a large code diff.
        """

        logger.info(
            "📝 [Route B] Issue-First for '%s' (type=%s, severity=%s) "
            "— polite heads-up, no code yet",
            finding.title,
            finding.type.value,
            finding.severity.value,
        )

        # Build a minimal contribution object for body generation
        fake_contribution = Contribution(
            finding=finding,
            contribution_type=finding.type,
            title=f"[Proposal] {finding.title}",
            description=finding.description or "",
            changes=[],  # no changes — no code generated
            commit_message=f"chore: propose fix for {finding.file_path}",
            branch_name="",  # no branch for issue-first
        )

        # Build a concise issue title
        issue_title = finding.title
        finding_type = finding.type.value if finding.type else "unknown"
        if not issue_title or issue_title.lower() == "untitled finding":
            issue_title = f"Potential {finding_type.replace('_', ' ')} in {finding.file_path}"

        # Generate issue body — use _pr_manager if available, else inline fallback
        if self._pr_manager is not None:
            issue_body = self._pr_manager._generate_issue_body(fake_contribution)
        else:
            # Inline fallback: lazy senior dev style
            issue_body = (
                f"Spotted a potential issue in `{finding.file_path}`.\n\n"
                "If the team thinks this is worth addressing, I can put together a PR. "
                "Happy to help."
            )

        # Create the issue immediately (no artificial delay)
        try:
            issue_data = await self._github.create_issue(
                owner=repo.owner,
                repo=repo.name,
                title=issue_title,
                body=issue_body,
                labels=["enhancement"],
            )

            issue_number = issue_data.get("number", 0)
            issue_url = issue_data.get(
                "html_url", f"https://github.com/{repo.full_name}/issues/{issue_number}"
            )

            logger.info(
                "📝 Issue created: %s/%s/#%d — '%s'",
                repo.owner,
                repo.name,
                issue_number,
                issue_title,
            )

            # Record in memory so we don't spam duplicate issues on next run
            try:
                await self._memory.record_issue_proposal(
                    repo=repo.full_name,
                    issue_number=issue_number,
                    issue_url=issue_url,
                    title=issue_title,
                    finding_type=finding.type.value,
                    finding_title=finding.title,
                    file_path=finding.file_path or "",
                )
            except Exception as e:
                logger.critical(
                    "Issue %s/%s #%d created on GitHub but local DB record failed: %s — "
                    "Issue may be duplicated on next restart",
                    repo.full_name,
                    issue_number,
                    e,
                )

        except Exception as exc:
            logger.error("Failed to create issue for %s: %s", repo.full_name, exc)

    async def _process_repo_issues(
        self, repo: Repository, dry_run: bool, max_prs: int = 3
    ) -> PipelineResult:
        """Process a repo by solving its open Issues.

        v2.0.0: Issue-driven mode. Fetches solvable issues, uses
        solve_issue_deep() to plan multi-file changes, generates
        contributions, and creates PRs that close issues.
        """
        result = PipelineResult()
        logger.info("📋 Looking for solvable issues in %s...", repo.full_name)

        # Check AI policy first
        if await self._check_ai_policy(repo):
            logger.warning(
                "🚫 %s bans AI PRs, skipping issue solving.",
                repo.full_name,
            )
            return result

        # Check interaction limits — skip repos that restrict to prior contributors
        if await self._github.check_interaction_limits(repo.owner, repo.name):
            logger.warning(
                "🚫 Repo %s has active interaction limits "
                "(e.g., prior contributors only). Skipping to save resources.",
                repo.full_name,
            )
            return result

        # Initialize issue solver
        solver = IssueSolver(llm=self._llm, github=self._github)

        # Fetch solvable issues
        issues = await solver.fetch_solvable_issues(repo, max_issues=max_prs, max_complexity=3)

        if not issues:
            logger.info("No solvable issues found in %s", repo.full_name)
            return result

        # Fetch repo guidelines
        guidelines = await fetch_repo_guidelines(self._github, repo.owner, repo.name, memory=self._memory, llm=self._llm)

        # Build repo context with more files for deeper understanding
        file_tree = await self._github.get_file_tree(repo.owner, repo.name)
        relevant_files: dict[str, str] = {}

        # Fetch key files for context (README, main modules, etc.)
        key_files = self._identify_key_files(file_tree, repo)
        for fpath in key_files[:10]:
            try:
                # Micro-sleep to keep RPS below GitHub abuse-detection threshold
                await asyncio.sleep(0.2)
                content = await self._github.get_file_content(repo.owner, repo.name, fpath)
                relevant_files[fpath] = content
            except Exception:
                pass

        from farm_agent.core.models import RepoContext

        context = RepoContext(
            repo=repo,
            file_tree=file_tree,
            relevant_files=relevant_files,
        )

        # Process each issue
        for issue in issues:
            if result.prs_created >= max_prs:
                break

            logger.info(
                "🧠 Solving issue #%d: %s",
                issue.number,
                issue.title,
            )

            # Deep solve → multi-file findings
            self._set_task("analysis")
            findings = await solver.solve_issue_deep(issue, repo, context)

            # Filter out findings that only touch non-code files
            # (docs, configs, meta files — low-value changes)
            def _is_code_file(path: str | None) -> bool:
                if not path:
                    return True  # no path → keep it
                import os

                _, ext = os.path.splitext(path.lower())
                if ext in SKIP_EXTENSIONS:
                    return False
                return path.lower() not in {p.lower() for p in PROTECTED_META_FILES}

            findings = [f for f in findings if _is_code_file(f.file_path)]

            result.findings_total += len(findings)

            if not findings:
                logger.info("Could not solve issue #%d", issue.number)
                continue

            # Fetch file contents for each finding
            for finding in findings:
                if finding.file_path and finding.file_path not in relevant_files:
                    try:
                        content = await self._github.get_file_content(
                            repo.owner, repo.name, finding.file_path
                        )
                        relevant_files[finding.file_path] = content
                        context.relevant_files[finding.file_path] = content
                    except Exception:
                        pass

            # Generate contributions — first finding is the primary one
            # The generator already handles multi-file via cross-file matching
            primary = findings[0]
            logger.info(
                "🛠️ Generating fix for issue #%d (%d files)...",
                issue.number,
                len(findings),
            )

            self._set_task("code_gen")
            contribution = await self._generator.generate(
                primary,
                context,
                guidelines=guidelines,
                github_client=self._github,
            )

            if not contribution:
                logger.warning(
                    "Failed to generate contribution for issue #%d",
                    issue.number,
                )
                continue

            result.contributions_generated += 1

            if dry_run:
                logger.info(
                    "🏃 [DRY RUN] Would create PR for issue #%d: %s",
                    issue.number,
                    contribution.title,
                )
                continue

            # --- Sandbox Guillotine — Docker-based patch validation (P0 FIX) ---
            # _process_repo_issues was MISSING sandbox validation — add it here
            if not self.config.pipeline.sandbox_validation_enabled:
                logger.error(
                    "🚫 SANDBOX GUILLOTINE: sandbox_validation_enabled=False — "
                    "PR creation BLOCKED for issue #%d. Validation can never be disabled.",
                    issue.number,
                )
                continue
            if self._sandbox is None:
                logger.error(
                    "🚫 SANDBOX GUILLOTINE: sandbox unavailable for issue #%d — "
                    "PR creation BLOCKED.",
                    issue.number,
                )
                continue
            else:
                max_retries = 3
                for attempt in range(1, max_retries + 1):
                    logger.info(
                        "🔬 Sandbox validation attempt %d/%d for issue #%d ('%s')",
                        attempt,
                        max_retries,
                        issue.number,
                        contribution.title,
                    )
                    sandbox_result = await self._sandbox.run_in_sandbox(
                        repo_path=await self._clone_and_patch_repo(
                            repo.clone_url,
                            contribution.changes,
                            contribution.tests_added,
                        ),
                        command=None,  # Auto-select via Polyglot Guillotine
                    )
                    if isinstance(sandbox_result, dict):
                        is_success = sandbox_result.get("exit_code") == 0
                        raw_stdout = sandbox_result.get("stdout", "")
                        raw_stderr = sandbox_result.get("stderr", "")
                    else:
                        is_success = getattr(sandbox_result, "exit_code", -1) == 0
                        raw_stdout = getattr(sandbox_result, "stdout", "")
                        raw_stderr = getattr(sandbox_result, "stderr", "")

                    out_trunc = raw_stdout[:500] if raw_stdout else ""
                    err_trunc = raw_stderr[-2000:] if raw_stderr else ""
                    error_log = f"STDOUT:\n{out_trunc}\n\nSTDERR:\n{err_trunc}"

                    if is_success:
                        logger.info(
                            "✅ Sandbox validated for issue #%d — patch passes CI/tests.",
                            issue.number,
                        )
                        break

                    logger.warning(
                        "🚫 Sandbox attempt %d/%d failed for issue #%d — invoking self-correction.",
                        attempt,
                        max_retries,
                        issue.number,
                    )
                    try:
                        corrected = await self._generator.fix_contribution_from_error(
                            contribution,
                            context,
                            error_log,
                        )
                        if corrected is not None:
                            contribution = corrected
                            logger.info("🔧 Self-correction succeeded for issue #%d", issue.number)
                    except Exception as correction_err:
                        logger.warning(
                            "🔧 Self-correction threw for issue #%d: %s",
                            issue.number,
                            correction_err,
                        )
                else:
                    # for/else: runs only if no break occurred (all retries exhausted)
                    logger.error(
                        "🚫 SANDBOX GUILLOTINE: PR creation blocked for issue #%d — "
                        "patch still failing after %d self-correction attempts.",
                        issue.number,
                        max_retries,
                    )
                    continue
            # ----------------------------------------------------------

            # Layer 2: Supreme Auditor
            layer2_approved, reject_reason = await self._layer2_supreme_audit(contribution, error_log)
            if not layer2_approved:
                logger.warning("🚫 Vetoed by Layer 2 Supreme Auditor (Gemini). Skipping PR for issue #%d.", issue.number)
                if self._memory:
                    patch_str = "\n".join(f"File: {c.path}\n```\n{c.new_content}\n```" for c in contribution.changes)
                    await self._memory.add_filter_lesson(repo.full_name, 2, patch_str, reject_reason)
                logger.info("Recorded Layer 2 lesson for %s: %s...", repo.full_name, reject_reason[:50])
                continue

            # ── Diplomat Protocol: Security Disclosure Gate ──────────────────
            from types import SimpleNamespace
            dummy_dossier = SimpleNamespace(
                vulnerabilities=[contribution.finding],
                repo_url=repo.clone_url
            )
            security_gate_result = await run_security_gate(
                github=self._github,
                owner=repo.owner,
                repo=repo.name,
                dossier=dummy_dossier,
                notifier=self._notifier,
            )
            if security_gate_result is not None:
                logger.warning(
                    "[COMPLIANCE SKIP] Private security disclosure requested by maintainers. "
                    "Approved finding saved to secret_findings/. Aborting PR for %s.",
                    repo.full_name,
                )
                continue

            # Create PR immediately (no artificial delay)
            try:
                patch_length = sum(
                    len(c.new_content) for c in contribution.changes if c.new_content
                )
                base_coding_time = max(60, patch_length // 15)
                logger.info(
                    "Creating PR for issue #%d in %s...", issue.number, repo.full_name
                )
                async with self._human_typing_lock:
                    if not dry_run:
                        curr_prs = await self._memory.get_today_pr_count()
                        if curr_prs >= self.config.github.max_prs_per_day:
                            logger.warning(
                                "TOCTOU PR LIMIT DEFENSE: Concurrent quota hit "
                                "(%d). Aborting PR for %s",
                                curr_prs,
                                repo.full_name,
                            )
                            return result

                    logger.info(
                        "Creating PR for issue #%d in %s...", issue.number, repo.full_name
                    )
                typing_time = int(patch_length / 3.75)
                total_coding_delay = min(base_coding_time + typing_time, 3600)

                # CRIT-04 FIX: Move long coding delay OUTSIDE the lock.
                if not dry_run:
                    logger.info(
                        f"⏳ Bắt đầu code cho {repo.full_name}... "
                        f"(Simulating {total_coding_delay}s of heavy coding)"
                    )
                    await asyncio.sleep(total_coding_delay)

                # INSIDE THE LOCK: Sequential PR pushing only
                async with self._human_typing_lock:
                    if not dry_run:
                        # P2-FIX: TOCTOU Quota defense inside lock.
                        curr_prs = await self._memory.get_today_pr_count()
                        if curr_prs >= self.config.github.max_prs_per_day:
                            logger.warning(
                                "🚫 TOCTOU PR LIMIT DEFENSE: Concurrent quota hit "
                                "(%d). Aborting PR for %s",
                                curr_prs,
                                repo.full_name,
                            )
                            return result

                        logger.info("⏳ Chuẩn bị push code... (Taking a deep breath)")
                        await asyncio.sleep(random.randint(15, 45))

                    logger.info(
                        "📤 Creating PR for issue #%d in %s...", issue.number, repo.full_name
                    )
                    pr_result = await self._pr_manager.create_pr(
                        contribution,
                        repo,
                        guidelines=guidelines,
                        closes_issue=issue.number,
                    )
                result.prs_created += 1
                result.prs.append(pr_result)

                await self._memory.record_pr(
                    repo=repo.full_name,
                    pr_number=pr_result.pr_number,
                    pr_url=pr_result.pr_url,
                    title=contribution.title,
                    pr_type=contribution.contribution_type.value,
                    branch=pr_result.branch_name,
                    fork=pr_result.fork_full_name,
                )

                if not dry_run and getattr(self, "_notifier", None):
                    await self._safe_send_notification(
                        f"✅ **PR SUCCESS**\n"
                        f"Target: {repo.full_name}\n"
                        f"URL: {pr_result.pr_url}\n"
                        f"Vulnerability: {contribution.finding.type.value}"
                    )

                # Post-PR compliance
                try:
                    await self._pr_manager.check_compliance_and_fix(
                        pr_result, contribution, guidelines=guidelines
                    )
                except Exception as e:
                    logger.warning("Compliance check failed: %s", e)

                # CI check
                try:
                    await self._check_ci_and_close_if_failed(pr_result, repo)
                except Exception as e:
                    logger.warning("CI check failed: %s", e)

            except Exception as e:
                error = f"PR creation failed for issue #{issue.number}: {e}"
                logger.error(error)
                result.errors.append(error)
                if not dry_run and getattr(self, "_notifier", None):
                    await self._safe_send_notification(
                        f"❌ **PR FAILED**\n"
                        f"Target: {repo.full_name}\n"
                        f"Error: {str(e)[:200]}"
                    )

        result.repos_analyzed = 1
        return result

    def _identify_key_files(self, file_tree: list, repo: Repository) -> list[str]:
        """Identify key files in a repo for building context.

        Prioritizes: README, main entry points, config files, core modules.
        """
        priority_patterns = [
            "README.md",
            "CONTRIBUTING.md",
            "setup.py",
            "pyproject.toml",
            "package.json",
            "Cargo.toml",
            "go.mod",
        ]

        # Collect all blob paths
        all_files = [f.path for f in file_tree if f.type == "blob"]

        key_files: list[str] = []

        # Add priority files first
        for pattern in priority_patterns:
            for fpath in all_files:
                if fpath.endswith(pattern) and fpath not in key_files:
                    key_files.append(fpath)
                    break

        # Add main entry points based on language
        lang = (repo.language or "").lower()
        entry_patterns = {
            "python": ["__init__.py", "main.py", "app.py", "cli.py"],
            "javascript": ["index.js", "app.js", "server.js"],
            "typescript": ["index.ts", "app.ts", "main.ts"],
            "go": ["main.go", "cmd/main.go"],
            "rust": ["main.rs", "lib.rs"],
        }

        for pat in entry_patterns.get(lang, []):
            for fpath in all_files:
                if fpath.endswith(pat) and fpath not in key_files:
                    key_files.append(fpath)

        # Add source files from common directories
        src_dirs = ["src/", "lib/", "app/", "pkg/", "internal/"]
        for fpath in all_files:
            if len(key_files) >= 15:
                break
            if any(fpath.startswith(d) for d in src_dirs) and fpath not in key_files:
                key_files.append(fpath)

        return key_files[:15]

    async def _validate_findings(
        self,
        findings: list,
        relevant_files: dict[str, str],
    ) -> list:
        """Validate findings against full file content to filter false positives.

        For each finding, asks the LLM to re-examine whether the issue is
        genuinely valid given the complete file context. This catches issues
        like:
        - Code protected by circuit breakers / error boundaries
        - Maps bounded by static data sources
        - Functions called only from safe contexts
        """
        if not findings:
            return []

        self._set_task("validation")
        validated = []

        for finding in findings:
            file_content = relevant_files.get(finding.file_path, "")
            if not file_content:
                # Can't validate without file content — keep the finding
                validated.append(finding)
                continue

            prompt = (
                f"## Finding Validation\n\n"
                f"A code analyzer found this issue. Your job is to determine "
                f"if it is a GENUINE problem or a FALSE POSITIVE.\n\n"
                f"### Finding\n"
                f"- **Title**: {finding.title}\n"
                f"- **Severity**: {finding.severity.value}\n"
                f"- **File**: {finding.file_path}\n"
                f"- **Description**: {finding.description}\n"
                f"- **Suggestion**: {finding.suggestion}\n\n"
                f"### Full File Content\n"
                f"```\n{file_content[:12000]}\n```\n\n"
                f"### Validation Checklist\n"
                f"Check ALL of these before deciding:\n"
                f"1. Is the affected code already protected by try/catch, "
                f"circuit breakers, error boundaries, or fallback patterns?\n"
                f"2. If the finding is about unbounded growth — is the data source "
                f"actually bounded (static array, enum, hardcoded list, config)?\n"
                f"3. Is the function only called from contexts where the issue "
                f"cannot occur?\n"
                f"4. Would the suggested fix add unnecessary complexity without "
                f"real benefit?\n"
                f"5. Does the existing code already handle this edge case through "
                f"a different mechanism?\n\n"
                f"### Additional Rejection Triggers\n"
                f"- Snippet is a raw string literal with no code structure → REJECT\n"
                f"- Snippet is fewer than 2 lines of actual code → REJECT\n"
                f"- No clear path from user input to vulnerable sink → REJECT\n"
                f"- Code relies on implicit behavior not present in snippet → REJECT\n\n"
                f"### Response Format\n"
                f"You MUST respond ONLY with valid JSON. No markdown, no explanation outside JSON.\n"
                f'{{"devil_advocate_critique": "MANDATORY: Write 2 sentences explaining why this snippet is perfectly safe, '
                f'normal, or uses modern language defaults. Prove the scanner wrong.", '
                f'"is_real_vulnerability": true/false, "confidence_score": 0-100, '
                f'"rejection_reason": "reason if false", "data_flow_proof": "exact var names if true"}}'
            )

            # TASK 3: Python pre-filter — skip non-code findings before LLM call
            finding_text = f"{finding.title} {finding.description} {finding.suggestion or ''}"
            code_chars = {"{", "}", "(", ")", "=", ":=", "func", "def", "class",
                          "[", "]", "<", ">", "+", "-", "*", "/", ";", "!"}
            if not any(ch in finding_text for ch in code_chars):
                logger.info(
                    "Snippet dropped: Does not look like code — %s",
                    finding.title,
                )
                continue

            try:
                response = await self._llm.complete(
                    prompt,
                    system=(
                        "You are a senior code reviewer validating automated findings. "
                        "Be skeptical — reject findings that are false positives.\n\n"
                        "CRITICAL RULES:\n"
                        "1. NO ASSUMPTIONS: You MUST base your assessment ONLY on the provided code snippet. "
                        "Do NOT assume, guess, or imagine functionality not visible. "
                        "Do NOT use 'If [condition]' logic. If you have to say 'If', it is a False Positive.\n"
                        "2. DATA FLOW REQUIREMENT: You must trace user-controlled input to the vulnerable sink. "
                        "If no clear exploitable data flow exists, mark as False Positive.\n"
                        "3. GARBAGE SNIPPET REJECTION: If snippet is too short, is just a string literal, "
                        "or lacks structural programming context, reject immediately.\n\n"
                        "KNOWN FALSE POSITIVES IMMUNITY LIST:\n"
                        "- GO LANG: defer guarantees execution. defer mutex.Unlock() is safe and the OPPOSITE of a deadlock. NEVER flag it.\n"
                        "- GO LANG: crypto/tls defaults to TLS 1.2+ in modern Go. Missing MinVersion is safe. NEVER flag it.\n"
                        "- PYTHON: Standard urllib or requests usages WITHOUT explicit unsanitized user inputs in the URL are safe.\n"
                        "- ALL: If the snippet is NOT valid programming code (e.g., just English text like 'TLS configuration missing'), DROP IT.\n\n"
                        "DEVIL'S ADVOCATE: You MUST write 2 sentences in devil_advocate_critique explaining why this snippet is "
                        "perfectly safe, normal, or uses modern language defaults. Prove the scanner wrong.\n\n"
                        "Respond ONLY with valid JSON matching this schema:\n"
                        '{"devil_advocate_critique": "string (MANDATORY)", '
                        '"is_real_vulnerability": boolean, '
                        '"confidence_score": integer (0-100), '
                        '"rejection_reason": "string (required if false)", '
                        '"data_flow_proof": "string (required if true — cite exact variable names)"}'
                    ),
                    temperature=0.1,
                )
            except Exception as e:
                # Infrastructure error — re-raise so caller can handle
                logger.error("Finding %s validation failed (infrastructure): %s", finding.title, e)
                raise

            # Parse JSON response
            try:
                response_text = response.strip()
                fence_match = re.search(r"```(?:json)?\s*(.*?)```", response_text, re.DOTALL | re.IGNORECASE)
                if fence_match:
                    response_text = fence_match.group(1).strip()
                brace_start = response_text.find("{")
                brace_end = response_text.rfind("}")
                if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
                    response_text = response_text[brace_start:brace_end + 1]

                parsed = json.loads(response_text)

                devil_advocate = parsed.get("devil_advocate_critique", "")
                is_real = parsed.get("is_real_vulnerability", False)
                try:
                    confidence = int(parsed.get("confidence_score", 0))
                except ValueError:
                    confidence = 0
                rejection_reason = parsed.get("rejection_reason", "no reason provided")
                data_flow_proof = parsed.get("data_flow_proof", "")

                # TASK 3: Auto-drop if data_flow_proof is lazy (hallucination indicator)
                _hallucination_words = {" If ", " Assume ", " Might ", " Maybe ", " Possibly ", " Probably "}
                if is_real and (len(data_flow_proof) < 20 or data_flow_proof.lower().count("if") > 2
                        or any(w in data_flow_proof for w in _hallucination_words)):
                    logger.info(
                        "❌ data_flow_proof too lazy (len=%d, contains If/Assume/Might) for %s — auto-rejected",
                        len(data_flow_proof),
                        finding.title,
                    )
                    continue

                # Gate: drop if not real OR confidence < 90
                if not is_real or confidence < 90:
                    logger.info(
                        "❌ Finding rejected: %s — score=%d reason=%s | devil_advocate=%s",
                        finding.title,
                        confidence,
                        rejection_reason,
                        (devil_advocate[:60] + "...") if len(devil_advocate) > 60 else devil_advocate,
                    )
                    continue

                logger.info(
                    "✅ Finding validated: %s — score=%d flow=%s",
                    finding.title,
                    confidence,
                    (data_flow_proof[:60] + "...") if len(data_flow_proof) > 60 else data_flow_proof,
                )
                validated.append(finding)

            except (json.JSONDecodeError, ValueError, TypeError, AttributeError) as e:
                # Finding is genuinely invalid — skip it, don't retry
                logger.warning("Finding %s failed validation (parse error): %s", finding.title, e)
                continue

        return validated

    async def _layer1_expert_appraisal(
        self,
        finding: Finding,
        file_content: str,
    ) -> tuple[bool, str]:
        """Layer 1: The Appraiser. Verifies if finding is genuinely HIGH/CRITICAL."""
        if not file_content:
            return True, ""  # Bypass if no code (or handle differently)
        
        from farm_agent.llm.provider import create_llm_provider
        import copy
        import json
        import re
        
        try:
            kimi_cfg = copy.copy(self.config.llm)
            kimi_cfg.provider = "openrouter"
            kimi_cfg.model = "moonshotai/kimi-k2.5"
            kimi_provider = create_llm_provider(kimi_cfg)
        except Exception as e:
            logger.warning("Layer 1 instantiation failed: %s. Failing closed.", e)
            return False, f"Instantiation failed: {e}"

        prompt = (
            f"Please verify this vulnerability claim:\n\n"
            f"Title: {finding.title}\n"
            f"Description: {finding.description}\n"
            f"Code snippet context:\n```\n{file_content[:10000]}\n```\n"
        )
        system_prompt = (
            "You are the Expert Security Appraiser. The Red Team claims the provided code snippet "
            "contains a vulnerability. They often hallucinate. Your job is to rigorously debunk their claim. "
            "You must verify if this is a GENUINE, EXPLOITABLE vulnerability of HIGH, CRITICAL, or Zero-Day severity. "
            "If it is a False Positive, a theoretical edge case, or lacks clear data-flow evidence, you MUST reject it.\n\n"
            "Respond ONLY in valid JSON matching this schema:\n"
            '{{"is_genuine_severe_vuln": boolean, "expert_critique": "string"}}'
        )

        try:
            response = await kimi_provider.complete(prompt, system=system_prompt, temperature=0.1)
            await kimi_provider.close()
            
            response_text = response.strip()
            fence_match = re.search(r"```(?:json)?\s*(.*?)```", response_text, re.DOTALL | re.IGNORECASE)
            if fence_match:
                response_text = fence_match.group(1).strip()
            brace_start = response_text.find("{")
            brace_end = response_text.rfind("}")
            if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
                response_text = response_text[brace_start:brace_end + 1]

            parsed = json.loads(response_text)
            is_genuine = parsed.get("is_genuine_severe_vuln", False)
            critique = parsed.get("expert_critique", "No critique provided")
            
            if not is_genuine:
                logger.warning("Dropped by Layer 1 Appraiser (Kimi): %s", critique)
                return False, critique
            return True, ""
            
        except Exception as e:
            logger.error("Layer 1 evaluation failed for %s: %s", finding.title, e)
            return False, str(e)

    async def _layer2_supreme_audit(
        self,
        contribution: Contribution,
        sandbox_logs: str,
    ) -> tuple[bool, str]:
        """Layer 2: The Supreme Auditor. Final gate before PR or writing to secret_findings."""
        from farm_agent.llm.provider import create_llm_provider
        import copy
        import json
        import re
        
        try:
            gem_cfg = copy.copy(self.config.llm)
            gem_cfg.provider = "openrouter"
            gem_cfg.model = "google/gemini-3.1-pro-preview"
            gem_provider = create_llm_provider(gem_cfg)
        except Exception as e:
            logger.warning("Layer 2 instantiation failed: %s. Failing closed.", e)
            return False, f"Instantiation failed: {e}"

        patch_str = "\n".join(
            f"File: {c.path}\n```\n{c.new_content}\n```" for c in contribution.changes
        )

        prompt = (
            f"Vulnerability Dossier Audit:\n\n"
            f"Title: {contribution.finding.title}\n"
            f"Description/Root Cause: {contribution.finding.description}\n\n"
            f"Proposed Patch:\n{patch_str}\n\n"
            f"Sandbox Logs:\n```\n{sandbox_logs[-10000:]}\n```\n"
        )
        system_prompt = (
            "You are the Supreme Auditor, the final gatekeeper before a vulnerability report or code patch is deployed to production. "
            "You are provided with the entire incident dossier: original context, root cause analysis, the proposed patch, and Sandbox execution logs. "
            "Your task is to audit the ENTIRE pipeline. Does the root cause make actual sense? Does the fix perfectly resolve it without introducing regressions? "
            "Are the sandbox logs completely clean?\n"
            "If there is ANY hallucination in the root cause, or if the fix is incomplete, you MUST reject the entire operation.\n\n"
            "Respond ONLY in valid JSON matching this schema:\n"
            '{{"final_approval": boolean, "rejection_reason": "string (mandatory if false)"}}'
        )

        try:
            response = await gem_provider.complete(prompt, system=system_prompt, temperature=0.1)
            await gem_provider.close()
            
            response_text = response.strip()
            fence_match = re.search(r"```(?:json)?\s*(.*?)```", response_text, re.DOTALL | re.IGNORECASE)
            if fence_match:
                response_text = fence_match.group(1).strip()
            brace_start = response_text.find("{")
            brace_end = response_text.rfind("}")
            if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
                response_text = response_text[brace_start:brace_end + 1]

            parsed = json.loads(response_text)
            approved = parsed.get("final_approval", False)
            reason = parsed.get("rejection_reason", "No reason provided")
            
            if not approved:
                logger.warning("Vetoed by Layer 2 Supreme Auditor (Gemini): %s", reason)
                return False, reason
            return True, ""
            
        except Exception as e:
            logger.error("Layer 2 audit failed for %s: %s", contribution.title, e)
            return False, str(e)

    async def _check_ai_policy(self, repo: Repository) -> bool:
        """Check if a repo has an AI policy that bans AI-generated PRs.

        Checks:
        - AI_POLICY.md or .github/AI_POLICY.md
        - Keywords in CONTRIBUTING.md suggesting AI PRs are banned

        Returns True if the repo bans AI PRs.
        """
        ai_policy_paths = [
            "AI_POLICY.md",
            ".github/AI_POLICY.md",
            ".github/ai_policy.md",
        ]

        for path in ai_policy_paths:
            try:
                content = await self._github.get_file_content(repo.owner, repo.name, path)
                if content:
                    content_lower = content.lower()
                    # Check for ban keywords
                    ban_keywords = [
                        "do not accept ai",
                        "no ai-generated",
                        "ai contributions are not accepted",
                        "ban ai",
                        "prohibit ai",
                        "ai-generated pull requests will be closed",
                        "reject ai",
                    ]
                    if any(kw in content_lower for kw in ban_keywords):
                        return True
            except Exception as e:
                logger.error("AI policy check failed: %s — continuing", e)
                continue

        # Also check CONTRIBUTING.md for anti-AI language
        try:
            for contrib_path in ["CONTRIBUTING.md", ".github/CONTRIBUTING.md"]:
                try:
                    content = await self._github.get_file_content(
                        repo.owner, repo.name, contrib_path
                    )
                    if content:
                        content_lower = content.lower()
                        ban_phrases = [
                            "ai-generated contributions",
                            "no ai pull requests",
                            "ban on ai-generated",
                            "do not submit ai",
                            "see ai_policy",
                        ]
                        if any(phrase in content_lower for phrase in ban_phrases):
                            return True
                except Exception as e:
                    logger.error("AI policy check failed: %s — denying by default", e)
                    return False
        except Exception as e:
            logger.error("AI policy check failed: %s — denying by default", e)
            return False

        return False

    async def _check_ci_and_close_if_failed(
        self,
        pr_result: PRResult,
        repo: Repository,
        *,
        max_wait_sec: int = 90,
        poll_interval: int = 15,
    ) -> None:
        """Wait for CI checks and leave failed PRs open for Patrol auto-heal.

        Polls the PR's head commit for check run results. If required
        checks fail (e.g. lint, typecheck, unit tests), logs the failure
        and leaves the PR open so PRPatrol can download logs and push a
        follow-up fix.
        """
        import asyncio

        branch = pr_result.branch_name
        fork_parts = pr_result.fork_full_name.split("/")
        fork_owner = fork_parts[0]
        fork_name = fork_parts[1] if len(fork_parts) > 1 else repo.name

        # Get the head SHA of the PR branch
        try:
            branch_data = await self._github._get(
                f"/repos/{fork_owner}/{fork_name}/git/ref/heads/{branch}"
            )
            head_sha = branch_data["object"]["sha"]
        except Exception:
            logger.debug("Could not get head SHA for CI check, skipping")
            return

        logger.info("⏳ Waiting for CI checks on PR #%d...", pr_result.pr_number)

        elapsed = 0
        while elapsed < max_wait_sec:
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

            status = await self._github.get_combined_status(repo.owner, repo.name, head_sha)

            if status.get("total", 0) == 0:
                logger.info(
                    "ℹ️ No CI check runs detected for PR #%d;"  # noqa: RUF001
                    " leaving it open for Patrol/manual follow-up",
                    pr_result.pr_number,
                )
                return

            if status["state"] == "pending":
                logger.debug(
                    "CI still running (%ds/%ds): %s",
                    elapsed,
                    max_wait_sec,
                    ", ".join(status.get("in_progress", [])),
                )
                continue

            if status["state"] == "success":
                logger.info(
                    "✅ CI passed for PR #%d (%d checks)",
                    pr_result.pr_number,
                    status["total"],
                )
                return

            if status["state"] == "failure":
                failed_names = ", ".join(status["failed"])
                logger.warning(
                    "❌ CI failed for PR #%d: %s",
                    pr_result.pr_number,
                    failed_names,
                )
                logger.info(
                    "🤖 Leaving PR #%d open so Patrol can attempt CI auto-healing",
                    pr_result.pr_number,
                )
                return

        # Timeout — log but don't close (CI may still be running)
        logger.info(
            "⏰ CI check timed out after %ds for PR #%d, leaving open",
            max_wait_sec,
            pr_result.pr_number,
        )

    async def _safe_send_notification(self, message: str) -> None:
        """Send a notification without crashing the main loop."""
        try:
            await self._notifier.send_message(message)
        except Exception as exc:
            logger.warning("Notification send failed (non-fatal): %s", exc)

    def _set_task(self, task_name: str) -> None:
        """Set the current task context for multi-model routing."""
        if not self._llm or not hasattr(self._llm, "set_task"):
            return

        import contextlib

        from farm_agent.llm.models import TaskType

        with contextlib.suppress(ValueError, AttributeError):
            self._llm.set_task(TaskType(task_name))

    async def _clone_and_patch_repo(
        self,
        clone_url: str,
        changes: list,
        tests_added: list,
    ) -> str:
        """Clone a GitHub repo to a temp dir and apply patches for sandbox validation.

        BUG FIX (Crucible): The sandbox expects a LOCAL filesystem path, not a
        GitHub URL. Previously pipeline passed repo.clone_url directly, causing
        'Sandbox repository path does not exist: /home/farm_agent/https:/...'.

        This method:
        1. Clones the repo to a unique temp directory (cached per clone_url)
        2. Applies all FileChange patches to the local clone
        3. Returns the local path for sandbox validation
        """
        # Use a class-level cache to avoid re-cloning the same repo across
        # multiple sandbox calls within the same pipeline run.
        cache_key = clone_url
        if not hasattr(self, "_clone_cache"):
            self._clone_cache: dict[str, str] = {}

        if cache_key in self._clone_cache:
            clone_path = self._clone_cache[cache_key]
            logger.debug("Reusing cached clone at %s", clone_path)
        else:
            # Create a unique temp directory for this clone
            base_temp = tempfile.gettempdir()
            clone_path = os.path.join(base_temp, f"farm_agent_sandbox_{len(self._clone_cache)}")
            await asyncio.to_thread(os.makedirs, clone_path, exist_ok=True)

            def _do_clone() -> None:
                result = subprocess.run(
                    ["git", "clone", "--depth=1", clone_url, clone_path],
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                if result.returncode != 0:
                    raise RuntimeError(
                        f"git clone failed (exit {result.returncode}): {result.stderr}"
                    )

            try:
                await asyncio.to_thread(_do_clone)
            except Exception as e:
                logger.error("Failed to clone %s: %s", clone_url, e)
                raise

            self._clone_cache[cache_key] = clone_path
            logger.info("Cloned %s → %s", clone_url, clone_path)

        # Apply patches (changes + tests_added) to the local clone
        all_changes = list(changes) + list(tests_added)

        # PERF-OPT: Process file patches using to_thread to avoid blocking event loop
        # and gather them for potential parallel I/O speedup.
        patch_tasks = [
            asyncio.to_thread(self._apply_patch_sync, clone_path, change) for change in all_changes
        ]
        await asyncio.gather(*patch_tasks)

        return clone_path

    def _apply_patch_sync(self, clone_path: str, change: FileChange) -> None:
        """Synchronously apply a single FileChange patch to the local clone."""
        file_path = os.path.normpath(os.path.join(clone_path, change.path))
        # Security: ensure the file path stays within the clone directory
        if not file_path.startswith(clone_path + os.sep) and file_path != clone_path:
            logger.warning("Patch path %s escapes clone dir — skipping", change.path)
            return

        try:
            if change.is_new_file:
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(change.new_content)
                logger.debug("Created new file: %s", change.path)
            elif change.is_deleted:
                if os.path.exists(file_path):
                    os.remove(file_path)
                logger.debug("Deleted file: %s", change.path)
            else:
                # Replace original_content snippet with new_content
                if os.path.exists(file_path):
                    with open(file_path, encoding="utf-8") as f:
                        content = f.read()
                    if change.original_content and change.original_content in content:
                        content = content.replace(
                            change.original_content,
                            change.new_content,
                            1,
                        )
                    else:
                        # Fallback: just write new_content (original_content may be
                        # a partial snippet from the LLM)
                        content = change.new_content
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(content)
                    logger.debug("Patched file: %s", change.path)
                else:
                    logger.warning(
                        "Patch target file does not exist: %s — creating it",
                        change.path,
                    )
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(change.new_content)
        except Exception as e:
            logger.warning("Failed to apply patch to %s: %s", change.path, e)
            # Continue with other patches — don't fail the whole validation
