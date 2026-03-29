"""Persistent memory system using SQLite.

Tracks analyzed repos, submitted PRs, and learning data
to avoid duplicate work and improve over time.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

import aiosqlite

logger = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS analyzed_repos (
    full_name   TEXT PRIMARY KEY,
    language    TEXT,
    stars       INTEGER,
    analyzed_at TEXT,
    findings    INTEGER DEFAULT 0,
    metadata    TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS submitted_prs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    repo        TEXT NOT NULL,
    pr_number   INTEGER NOT NULL,
    pr_url      TEXT NOT NULL,
    title       TEXT NOT NULL,
    type        TEXT NOT NULL,
    status      TEXT DEFAULT 'open',
    branch      TEXT,
    fork        TEXT,
    created_at  TEXT,
    updated_at  TEXT,
    ci_fix_attempts INTEGER DEFAULT 0,
    discussion_replies INTEGER DEFAULT 0,
    UNIQUE(repo, pr_number)
);

CREATE TABLE IF NOT EXISTS findings_cache (
    id          TEXT PRIMARY KEY,
    repo        TEXT NOT NULL,
    type        TEXT NOT NULL,
    severity    TEXT NOT NULL,
    title       TEXT NOT NULL,
    file_path   TEXT,
    status      TEXT DEFAULT 'new',
    created_at  TEXT
);

CREATE TABLE IF NOT EXISTS run_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at  TEXT,
    finished_at TEXT,
    repos_analyzed INTEGER DEFAULT 0,
    prs_created  INTEGER DEFAULT 0,
    findings     INTEGER DEFAULT 0,
    errors       INTEGER DEFAULT 0,
    metadata     TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS pr_outcomes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    repo        TEXT NOT NULL,
    pr_number   INTEGER NOT NULL,
    pr_url      TEXT NOT NULL,
    pr_type     TEXT NOT NULL,
    outcome     TEXT NOT NULL,
    feedback    TEXT DEFAULT '',
    time_to_close_hours REAL DEFAULT 0,
    recorded_at TEXT,
    UNIQUE(repo, pr_number)
);

CREATE TABLE IF NOT EXISTS repo_preferences (
    repo        TEXT PRIMARY KEY,
    preferred_types TEXT DEFAULT '[]',
    rejected_types  TEXT DEFAULT '[]',
    merge_rate  REAL DEFAULT 0.0,
    avg_review_hours REAL DEFAULT 0.0,
    notes       TEXT DEFAULT '',
    updated_at  TEXT
);

CREATE TABLE IF NOT EXISTS blacklisted_repos (
    repo            TEXT PRIMARY KEY,
    reason          TEXT NOT NULL,
    pr_number       INTEGER,
    blacklisted_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS api_usage_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   REAL NOT NULL,
    provider    TEXT NOT NULL
);
"""


