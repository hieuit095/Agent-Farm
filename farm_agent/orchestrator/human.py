"""Terminator Mode — relentless continuous execution loop.

Runs hunt-circular and patrol in a tight loop with minimal safety sleep,
preserving daily KB garbage collection and friendly-repos sync.
All simulated human delays, coffee breaks, and randomized daily PR targets
have been removed. The loop runs continuously and aggressively.

Usage:
    farm_agent superhuman              # Run the terminator loop
    farm_agent superhuman --time-warp  # Run 10 fast iterations for testing
"""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import UTC, date, datetime

from farm_agent.core.exceptions import FarmAgentError, GitHubAPIError, LLMRateLimitError
from farm_agent.core.notifier import TelegramNotifier

logger = logging.getLogger(__name__)

# Time-warp overrides (seconds) for testing
WARP_MAX_ITERATIONS = 10

# Terminator loop constants
TERMINATOR_SLEEP = 10          # Seconds between iterations (prevents CPU pegging)
TERMINATOR_SLEEP_WARP = 1      # Seconds in time-warp mode
PATROL_ONLY_SLEEP = 60         # Seconds when in patrol-only mode (quota met)
LLM_QUOTA_COOLDOWN = 300       # Seconds when LLM quota exhausted (5 min)
LLM_QUOTA_COOLDOWN_WARP = 3    # Seconds in time-warp mode

# Action selection weights
HUNT_WEIGHT = 0.60
PATROL_WEIGHT = 0.40


