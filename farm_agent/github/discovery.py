"""Repository discovery engine.

Discovers, filters, and prioritizes GitHub repositories
that are good candidates for contributions.
"""

from __future__ import annotations

import json
import logging
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path

from farm_agent.core.config import DiscoveryConfig
from farm_agent.core.models import DiscoveryCriteria, Repository, TargetRepoEntry
from farm_agent.github.client import GitHubClient

logger = logging.getLogger(__name__)


class RepoDiscovery:
    """Discover contribution-friendly open source repositories."""

    def __init__(self, client: GitHubClient, config: DiscoveryConfig, memory=None):
        self._client = client
        self._config = config
        self._memory = memory

    async def discover(self, criteria: DiscoveryCriteria | None = None) -> list[Repository]:
        """Discover repositories matching criteria.

        Pipeline: search → filter → prioritize → return top N.
        """
        if criteria is None:
            criteria = self._criteria_from_config()

        # Search GitHub
        repos = await self._search(criteria)
        logger.info("Search returned %d repositories", len(repos))

        # Remove blacklisted repos
        if self._memory:
            blacklisted = await self._memory.get_blacklisted_repos()
            bl_names = {r["repo"] for r in blacklisted}
            repos = [r for r in repos if r.full_name not in bl_names]
            if bl_names:
                logger.info("Filtered out %d blacklisted repo(s)", len(bl_names))

        # Filter for contribution-friendliness
        repos = await self._filter_contributable(repos, criteria)
        logger.info("After filtering: %d repositories", len(repos))

        # Prioritize by impact potential
        repos = self._prioritize(repos)

        # Return top N
        return repos[: criteria.max_results]

    def _criteria_from_config(self) -> DiscoveryCriteria:
        """Build criteria from configuration."""
        return DiscoveryCriteria(
            languages=self._config.languages,
            stars_min=self._config.stars_range[0] if len(self._config.stars_range) > 0 else 50,
            stars_max=self._config.stars_range[1] if len(self._config.stars_range) > 1 else 10000,
            min_last_activity_days=self._config.min_last_activity_days,
            require_contributing_guide=self._config.require_contributing_guide,
            topics=self._config.topics,
        )

    async def _search(self, criteria: DiscoveryCriteria) -> list[Repository]:
        """Build and execute GitHub search query with stochastic entropy.

        Entropy injections to break deterministic stagnation:
        1. Random star sub-window (100-star slice within the configured range)
        2. Randomized sort parameter (stars/updated/help-wanted-issues)
        3. Randomized order (desc/asc)
        4. Random pagination jitter (page 1-5)
        """
        all_repos: list[Repository] = []

        for language in criteria.languages:
            # ── Entropy 1: Random star sub-window ──────────────────────
            # Instead of the full range (e.g., stars:2000..12000), pick a
            # random 100-star slice to reach repos beyond the top-30.
            star_span = criteria.stars_max - criteria.stars_min
            if star_span > 100:
                window_start = random.randint(
                    criteria.stars_min,
                    criteria.stars_max - 100,
                )
                window_end = window_start + 100
            else:
                # Range is already narrow — use it as-is
                window_start = criteria.stars_min
                window_end = criteria.stars_max

            query_parts = [
                f"language:{language}",
                f"stars:{window_start}..{window_end}",
                "archived:false",
                "is:public",
            ]

            # Activity filter
            if criteria.min_last_activity_days:
                cutoff = datetime.now(UTC) - timedelta(days=criteria.min_last_activity_days)
                query_parts.append(f"pushed:>{cutoff.strftime('%Y-%m-%d')}")

            # Topic filter
            for topic in criteria.topics:
                query_parts.append(f"topic:{topic}")

            query = " ".join(query_parts)

            # ── Entropy 2: Randomize sort parameter ───────────────────
            sort_choices = ["stars", "updated", "help-wanted-issues"]
            sort_weights = [0.4, 0.4, 0.2]
            random_sort = random.choices(sort_choices, weights=sort_weights, k=1)[0]

            # ── Entropy 3: Randomize order ────────────────────────────
            random_order = random.choices(
                ["desc", "asc"], weights=[0.8, 0.2], k=1
            )[0]

            # ── Entropy 4: Pagination jitter ──────────────────────────
            random_page = random.randint(1, 5)

            logger.info(
                "🎲 Stochastic search: lang=%s, ★ %d-%d (window from %d-%d), "
                "sort=%s, order=%s, page=%d",
                language, window_start, window_end,
                criteria.stars_min, criteria.stars_max,
                random_sort, random_order, random_page,
            )

            repos = await self._client.search_repositories(
                query=query,
                sort=random_sort,
                order=random_order,
                per_page=min(30, criteria.max_results * 2),
                page=random_page,
            )
            all_repos.extend(repos)

        # Deduplicate
        seen = set()
        unique: list[Repository] = []
        for repo in all_repos:
            if repo.full_name not in seen and repo.full_name not in criteria.exclude_repos:
                seen.add(repo.full_name)
                unique.append(repo)

        return unique

    async def _filter_contributable(
        self, repos: list[Repository], criteria: DiscoveryCriteria
    ) -> list[Repository]:
        """Filter repositories that are good candidates for contributions."""
        filtered: list[Repository] = []

        for repo in repos:
            # Skip if no open issues (may not welcome contributions)
            if repo.open_issues == 0:
                logger.debug("Skipping %s: no open issues", repo.full_name)
                continue

            # Check for contributing guide if required
            if criteria.require_contributing_guide:
                guide = await self._client.get_contributing_guide(repo.owner, repo.name)
                if not guide:
                    logger.debug("Skipping %s: no contributing guide", repo.full_name)
                    continue
                repo.has_contributing = True

            # Check last activity
            if repo.last_push_at:
                cutoff = datetime.now(UTC) - timedelta(days=criteria.min_last_activity_days)
                if repo.last_push_at < cutoff:
                    logger.debug("Skipping %s: inactive", repo.full_name)
                    continue

            filtered.append(repo)

        return filtered

    def _prioritize(self, repos: list[Repository]) -> list[Repository]:
        """Score and sort repositories by contribution potential."""

        def score(repo: Repository) -> float:
            s = 0.0
            # Star range sweet spot (100-5000)
            if 100 <= repo.stars <= 5000:
                s += 3.0
            elif repo.stars < 100:
                s += 1.0
            else:
                s += 2.0

            # Open issues = opportunities
            s += min(repo.open_issues / 10.0, 3.0)

            # Has license = probably welcomes contributions
            if repo.has_license:
                s += 1.0

            # Has contributing guide
            if repo.has_contributing:
                s += 2.0

            # Moderate forks = active community
            if 10 <= repo.forks <= 500:
                s += 1.5

            return s

        return sorted(repos, key=score, reverse=True)