class Memory:
    """Persistent memory backed by SQLite."""

    def __init__(self, db_path: str | Path):
        self._db_path = Path(db_path).expanduser()
        self._db: aiosqlite.Connection | None = None

    async def init(self):
        """Initialize database connection and schema."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(str(self._db_path))
        # Enable Write-Ahead Logging for concurrent read/write safety
        await self._db.execute("PRAGMA journal_mode=WAL;")
        await self._db.executescript(SCHEMA)
        # DEBT-04: Add index for sliding-window quota queries on (provider, timestamp)
        await self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_api_usage ON api_usage_log(provider, timestamp)"
        )
        await self._db.commit()

        # ── Migrations ────────────────────────────────────────────────────
        # Add columns to existing databases that lack them.
        for col in (
            "ci_fix_attempts INTEGER DEFAULT 0",
            "discussion_replies INTEGER DEFAULT 0",
        ):
            try:
                await self._db.execute(
                    f"ALTER TABLE submitted_prs ADD COLUMN {col}"
                )
                await self._db.commit()
            except Exception:
                pass  # column already exists

        logger.info("Memory initialized at %s", self._db_path)

    async def close(self):
        if self._db:
            await self._db.close()

    # ── Repos ──────────────────────────────────────────────────────────────

    async def has_analyzed(self, full_name: str) -> bool:
        """Check if a repo has been analyzed before."""
        cursor = await self._db.execute(
            "SELECT 1 FROM analyzed_repos WHERE full_name = ?", (full_name,)
        )
        return await cursor.fetchone() is not None

    async def record_analysis(self, full_name: str, language: str, stars: int, findings_count: int):
        """Record that a repo was analyzed."""
        await self._db.execute(
            """INSERT OR REPLACE INTO analyzed_repos
               (full_name, language, stars, analyzed_at, findings)
               VALUES (?, ?, ?, ?, ?)""",
            (full_name, language, stars, datetime.now(UTC).isoformat(), findings_count),
        )
        await self._db.commit()

    async def get_analyzed_repos(self, limit: int = 50) -> list[dict]:
        """Get recently analyzed repos."""
        cursor = await self._db.execute(
            "SELECT * FROM analyzed_repos ORDER BY analyzed_at DESC LIMIT ?", (limit,)
        )
        rows = await cursor.fetchall()
        cols = [d[0] for d in cursor.description]
        return [dict(zip(cols, row, strict=False)) for row in rows]

    # ── PRs ────────────────────────────────────────────────────────────────

    async def record_pr(
        self,
        repo: str,
        pr_number: int,
        pr_url: str,
        title: str,
        pr_type: str,
        branch: str = "",
        fork: str = "",
    ):
        """Record a submitted PR."""
        now = datetime.now(UTC).isoformat()
        await self._db.execute(
            """INSERT OR REPLACE INTO submitted_prs
               (repo, pr_number, pr_url, title, type, branch, fork, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (repo, pr_number, pr_url, title, pr_type, branch, fork, now, now),
        )
        await self._db.commit()

    async def record_issue_proposal(
        self,
        repo: str,
        issue_number: int,
        issue_url: str,
        title: str,
        finding_type: str,
        finding_title: str,
        file_path: str = "",
    ):
        """Record an Issue-First proposal (Route B — waiting for maintainer approval)."""
        now = datetime.now(UTC).isoformat()
        # Re-use submitted_prs table with type='issue_proposal' and pr_number=issue_number
        await self._db.execute(
            """INSERT OR REPLACE INTO submitted_prs
               (repo, pr_number, pr_url, title, type, branch, fork, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                repo,
                issue_number,
                issue_url,
                title,
                "issue_proposal",
                "",  # branch — no branch for issues
                finding_title[:100],  # re-purpose 'fork' field as finding_title cache
                now,
                now,
            ),
        )
        await self._db.commit()
        logger.info(
            "📝 Issue-First proposal recorded: %s/#%d — '%s' (type=%s, file=%s)",
            repo,
            issue_number,
            title,
            finding_type,
            file_path,
        )

    async def update_pr_status(self, repo: str, pr_number: int, status: str):
        """Update PR status."""
        await self._db.execute(
            "UPDATE submitted_prs SET status = ?, updated_at = ? WHERE repo = ? AND pr_number = ?",
            (status, datetime.now(UTC).isoformat(), repo, pr_number),
        )
        await self._db.commit()

    async def get_prs(self, status: str | None = None, limit: int = 50) -> list[dict]:
        """Get submitted PRs, optionally filtered by status."""
        if status:
            cursor = await self._db.execute(
                "SELECT * FROM submitted_prs WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                (status, limit),
            )
        else:
            cursor = await self._db.execute(
                "SELECT * FROM submitted_prs ORDER BY created_at DESC LIMIT ?", (limit,)
            )
        rows = await cursor.fetchall()
        cols = [d[0] for d in cursor.description]
        return [dict(zip(cols, row, strict=False)) for row in rows]

    async def get_today_pr_count(self) -> int:
        """Get number of PRs created today (local date, UTC-offset-aware)."""
        # Use LOCAL date — created_at is stored as UTC ISO string, but represents
        # a local wall-clock moment. At 01:00 UTC+7, UTC date is yesterday (18:00 UTC
        # Mar 28), so UTC-based query would miss today's local PRs.
        # Convert: get current UTC time, shift to local, extract local date.
        utc_now = datetime.now(UTC)
        local_now = utc_now.astimezone()  # local timezone from OS
        today_local = local_now.date().isoformat()
        cursor = await self._db.execute(
            "SELECT COUNT(*) FROM submitted_prs WHERE created_at LIKE ?",
            (f"{today_local}%",),
        )
        row = await cursor.fetchone()
        return row[0] if row else 0

    async def get_repo_prs(self, repo: str) -> list[dict]:
        """Get all PRs previously submitted for a specific repo."""
        cursor = await self._db.execute(
            "SELECT * FROM submitted_prs WHERE repo = ? ORDER BY created_at DESC",
            (repo,),
        )
        rows = await cursor.fetchall()
        cols = [d[0] for d in cursor.description]
        return [dict(zip(cols, row, strict=False)) for row in rows]

    async def get_friendly_repos_for_hunting(
        self,
        limit: int = 3,
        cooldown_days: int = 7,
    ) -> list[dict]:
        """Return merged repos that are off cooldown for re-hunting.

        Friendly repos = repos where we have at least one merged PR.
        Cooldown = repo must NOT have been analyzed in the last cooldown_days
        to avoid spamming maintainers who trusted us.
        """
        cutoff = (
            datetime.now(UTC) - timedelta(days=cooldown_days)
        ).isoformat()

        cursor = await self._db.execute(
            """
            SELECT DISTINCT
                sr.repo                         AS full_name,
                ar.language,
                ar.stars,
                ar.analyzed_at,
                sr.created_at                   AS merged_at,
                sr.title                        AS merged_pr_title
            FROM submitted_prs AS sr
            LEFT JOIN analyzed_repos AS ar ON sr.repo = ar.full_name
            WHERE sr.status = 'merged'
              AND (ar.analyzed_at IS NULL OR ar.analyzed_at < ?)
            ORDER BY sr.created_at DESC
            LIMIT ?
            """,
            (cutoff, limit),
        )
        rows = await cursor.fetchall()
        cols = [d[0] for d in cursor.description]
        result = [dict(zip(cols, row, strict=False)) for row in rows]
        logger.info(
            "🏠 Familiar Grounds: found %d friendly repos off cooldown (limit=%d, cooldown=%dd)",
            len(result),
            limit,
            cooldown_days,
        )
        return result

    # ── CI Fix Attempts ───────────────────────────────────────────────────

    async def get_ci_fix_attempts(self, repo: str, pr_number: int) -> int:
        """Get the number of CI auto-fix attempts for a PR."""
        cursor = await self._db.execute(
            "SELECT ci_fix_attempts FROM submitted_prs WHERE repo = ? AND pr_number = ?",
            (repo, pr_number),
        )
        row = await cursor.fetchone()
        return row[0] if row else 0

    async def increment_ci_fix_attempts(self, repo: str, pr_number: int) -> int:
        """Increment the CI fix attempt counter for a PR. Returns the new count."""
        await self._db.execute(
            "UPDATE submitted_prs SET ci_fix_attempts = ci_fix_attempts + 1, updated_at = ? "
            "WHERE repo = ? AND pr_number = ?",
            (datetime.now(UTC).isoformat(), repo, pr_number),
        )
        await self._db.commit()
        return await self.get_ci_fix_attempts(repo, pr_number)

    # ── Discussion Reply Tracking ──────────────────────────────────────────

    async def get_discussion_replies(self, repo: str, pr_number: int) -> int:
        """Get the number of discussion replies the bot sent on a PR."""
        cursor = await self._db.execute(
            "SELECT discussion_replies FROM submitted_prs WHERE repo = ? AND pr_number = ?",
            (repo, pr_number),
        )
        row = await cursor.fetchone()
        return row[0] if row else 0

    async def increment_discussion_replies(self, repo: str, pr_number: int) -> int:
        """Increment the discussion reply counter for a PR. Returns the new count."""
        await self._db.execute(
            "UPDATE submitted_prs SET discussion_replies = discussion_replies + 1, updated_at = ? "
            "WHERE repo = ? AND pr_number = ?",
            (datetime.now(UTC).isoformat(), repo, pr_number),
        )
        await self._db.commit()
        return await self.get_discussion_replies(repo, pr_number)

    # ── Run Log ────────────────────────────────────────────────────────────

    async def start_run(self) -> int:
        """Record the start of a pipeline run. Returns run ID."""
        cursor = await self._db.execute(
            "INSERT INTO run_log (started_at) VALUES (?)",
            (datetime.now(UTC).isoformat(),),
        )
        await self._db.commit()
        return cursor.lastrowid

    async def finish_run(
        self,
        run_id: int,
        repos_analyzed: int,
        prs_created: int,
        findings: int,
        errors: int,
    ):
        """Record the completion of a pipeline run."""
        await self._db.execute(
            """UPDATE run_log
               SET finished_at = ?, repos_analyzed = ?, prs_created = ?,
                   findings = ?, errors = ?
               WHERE id = ?""",
            (datetime.now(UTC).isoformat(), repos_analyzed, prs_created, findings, errors, run_id),
        )
        await self._db.commit()

    async def get_stats(self) -> dict:
        """Get overall statistics."""
        stats = {}

        cursor = await self._db.execute("SELECT COUNT(*) FROM analyzed_repos")
        stats["total_repos_analyzed"] = (await cursor.fetchone())[0]

        cursor = await self._db.execute("SELECT COUNT(*) FROM submitted_prs")
        stats["total_prs_submitted"] = (await cursor.fetchone())[0]

        cursor = await self._db.execute(
            "SELECT COUNT(*) FROM submitted_prs WHERE status = 'merged'"
        )
        stats["prs_merged"] = (await cursor.fetchone())[0]

        cursor = await self._db.execute("SELECT COUNT(*) FROM run_log")
        stats["total_runs"] = (await cursor.fetchone())[0]

        return stats

    async def get_run_history(self, limit: int = 20) -> list[dict]:
        """Get recent run history."""
        cursor = await self._db.execute(
            "SELECT * FROM run_log ORDER BY started_at DESC LIMIT ?",
            (limit,),
        )
        rows = await cursor.fetchall()
        cols = [d[0] for d in cursor.description]
        return [dict(zip(cols, row, strict=False)) for row in rows]

    # ── Outcome Learning ──────────────────────────────────────────────────

    async def record_outcome(
        self,
        repo: str,
        pr_number: int,
        pr_url: str,
        pr_type: str,
        outcome: str,
        feedback: str = "",
        time_to_close_hours: float = 0.0,
    ):
        """Record the outcome of a PR (merged, closed, rejected)."""
        await self._db.execute(
            """INSERT OR REPLACE INTO pr_outcomes
               (repo, pr_number, pr_url, pr_type, outcome, feedback,
                time_to_close_hours, recorded_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                repo,
                pr_number,
                pr_url,
                pr_type,
                outcome,
                feedback,
                time_to_close_hours,
                datetime.now(UTC).isoformat(),
            ),
        )
        await self._db.commit()

        # Auto-update repo preferences
        await self._update_repo_preferences(repo)

    async def _update_repo_preferences(self, repo: str):
        """Recompute repo preferences from outcome history."""
        import json

        cursor = await self._db.execute(
            "SELECT pr_type, outcome, time_to_close_hours FROM pr_outcomes WHERE repo = ?",
            (repo,),
        )
        rows = await cursor.fetchall()
        if not rows:
            return

        merged_types: list[str] = []
        rejected_types: list[str] = []
        total_hours = 0.0
        merged_count = 0

        for pr_type, outcome, hours in rows:
            if outcome == "merged":
                merged_types.append(pr_type)
                merged_count += 1
                total_hours += hours or 0
            elif outcome in ("closed", "rejected"):
                rejected_types.append(pr_type)

        merge_rate = merged_count / len(rows) if rows else 0.0
        avg_hours = total_hours / merged_count if merged_count else 0.0

        await self._db.execute(
            """INSERT OR REPLACE INTO repo_preferences
               (repo, preferred_types, rejected_types, merge_rate,
                avg_review_hours, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (
                repo,
                json.dumps(list(set(merged_types))),
                json.dumps(list(set(rejected_types))),
                round(merge_rate, 3),
                round(avg_hours, 1),
                datetime.now(UTC).isoformat(),
            ),
        )
        await self._db.commit()

    async def get_repo_preferences(self, repo: str) -> dict | None:
        """Get learned preferences for a specific repo."""
        import json

        cursor = await self._db.execute("SELECT * FROM repo_preferences WHERE repo = ?", (repo,))
        row = await cursor.fetchone()
        if not row:
            return None
        cols = [d[0] for d in cursor.description]
        prefs = dict(zip(cols, row, strict=False))
        prefs["preferred_types"] = json.loads(prefs.get("preferred_types", "[]"))
        prefs["rejected_types"] = json.loads(prefs.get("rejected_types", "[]"))
        return prefs

    async def get_rejection_patterns(self, limit: int = 20) -> list[dict]:
        """Get common rejection reasons across all repos."""
        cursor = await self._db.execute(
            """SELECT repo, pr_type, feedback
               FROM pr_outcomes
               WHERE outcome IN ('closed', 'rejected') AND feedback != ''
               ORDER BY recorded_at DESC LIMIT ?""",
            (limit,),
        )
        rows = await cursor.fetchall()
        return [{"repo": r[0], "pr_type": r[1], "feedback": r[2]} for r in rows]

    async def get_outcome_stats(self) -> dict:
        """Get outcome statistics."""
        stats = {}
        cursor = await self._db.execute(
            "SELECT outcome, COUNT(*) FROM pr_outcomes GROUP BY outcome"
        )
        for outcome, count in await cursor.fetchall():
            stats[outcome] = count
        cursor = await self._db.execute("SELECT AVG(merge_rate) FROM repo_preferences")
        row = await cursor.fetchone()
        stats["avg_merge_rate"] = round(row[0], 3) if row and row[0] else 0.0
        return stats

    # ── Blacklist ───────────────────────────────────────────────────────────

    async def blacklist_repo(
        self,
        owner: str,
        repo_name: str,
        reason: str,
        pr_number: int | None = None,
    ) -> None:
        """Permanently blacklist a repository so it is never targeted again."""
        full_name = f"{owner}/{repo_name}"
        await self._db.execute(
            """INSERT OR REPLACE INTO blacklisted_repos
               (repo, reason, pr_number, blacklisted_at)
               VALUES (?, ?, ?, ?)""",
            (full_name, reason[:1000], pr_number, datetime.now(UTC).isoformat()),
        )
        await self._db.commit()
        logger.warning("🚫 Blacklisted repo %s: %s", full_name, reason[:120])

    async def is_blacklisted(self, full_name: str) -> bool:
        """Check if a repository has been blacklisted."""
        cursor = await self._db.execute(
            "SELECT 1 FROM blacklisted_repos WHERE repo = ?", (full_name,)
        )
        return await cursor.fetchone() is not None

    async def get_blacklisted_repos(self) -> list[dict]:
        """Get all blacklisted repositories."""
        async with self._db.execute("SELECT repo, reason, pr_number, blacklisted_at FROM blacklisted_repos") as cursor:
            rows = await cursor.fetchall()
            return [
                {
                    "repo": r[0],
                    "reason": r[1],
                    "pr_number": r[2],
                    "blacklisted_at": r[3],
                }
                for r in rows
            ]

    # ── Safe Quota Tracking (Minimax Overdrive) ──────────────────────────

    async def check_and_record_llm_quota(self, provider: str = "minimax") -> None:
        """Sliding-window quota checker and recorder for LLM providers.

        Minimax plan limits: 1000 requests per 5 hours, 10000 per 7 days.
        Uses a 5% safety buffer (950 / 9500) to prevent overshoot.

        On success, atomically records the request in the usage log.
        On threshold breach, raises LLMRateLimitError so callers can
        react (e.g. take a long cooldown sleep).
        """
        import time

        from farm_agent.core.exceptions import LLMRateLimitError

        now = time.time()

        # Sliding window boundaries
        five_hours_ago = now - 18_000.0       # 5 * 3600
        seven_days_ago = now - 604_800.0      # 7 * 24 * 3600

        # ── Count requests in each window ──────────────────────────────
        cursor = await self._db.execute(
            "SELECT COUNT(1) FROM api_usage_log WHERE provider = ? AND timestamp >= ?",
            (provider, five_hours_ago),
        )
        row = await cursor.fetchone()
        count_5h = row[0] if row else 0

        cursor = await self._db.execute(
            "SELECT COUNT(1) FROM api_usage_log WHERE provider = ? AND timestamp >= ?",
            (provider, seven_days_ago),
        )
        row = await cursor.fetchone()
        count_7d = row[0] if row else 0

        # ── Safety thresholds (95% of hard limits) ─────────────────────
        if count_5h >= 950:
            logger.warning(
                "LLM quota BREACHED: %s 5-hour window has %d requests (limit 950).",
                provider, count_5h,
            )
            raise LLMRateLimitError(
                f"{provider} 5-hour quota exhausted: {count_5h}/950 requests"
            )

        if count_7d >= 9500:
            logger.warning(
                "LLM quota BREACHED: %s 7-day window has %d requests (limit 9500).",
                provider, count_7d,
            )
            raise LLMRateLimitError(
                f"{provider} 7-day quota exhausted: {count_7d}/9500 requests"
            )

        # ── Record this request atomically ─────────────────────────────
        await self._db.execute(
            "INSERT INTO api_usage_log (timestamp, provider) VALUES (?, ?)",
            (now, provider),
        )

        # ── Time-based periodic cleanup: purge entries older than 7 days ──
        # DEBT-06: Replace volatile counter with time-based trigger (hourly cleanup)
        if not hasattr(self, "_last_quota_cleanup"):
            self._last_quota_cleanup = 0.0

        if now - self._last_quota_cleanup >= 3600:  # 1 hour
            await self._db.execute(
                "DELETE FROM api_usage_log WHERE timestamp < ?",
                (seven_days_ago,),
            )
            self._last_quota_cleanup = now

        await self._db.commit()
