"""Persistent memory system using SQLite.

Tracks analyzed repos, submitted PRs, and learning data
to avoid duplicate work and improve over time.
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
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

CREATE TABLE IF NOT EXISTS task_schedule (
    task_key    TEXT PRIMARY KEY,
    next_run    TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS knowledge_base (
    repo_name   TEXT NOT NULL,
    entry_type  TEXT NOT NULL,
    content     TEXT NOT NULL,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(repo_name, entry_type, content)
);

CREATE TABLE IF NOT EXISTS target_repos (
    repo_url        TEXT PRIMARY KEY,
    status          TEXT DEFAULT 'PENDING',
    scanned_at      REAL,
    language        TEXT,
    bounty_amount   TEXT,
    diamond_target  INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS repo_style_guides (
    repo            TEXT PRIMARY KEY,
    style_summary   TEXT NOT NULL,
    contributing_md TEXT DEFAULT '',
    pr_template     TEXT DEFAULT '',
    created_at      TEXT,
    updated_at      TEXT
);
"""


class Memory:
    """Persistent memory backed by SQLite."""

    def __init__(self, db_path: str | Path):
        self._db_path = Path(db_path).expanduser()
        self._db: aiosqlite.Connection | None = None
        self._quota_lock = asyncio.Lock()

    async def init(self):
        """Initialize database connection and schema."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(str(self._db_path))
        # Enable Write-Ahead Logging for concurrent read/write safety.
        # Fall back to DELETE journal mode if WAL fails (e.g. on some Docker
        # volume filesystems that don't support -wal/-shm auxiliary files).
        try:
            await self._db.execute("PRAGMA journal_mode=WAL;")
            await self._db.execute("PRAGMA wal_autocheckpoint=1000;")
        except sqlite3.OperationalError as e:
            logger.warning("WAL mode unavailable (%s), falling back to DELETE journal mode", e)
            await self._db.execute("PRAGMA journal_mode=DELETE;")
        # P1-OPSEC-9: Enable foreign key enforcement
        await self._db.execute("PRAGMA foreign_keys = ON;")
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
                await self._db.execute(f"ALTER TABLE submitted_prs ADD COLUMN {col}")
                await self._db.commit()
            except sqlite3.OperationalError as e:
                if "already exists" in str(e) or "duplicate column name" in str(e).lower():
                    logger.debug("Schema migration skipped: column already exists — %s", e)
                else:
                    logger.error("Schema migration failed critically: %s", e)
                    raise  # re-raise structural failures
            except Exception as e:
                logger.error("Unexpected DB error during migration: %s", e)
                raise

        await self.cleanup_old_records()
        logger.info("Memory initialized at %s", self._db_path)

    async def close(self):
        if self._db:
            await self._db.close()

    async def checkpoint(self) -> None:
        """Checkpoint WAL and truncate if safe. Call this periodically or on shutdown."""
        if self._db is None:
            return
        try:
            # WAL checkpoint is only valid when journal_mode=WAL
            await self._db.execute("PRAGMA journal_mode;")
            rows = await self._db.execute("PRAGMA journal_mode;").fetchall()
            if rows and rows[0][0].upper() == "WAL":
                await self._db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except Exception as e:
            logger.warning("WAL checkpoint failed (may be in DELETE mode): %s", e)

    async def cleanup_old_records(self, days: int = 30) -> dict[str, int]:
        """Delete records older than `days`. Call on startup or daily.

        Returns dict of table->deleted_count.
        """
        deleted: dict[str, int] = {}
        cutoff = (datetime.now(UTC) - timedelta(days=days)).isoformat()

        try:
            # api_usage_log: keep 30 days
            cur = await self._db.execute("DELETE FROM api_usage_log WHERE timestamp < ?", (cutoff,))
            deleted["api_usage_log"] = cur.rowcount

            # task_schedule: delete completed entries older than 7 days
            task_cutoff = (datetime.now(UTC) - timedelta(days=7)).isoformat()
            cur = await self._db.execute(
                "DELETE FROM task_schedule WHERE updated_at < ?", (task_cutoff,)
            )
            deleted["task_schedule"] = cur.rowcount

            await self._db.commit()
            logger.info("TTL cleanup deleted: %s", deleted)
        except Exception as e:
            logger.error("TTL cleanup failed: %s", e)
        return deleted

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

    async def delete_submitted_prs_for_repo(self, repo_full_name: str) -> int:
        """Delete all submitted PR records for a repo. Call this when purging a repo.

        Returns the number of rows deleted.
        """
        cur = await self._db.execute(
            "DELETE FROM submitted_prs WHERE repo = ?",
            (repo_full_name,),
        )
        await self._db.commit()
        return cur.rowcount

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
        """Get number of PRs created today (UTC).

        P0-FIX: Generate UTC date in Python instead of relying on SQLite's
        date('now') which uses the system timezone. This ensures quota counts
        strictly align with UTC midnights regardless of server locale.
        """
        today_utc = datetime.now(UTC).date().isoformat()
        cursor = await self._db.execute(
            "SELECT COUNT(*) FROM submitted_prs WHERE date(created_at) = ?",
            (today_utc,),
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
        """Increment the CI fix attempt counter for a PR. Returns the new count.

        P2-FIX: Use RETURNING clause to avoid TOCTOU race condition
        between UPDATE and SELECT in concurrent environments.
        """
        cursor = await self._db.execute(
            "UPDATE submitted_prs SET ci_fix_attempts = ci_fix_attempts + 1, updated_at = ? "
            "WHERE repo = ? AND pr_number = ? RETURNING ci_fix_attempts",
            (datetime.now(UTC).isoformat(), repo, pr_number),
        )
        row = await cursor.fetchone()
        await self._db.commit()
        return row[0] if row else 0

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
        """Increment the discussion reply counter for a PR. Returns the new count.

        P2-FIX: Use RETURNING clause to avoid TOCTOU race condition.
        """
        cursor = await self._db.execute(
            "UPDATE submitted_prs SET discussion_replies = discussion_replies + 1, updated_at = ? "
            "WHERE repo = ? AND pr_number = ? RETURNING discussion_replies",
            (datetime.now(UTC).isoformat(), repo, pr_number),
        )
        row = await cursor.fetchone()
        await self._db.commit()
        return row[0] if row else 0

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

    async def get_qa_lessons(self, repo_url: str) -> list[str]:
        """Retrieve QA lessons for a repository from the knowledge base.

        Returns a list of lesson strings sourced from past QA critiques.
        Used by the generator to avoid repeating past architectural mistakes.
        """
        if self._db is None:
            return []

        # Normalize repo_url to just the owner/name part
        repo_name = repo_url.rstrip("/")
        if "://" in repo_name:
            repo_name = repo_name.split("/")[-2] + "/" + repo_name.split("/")[-1]
        if repo_name.startswith("www."):
            repo_name = repo_name[4:]

        try:
            cursor = await self._db.execute(
                """SELECT content FROM knowledge_base
                   WHERE repo_name = ? AND entry_type = 'qa_lesson'
                   ORDER BY created_at DESC""",
                (repo_name,),
            )
            rows = await cursor.fetchall()
            return [r[0] for r in rows]
        except Exception as exc:
            logger.debug("Could not fetch QA lessons for %s: %s", repo_name, exc)
            return []

    async def record_qa_lesson(self, repo_name: str, content: str) -> None:
        """Record a QA lesson in the knowledge base."""
        if self._db is None:
            return

        try:
            await self._db.execute(
                """INSERT OR REPLACE INTO knowledge_base " \
                "(repo_name, entry_type, content, created_at)
                   VALUES (?, 'qa_lesson', ?, ?)""",
                (repo_name, content, datetime.now(UTC).isoformat()),
            )
            await self._db.commit()
        except Exception as exc:
            logger.debug("Could not record QA lesson for %s: %s", repo_name, exc)

    async def run_kb_garbage_collection(self, days: int = 90) -> int:
        """Purge stale knowledge base entries older than N days.

        Returns the number of deleted rows.
        """
        if self._db is None:
            return 0

        try:
            cursor = await self._db.execute(
                "DELETE FROM knowledge_base WHERE created_at < datetime('now', ?)",
                (f"-{days} days",),
            )
            await self._db.commit()
            deleted = cursor.rowcount
            if deleted > 0:
                logger.info(
                    "Garbage Collection: purged %d stale knowledge base entries " \
                    "(older than %d days)",
                    deleted,
                    days,
                )
            return deleted
        except Exception as exc:
            logger.error("KB garbage collection failed: %s", exc)
            return 0

    async def get_openrouter_usage_today(self) -> int:
        """Count OpenRouter API calls made today (UTC).

        Used by BloodhoundAnalyzer to enforce the red_team_daily_limit.
        """
        if self._db is None:
            return 0

        try:
            cursor = await self._db.execute(
                "SELECT COUNT(*) FROM api_usage_log WHERE provider = 'openrouter' " \
                "AND date(timestamp, 'unixepoch') = date('now')",
            )
            row = await cursor.fetchone()
            return row[0] if row else 0
        except Exception as exc:
            logger.debug("Could not query OpenRouter usage: %s", exc)
            return 0

    async def record_openrouter_usage(self) -> None:
        """Record an OpenRouter API call in the usage log."""
        if self._db is None:
            return

        import time as _time

        try:
            await self._db.execute(
                "INSERT INTO api_usage_log (timestamp, provider) VALUES (?, 'openrouter')",
                (_time.time(),),
            )
            await self._db.commit()
        except Exception as exc:
            logger.debug("Could not record OpenRouter usage: %s", exc)

    # ── Target Repo Management (Circular Target Loop) ────────────────────────

    async def seed_targets_from_json(self, json_path: Path) -> int:
        """Seed the target_repos table from a target_repo.json file.

        Uses INSERT OR IGNORE so existing rows (with progress) are never
        overwritten. This allows seamless upgrades from the JSON-based system.

        Returns the number of new rows inserted.
        """
        import json as _json

        if self._db is None:
            return 0

        json_path = Path(json_path)
        if not json_path.exists():
            logger.info("No target_repo.json found at %s — skipping seed", json_path)
            return 0

        try:
            raw = json_path.read_text(encoding="utf-8")
            entries = _json.loads(raw)
        except (_json.JSONDecodeError, OSError) as exc:
            logger.error("Failed to read target_repo.json for seeding: %s", exc)
            return 0

        inserted = 0
        for entry_data in entries:
            repo_url = entry_data.get("repo_url", "")
            if not repo_url:
                continue

            language = entry_data.get("language") or None
            status = entry_data.get("status", "PENDING")
            bounty = entry_data.get("bounty_amount")
            bounty_str = str(bounty) if bounty is not None else None
            diamond = 1 if entry_data.get("diamond_target") else 0

            scanned_at = None
            sa = entry_data.get("scanned_at")
            if sa is not None:
                try:
                    if isinstance(sa, str):
                        dt = datetime.fromisoformat(sa.replace("Z", "+00:00"))
                        scanned_at = dt.timestamp()
                    elif isinstance(sa, (int, float)):
                        scanned_at = float(sa)
                except (ValueError, TypeError):
                    scanned_at = None

            try:
                cursor = await self._db.execute(
                    """INSERT OR IGNORE INTO target_repos
                       (repo_url, status, scanned_at, language, bounty_amount, diamond_target)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (repo_url, status, scanned_at, language, bounty_str, diamond),
                )
                if cursor.rowcount == 1:
                    inserted += 1
            except Exception as exc:
                logger.debug("Seed skip for %s: %s", repo_url, exc)

        await self._db.commit()
        if inserted > 0:
            logger.info("Seeded %d target repos from %s", inserted, json_path)
        logger.info(f"Successfully seeded {inserted} targets from target_repo.json into SQLite.")
        return inserted

    async def get_next_target(self, excluded_languages: list[str] | None = None) -> dict | None:
        """Return the target repo with the oldest scanned_at (or NULL scanned_at first).

        Equivalent to the old JsonTargetDiscovery.get_next_target() but backed
        by SQLite for atomic reads and writes.

        Returns a dict with keys: repo_url, status, scanned_at, language,
        bounty_amount, diamond_target — or None if the table is empty.
        """
        if self._db is None:
            return None

        import time
        now_ts = time.time()

        if excluded_languages:
            placeholders = ",".join(["?"] * len(excluded_languages))
            query = f"""UPDATE target_repos
               SET scanned_at = ?
               WHERE repo_url = (SELECT repo_url FROM target_repos " \
               "WHERE LOWER(language) NOT IN ({placeholders}) " \
               "ORDER BY COALESCE(scanned_at, 0) ASC, rowid ASC LIMIT 1)
               RETURNING *"""
            params = (now_ts, *[lang.lower() for lang in excluded_languages])
        else:
            query = """UPDATE target_repos
               SET scanned_at = ?
               WHERE repo_url = (SELECT repo_url FROM target_repos " \
               "ORDER BY COALESCE(scanned_at, 0) ASC, rowid ASC LIMIT 1)
               RETURNING *"""
            params = (now_ts,)

        cursor = await self._db.execute(query, params)
        row = await cursor.fetchone()
        await self._db.commit()

        if row is None:
            return None

        cols = [d[0] for d in cursor.description]
        result = dict(zip(cols, row, strict=False))
        logger.info(
            f"[TARGET ACQUIRED] Repo: {result.get('repo_url')} | " \
            f"Language: {result.get('language')} | " \
            f"Bounty: {result.get('bounty_amount')} | " \
            f"Diamond: {result.get('diamond_target')}"
        )
        return result

    async def mark_target_status(
        self,
        repo_url: str,
        new_status: str,
        update_timestamp: bool = True,
    ) -> None:
        """Update the status of a target repo in the database.

        If update_timestamp is True, also updates scanned_at to the current
        Unix timestamp (for crash-safe rotation: call with update_timestamp=True
        BEFORE making any API or LLM calls).

        Args:
            repo_url: The repository URL to update.
            new_status: New status string (e.g. 'SCANNED', 'COMPLETED_NO_VULN',
                        'PR_SUBMITTED', 'COMPLETED_TOO_COMPLEX').
            update_timestamp: If True, also set scanned_at = current time.
        """
        if self._db is None:
            return

        import time as _time

        if update_timestamp:
            now_ts = _time.time()
            await self._db.execute(
                "UPDATE target_repos SET status = ?, scanned_at = ? WHERE repo_url = ?",
                (new_status, now_ts, repo_url),
            )
        else:
            await self._db.execute(
                "UPDATE target_repos SET status = ? WHERE repo_url = ?",
                (new_status, repo_url),
            )
        await self._db.commit()
        logger.debug("Target %s → status=%s (timestamp=%s)", repo_url, new_status, update_timestamp)

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
        query = "SELECT repo, reason, pr_number, blacklisted_at FROM blacklisted_repos"
        async with self._db.execute(query) as cursor:
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

        async with self._quota_lock:
            now = time.time()

            # Sliding window boundaries
            five_hours_ago = now - 18_000.0  # 5 * 3600
            seven_days_ago = now - 604_800.0  # 7 * 24 * 3600

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
                    provider,
                    count_5h,
                )
                raise LLMRateLimitError(
                    f"{provider} 5-hour quota exhausted: {count_5h}/950 requests"
                )

            if count_7d >= 9500:
                logger.warning(
                    "LLM quota BREACHED: %s 7-day window has %d requests (limit 9500).",
                    provider,
                    count_7d,
                )
                raise LLMRateLimitError(
                    f"{provider} 7-day quota exhausted: {count_7d}/9500 requests"
                )

            # ── Record this request atomically ─────────────────────────────
            await self._db.execute(
                "INSERT INTO api_usage_log (timestamp, provider) VALUES (?, ?)",
                (now, provider),
            )

            # ── DB-backed periodic cleanup: purge entries older than 7 days ──
            # P0-FIX (v2): Replaced volatile `self._last_quota_cleanup` with
            # persistent `task_schedule` table lookup.  Multiple processes or
            # CLI invocations now coordinate cleanups via the DB, not RAM.
            last_cleanup_iso = await self.get_task_schedule("quota_cleanup")
            run_cleanup = False
            if last_cleanup_iso is None:
                run_cleanup = True
            else:
                try:
                    last_ts = datetime.fromisoformat(last_cleanup_iso).timestamp()
                    run_cleanup = now - last_ts >= 3600  # 1 hour
                except (ValueError, TypeError):
                    run_cleanup = True  # corrupted entry — force cleanup

            if run_cleanup:
                await self._db.execute(
                    "DELETE FROM api_usage_log WHERE timestamp < ?",
                    (seven_days_ago,),
                )
                await self.set_task_schedule(
                    "quota_cleanup",
                    datetime.now(UTC).isoformat(),
                )

            await self._db.commit()

    # ── Task Schedule (for non-blocking skip logic) ─────────────────────────

    async def get_task_schedule(self, task_key: str) -> str | None:
        """Get the next_run ISO timestamp for a task, or None if not scheduled."""
        cursor = await self._db.execute(
            "SELECT next_run FROM task_schedule WHERE task_key = ?",
            (task_key,),
        )
        row = await cursor.fetchone()
        return row[0] if row else None

    async def set_task_schedule(self, task_key: str, next_run: str) -> None:
        """Set the next_run ISO timestamp for a task."""
        await self._db.execute(
            """INSERT OR REPLACE INTO task_schedule (task_key, next_run, updated_at)
               VALUES (?, ?, ?)""",
            (task_key, next_run, datetime.now(UTC).isoformat()),
        )
        await self._db.commit()

    # ── Repo Style Guides (Diplomat Protocol) ─────────────────────────────

    async def save_style_guide(
        self,
        repo: str,
        style_summary: str,
        contributing_md: str = "",
        pr_template: str = "",
    ) -> None:
        """Save a summarized repo style guide to avoid re-parsing on subsequent hunts."""
        if self._db is None:
            return
        now = datetime.now(UTC).isoformat()
        await self._db.execute(
            """INSERT OR REPLACE INTO repo_style_guides
               (repo, style_summary, contributing_md, pr_template, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (repo, style_summary, contributing_md[:8000], pr_template[:8000], now, now),
        )
        await self._db.commit()
        logger.debug("Saved style guide for %s (%d chars)", repo, len(style_summary))

    async def get_style_guide(self, repo: str) -> dict | None:
        """Retrieve a cached style guide summary for a repo.

        Returns a dict with keys: repo, style_summary, contributing_md, pr_template,
        or None if not cached.
        """
        if self._db is None:
            return None
        cursor = await self._db.execute(
            "SELECT repo, style_summary, contributing_md, pr_template " \
            "FROM repo_style_guides WHERE repo = ?",
            (repo,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        cols = [d[0] for d in cursor.description]
        return dict(zip(cols, row, strict=False))