class JsonTargetDiscovery:
    """Deterministic circular target loop from target_repo.json.

    Reads targets, sorts by scanned_at ascending (oldest first),
    and provides atomic update of scanned_at before analysis to
    guarantee crash-safe rotation.
    """

    EPOCH = datetime(1970, 1, 1, tzinfo=UTC)

    def __init__(self, json_path: str | Path = "target_repo.json"):
        self._path = Path(json_path)

    def get_next_target(self) -> TargetRepoEntry | None:
        """Return the target with the oldest scanned_at.

        Sorts by scanned_at ascending. Missing/null scanned_at
        is treated as epoch (1970-01-01), guaranteeing never-scanned
        repos are processed first.
        """
        entries = self._load_entries()
        if not entries:
            return None
        entries.sort(key=lambda e: e.scanned_at or self.EPOCH)
        return entries[0]

    def mark_scanned(self, repo_url: str) -> None:
        """Update scanned_at to now and atomically save.

        CRITICAL: Must be called BEFORE any analysis/LLM calls
        to guarantee crash-safe target rotation.
        """
        entries = self._load_entries()
        now = datetime.now(UTC)
        for e in entries:
            if e.repo_url == repo_url:
                e.scanned_at = now
                break
        self._save_entries(entries)

    def _load_entries(self) -> list[TargetRepoEntry]:
        """Load and validate entries from the JSON file."""
        if not self._path.exists():
            logger.warning("target_repo.json not found at %s", self._path)
            return []
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            return [TargetRepoEntry(**entry) for entry in raw]
        except (json.JSONDecodeError, Exception) as exc:
            logger.error("Failed to parse target_repo.json: %s", exc)
            return []

    def _save_entries(self, entries: list[TargetRepoEntry]) -> None:
        """Atomically save entries back to JSON using temp-file-then-rename."""
        tmp_path = self._path.with_suffix(".tmp")
        data = [e.model_dump(mode="json") for e in entries]
        tmp_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        tmp_path.replace(self._path)

    def mark_status(self, repo_url: str, status: str) -> None:
        """Update the status field for a target entry and atomically save.

        Used by the circular loop to mark targets as COMPLETED_NO_VULN
        or other terminal statuses.
        """
        entries = self._load_entries()
        for e in entries:
            if e.repo_url == repo_url:
                e.status = status
                break
        self._save_entries(entries)