class SuperHumanLoop:
    """Terminator execution loop: relentless continuous operation.

    Runs hunt-circular and patrol with minimal sleep, preserving:
    - Daily KB garbage collection
    - Friendly-repos sync (24-hour throttle)
    - max_prs_per_day safety cap
    - LLM rate-limit cooldown
    """

    def __init__(
        self,
        pipeline,
        memory,
        *,
        dry_run: bool = False,
        target_repo_url: str | None = None,
        target_repo_max_prs: int = 1,
    ):
        from farm_agent.core.daily_log import DailyMarkdownLogger

        self._pipeline = pipeline
        self._memory = memory
        self._dry_run = dry_run
        self._target_repo_url = target_repo_url
        self._target_repo_max_prs = max(1, target_repo_max_prs)
        self._prs_created_today: int = 0
        self._current_day: date | None = None
        self._iteration = 0
        self._daily_log = DailyMarkdownLogger()
        self._notifier = TelegramNotifier(
            token=self._pipeline.config.notifications.telegram_token,
            chat_id=self._pipeline.config.notifications.telegram_chat_id,
        )

    async def _new_day_check(self) -> bool:
        """Check if a new calendar day has started. Returns True if day changed.

        Also runs knowledge base garbage collection once per day.
        """
        today = datetime.now(UTC).date()
        if self._current_day != today:
            self._current_day = today
            self._prs_created_today = 0
            self._daily_log.log_new_day(self._pipeline.config.github.max_prs_per_day)
            logger.info("[TERMINATOR] New day: %s — resetting PR counter", today)

            # ── Knowledge Base Garbage Collection ──────────────────────
            try:
                deleted_count = await self._memory.run_kb_garbage_collection(days=90)
                logger.info(
                    "[TERMINATOR] KB GC complete: purged %d stale entries",
                    deleted_count,
                )
            except Exception as exc:
                logger.warning("[TERMINATOR] KB GC failed (non-fatal): %s", exc)

            return True
        return False

    async def _do_hunt(self) -> tuple[int, int]:
        """Execute a single Hunt action.

        Returns:
            Tuple of (prs_created, repos_analyzed).
        """
        logger.info("[TERMINATOR] Hunt iteration starting...")
        try:
            if self._target_repo_url:
                result = await self._pipeline.run_single(
                    self._target_repo_url,
                    dry_run=self._dry_run,
                    max_prs=self._target_repo_max_prs,
                )
            else:
                result = await self._pipeline.hunt(
                    rounds=1,
                    delay_sec=5,
                    dry_run=self._dry_run,
                    mode="both",
                )

            if result.prs_created > 0 and result.pr_urls:
                for url in result.pr_urls:
                    parts = url.rstrip("/").split("/")
                    repo = f"{parts[-4]}/{parts[-3]}" if len(parts) >= 4 else "unknown"
                    pr_num = int(parts[-1]) if parts[-1].isdigit() else 0
                    self._daily_log.log_hunt_success(repo, pr_num, url)
            elif result.prs_created > 0:
                self._daily_log.log_hunt_success("repo", result.prs_created, "(no URL available)")
            else:
                self._daily_log.log_hunt_no_result(result.repos_analyzed)

            return result.prs_created, result.repos_analyzed
        except GitHubAPIError as exc:
            logger.error("[TERMINATOR] Hunt failed (GitHubAPIError): %s", exc)
            raise
        except Exception as exc:
            logger.error("[TERMINATOR] Hunt failed (unexpected error): %s", exc)
            raise

    # ── Familiar Grounds Sync ───────────────────────────────────────────────

    async def _sync_historical_friendly_repos(self) -> int:
        """Sync historically merged PRs from GitHub into the local friendly-repos DB."""
        import time as time_module

        min_stars, max_stars = self._pipeline.config.discovery.stars_range

        username = ""
        for attempt in range(3):
            try:
                if self._pipeline._github is None:
                    await asyncio.sleep(2)
                    continue
                user: dict = await self._pipeline._github.get_authenticated_user()
                username = user.get("login", "")
                break
            except Exception as exc:
                if attempt < 2:
                    await asyncio.sleep(2)
                else:
                    logger.warning("Cannot sync friendly repos — auth failed: %s", exc)
                    return 0

        if not username:
            logger.warning("Cannot sync friendly repos — empty username")
            return 0

        logger.info("[TERMINATOR] Familiar Grounds sync: @%s ...", username)
        start = time_module.time()

        try:
            merged_prs = await self._pipeline._github.fetch_user_merged_prs(username)
        except Exception as exc:
            logger.warning("GitHub search API failed during friendly-repos sync: %s", exc)
            return 0

        repo_map: dict[str, dict] = {}
        for pr in merged_prs:
            repo = pr.get("repo", "")
            if not repo:
                continue
            merged_at = pr.get("merged_at") or ""
            if repo not in repo_map or merged_at > repo_map[repo].get("merged_at", ""):
                repo_map[repo] = pr

        new_count = 0
        now_utc = datetime.now(UTC).isoformat()

        semaphore = asyncio.Semaphore(3)

        async def process_one_repo(repo_full_name: str, pr: dict) -> bool:
            async with semaphore:
                await asyncio.sleep(1.0)
                owner = repo_full_name.split("/")[0]
                stars = 0
                try:
                    repo_details = await self._pipeline._github.get_repo_details(
                        owner, repo_full_name.split("/")[1]
                    )
                    stars = getattr(repo_details, "stars", 0) or 0
                except Exception:
                    return False

                if not (min_stars <= stars <= max_stars):
                    return False

                try:
                    cursor = await self._memory._db.execute(
                        """INSERT OR IGNORE INTO submitted_prs
                           (repo, pr_number, pr_url, title, type, status, created_at, updated_at)
                           VALUES (?, ?, ?, ?, 'historical_sync', 'merged', ?, ?)""",
                        (
                            repo_full_name,
                            pr.get("pr_number", 0),
                            pr.get("html_url") or "",
                            pr.get("title") or "",
                            pr.get("merged_at") or now_utc,
                            now_utc,
                        ),
                    )
                    new_row = cursor.rowcount == 1
                    if new_row:
                        logger.info("Friendly repo added: %s (★ %d)", repo_full_name, stars)
                        return True
                    await self._memory._db.execute(
                        """UPDATE submitted_prs
                           SET status = 'merged', updated_at = ?, pr_url = ?, title = ?
                           WHERE repo = ? AND pr_number = ?""",
                        (now_utc, pr.get("html_url") or "", pr.get("title") or "", repo_full_name, pr.get("pr_number", 0)),
                    )
                except Exception as exc:
                    logger.error("Sync DB Error for %s: %s", repo_full_name, exc)
                return False

        results = await asyncio.gather(
            *[process_one_repo(repo_full_name, pr) for repo_full_name, pr in repo_map.items()]
        )
        new_count = sum(1 for r in results if r)
        await self._memory._db.commit()
        elapsed = time_module.time() - start
        logger.info("Familiar Grounds sync: %d new repos (%d scanned) in %.1fs", new_count, len(repo_map), elapsed)
        return new_count

    async def _sync_vip_friendly_repos(self) -> int:
        """Discover and persist VIP repos (>1000 stars) where the user has merged PRs."""
        try:
            if not await self._memory.should_run_vip_sync():
                return 0
        except Exception as exc:
            logger.warning("VIP sync throttle check failed: %s — proceeding anyway", exc)

        username = ""
        try:
            user: dict = await self._pipeline._github.get_authenticated_user()
            username = user.get("login", "")
        except Exception as exc:
            logger.warning("VIP repo sync: could not get authenticated user: %s", exc)
            return 0

        if not username:
            logger.warning("VIP repo sync: empty username")
            return 0

        logger.info("[TERMINATOR] VIP Friendly sync: @%s ...", username)

        try:
            vip_repos = await self._pipeline._github.discover_vip_friendly_repos(username)
        except Exception as exc:
            logger.warning("VIP repo sync: GitHub API failed: %s", exc)
            return 0

        if not vip_repos:
            await self._memory.mark_vip_sync_done()
            return 0

        try:
            new_count = await self._memory.add_friendly_vip_repos(vip_repos)
            await self._memory.mark_vip_sync_done()
            logger.info("VIP Friendly sync: %d new repos inserted (%d found)", new_count, len(vip_repos))
            return new_count
        except Exception as exc:
            logger.warning("VIP repo sync: DB insert failed: %s", exc)
            return 0

    async def _run_janitor_sweep(self) -> dict:
        """Run the PR Janitor sweep."""
        from farm_agent.pr.janitor import PRJanitor

        try:
            user: dict = await self._pipeline._github.get_authenticated_user()
            username: str = user.get("login", "")
        except Exception as exc:
            logger.warning("Janitor sweep: could not get GitHub username: %s", exc)
            return {"total_scanned": 0, "garbage_closed": 0, "critical_spared": 0, "errors": 1, "details": []}

        janitor = PRJanitor(self._pipeline._github, username, self._pipeline.config.llm)
        logger.info("[TERMINATOR] Janitor sweep triggered.")
        result = await janitor.sweep_and_destroy()
        logger.info(
            "[TERMINATOR] Janitor sweep: scanned=%d, destroyed=%d",
            result["total_scanned"], result["garbage_closed"],
        )
        return result

    async def _run_accept_check(self) -> str:
        """Build a Hall of Fame message from merged PRs in the database."""
        merged = await self._memory.get_prs(status="merged", limit=15)
        if not merged:
            return "Chua co PR nao duoc gop vao Bang Vang. Dang co gang san day!"

        lines = ["HALL OF FAME\n"]
        for i, pr in enumerate(merged, 1):
            title = pr.get("title") or pr.get("pr_title") or "(untitled)"
            pr_num = pr.get("pr_number") or pr.get("pr_num") or "?"
            url = pr.get("pr_url") or pr.get("url") or ""
            if url:
                lines.append(f"{i}. {title} (#{pr_num}) {url}")
            else:
                lines.append(f"{i}. {title} (#{pr_num})")
        return "\n".join(lines)

    async def _do_patrol(self) -> None:
        """Execute a single PR Patrol action."""
        from farm_agent.pr.patrol import PRPatrol

        logger.info("[TERMINATOR] Patrol iteration starting...")
        try:
            open_prs = await self._memory.get_prs(status="open", limit=100)
            pending_prs = await self._memory.get_prs(status="pending", limit=100)
            pr_records = open_prs + pending_prs
            if not pr_records:
                logger.info("[TERMINATOR] No open PRs to patrol.")
                return

            logger.info("[TERMINATOR] Found %d PR(s) to patrol.", len(pr_records))

            github = self._pipeline._github
            llm = self._pipeline._llm

            patrol_engine = PRPatrol(
                github=github, llm=llm, memory=self._memory, notifier=self._notifier
            )
            result = await patrol_engine.patrol(
                pr_records,
                dry_run=self._dry_run,
            )

            for merged in result.prs_merged:
                repo_name = merged["repo"]
                pr_num = merged["pr_number"]
                message = f"[MERGED] PR #{pr_num} in {repo_name} has been accepted!"
                await self._pipeline._safe_send_notification(message)

            if result.prs_checked > 0:
                self._daily_log.log_patrol_result(
                    prs_checked=result.prs_checked,
                    fixes_pushed=result.fixes_pushed,
                    replies_sent=result.replies_sent,
                    ci_fixes=getattr(result, "ci_fixes_pushed", 0),
                )
            else:
                self._daily_log.log_patrol_empty()

        except GitHubAPIError as exc:
            logger.error("[TERMINATOR] Patrol failed (GitHubAPIError): %s", exc)
            raise
        except Exception as exc:
            logger.error("[TERMINATOR] Patrol failed: %s", exc)
            raise

    async def _has_pending_notifications(self) -> bool:
        """Check if there are pending notifications/comments on open PRs."""
        try:
            open_prs = await self._memory.get_prs(status="open", limit=10)
            if open_prs:
                logger.info("[TERMINATOR] %d PR(s) with open feedback — prioritizing patrol.", len(open_prs))
                return True
            return False
        except Exception:
            return False

    async def run_daily_routine(self, *, time_warp: bool = False) -> None:
        """Run the Terminator continuous execution loop.

        A relentless while-true loop that cycles through hunt and patrol
        without artificial delays. Preserves:
        - Daily KB garbage collection
        - Friendly-repos sync (24-hour throttle)
        - max_prs_per_day safety cap (switches to patrol-only)
        - LLM rate-limit cooldown

        Args:
            time_warp: If True, 1s delays and exit after 10 iterations.
        """
        logger.info("[TERMINATOR] Mode initialized — relentless loop starting.")
        self._iteration = 0

        # ── Sync PR counter from DB on startup ──
        try:
            self._prs_created_today = await self._memory.get_today_pr_count()
            if self._prs_created_today > 0:
                logger.info(
                    "[TERMINATOR] Synced PR counter from DB: %d PRs already created today",
                    self._prs_created_today,
                )
        except Exception:
            pass

        # Start telegram listener in the background with crash recovery
        if getattr(self, "_notifier", None):
            self._poller_task = asyncio.create_task(
                self._notifier.start_polling(
                    self._memory,
                    on_update_callback=self._sync_historical_friendly_repos,
                    on_clean_callback=self._run_janitor_sweep,
                    on_accept_callback=self._run_accept_check,
                )
            )
            self._poller_task.add_done_callback(self._poller_done_callback)

        # ── Familiar Grounds: sync on startup ──
        self._last_sync_time: float = 0.0
        try:
            if self._pipeline._github is None:
                logger.info("[TERMINATOR] Auth warmup: initializing GitHub client...")
                await self._pipeline._init_components()
            await self._sync_historical_friendly_repos()
            await self._sync_vip_friendly_repos()
        except Exception:
            pass
        self._last_sync_time = __import__("time").time()

        while True:
            self._iteration += 1

            # ── 24-hour friendly-repos sync ──
            elapsed = __import__("time").time() - self._last_sync_time
            if elapsed > 86400:
                try:
                    await self._sync_historical_friendly_repos()
                    await self._sync_vip_friendly_repos()
                except Exception:
                    pass
                self._last_sync_time = __import__("time").time()

            # ── Time-warp exit gate ──
            if time_warp and self._iteration > WARP_MAX_ITERATIONS:
                logger.info("[TERMINATOR] TIME-WARP: Completed %d iterations — exiting.", WARP_MAX_ITERATIONS)
                break

            # ── Daily reset & KB GC ──
            await self._new_day_check()

            # ── Safety cap: max PRs per day ──
            max_prs = self._pipeline.config.github.max_prs_per_day
            try:
                today_prs = await self._memory.get_today_pr_count()
            except Exception:
                today_prs = self._prs_created_today

            if today_prs >= max_prs:
                logger.info(
                    "[TERMINATOR] Daily PR cap reached (%d/%d) — patrol-only mode.",
                    today_prs, max_prs,
                )
                self._daily_log.log_quota_met(today_prs, max_prs)
                try:
                    await self._do_patrol()
                except (GitHubAPIError, FarmAgentError, Exception) as exc:
                    logger.error("[TERMINATOR] Patrol error (quota-met): %s", exc)
                    self._daily_log.log_error("Patrol (quota-met)", str(exc))
                await asyncio.sleep(PATROL_ONLY_SLEEP if not time_warp else TERMINATOR_SLEEP_WARP)
                continue

            # ── Priority: pending notifications → patrol first ──
            if await self._has_pending_notifications():
                try:
                    await self._do_patrol()
                except (GitHubAPIError, FarmAgentError, Exception) as exc:
                    logger.error("[TERMINATOR] Patrol error (pending-notify): %s", exc)
                await asyncio.sleep(TERMINATOR_SLEEP if not time_warp else TERMINATOR_SLEEP_WARP)
                continue

            # ── Stochastic action: hunt (60%) or patrol (40%) ──
            if random.random() < HUNT_WEIGHT:
                try:
                    prs_opened, repos_scanned = await self._do_hunt()
                    if prs_opened > 0:
                        self._prs_created_today += prs_opened
                        logger.info(
                            "[TERMINATOR] Hunt: +%d PRs → %d/%d today",
                            prs_opened, self._prs_created_today, max_prs,
                        )
                except LLMRateLimitError as exc:
                    cooldown = LLM_QUOTA_COOLDOWN_WARP if time_warp else LLM_QUOTA_COOLDOWN
                    logger.warning("[TERMINATOR] LLM quota exhausted — sleeping %ds: %s", cooldown, exc)
                    self._daily_log.log_error("HUNT (LLM Quota)", str(exc))
                    await asyncio.sleep(cooldown)
                    continue
                except (GitHubAPIError, FarmAgentError, Exception) as exc:
                    logger.error("[TERMINATOR] Hunt error: %s", exc)
                    self._daily_log.log_error("HUNT", str(exc))
            else:
                try:
                    await self._do_patrol()
                except (GitHubAPIError, FarmAgentError, Exception) as exc:
                    logger.error("[TERMINATOR] Patrol error: %s", exc)
                    self._daily_log.log_error("Patrol", str(exc))

            # ── Minimal safety sleep to prevent CPU pegging ──
            await asyncio.sleep(TERMINATOR_SLEEP if not time_warp else TERMINATOR_SLEEP_WARP)

        self._daily_log.log_shutdown(self._iteration - 1)
        logger.info("[TERMINATOR] Loop terminated.")

        # Clean up persistent HTTP connections
        if self._notifier:
            await self._notifier.close()

    def _poller_done_callback(self, task: asyncio.Task) -> None:
        """Handle unexpected Telegram poller crashes with restart."""
        if task.cancelled():
            return
        exc = task.exception()
        if exc:
            logger.error("Telegram poller crashed unexpectedly: %s. Restarting in 10s...", exc)
            self._restart_poller_task = asyncio.create_task(self._restart_poller())

    async def _restart_poller(self) -> None:
        """Restart the Telegram poller after an unexpected crash."""
        await asyncio.sleep(10)
        if getattr(self, "_notifier", None):
            try:
                self._poller_task = asyncio.create_task(
                    self._notifier.start_polling(
                        self._memory,
                        on_update_callback=self._sync_historical_friendly_repos,
                        on_clean_callback=self._run_janitor_sweep,
                        on_accept_callback=self._run_accept_check,
                    )
                )
                self._poller_task.add_done_callback(self._poller_done_callback)
                logger.info("Telegram poller restarted successfully")
            except Exception as exc:
                logger.error("Failed to restart Telegram poller: %s", exc)