"""Repository discovery engine.

Discovers, filters, and prioritizes GitHub repositories
that are good candidates for contributions.
"""

from __future__ import annotations

import logging
import random
from datetime import UTC, datetime, timedelta

from farm_agent.core.config import DiscoveryConfig
from farm_agent.core.models import DiscoveryCriteria, Repository
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
