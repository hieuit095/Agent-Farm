"""Persistent memory system using SQLite.

Tracks analyzed repos, submitted PRs, and learning data
to avoid duplicate work and improve over time.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import logging
import sqlite3
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import aiosqlite

from farm_agent.security.state import CandidateStatus, EvidenceKind, SecurityGateError
from farm_agent.security.scope import ScanManifest
from farm_agent.security.threat_model import ThreatModel
from farm_agent.security.coverage import CoverageOutcome, CoverageSummary

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
CREATE TABLE IF NOT EXISTS scan_events (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id      TEXT NOT NULL,
    candidate_id TEXT,
    repo         TEXT NOT NULL,
    pipeline     TEXT NOT NULL,
    stage        TEXT NOT NULL,
    outcome      TEXT NOT NULL,
    reason_code  TEXT,
    count        INTEGER NOT NULL DEFAULT 1,
    duration_ms  INTEGER,
    model        TEXT,
    input_tokens INTEGER,
    output_tokens INTEGER,
    cost_usd     REAL,
    created_at   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS security_candidates (
    id             TEXT PRIMARY KEY,
    scan_id        TEXT NOT NULL,
    repo           TEXT NOT NULL,
    target_commit  TEXT NOT NULL,
    file_path      TEXT NOT NULL,
    title          TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'DISCOVERED',
    reason_code    TEXT,
    closing_evidence_id TEXT,
    root_cause_fingerprint TEXT,
    defer_reason   TEXT,
    investigation_json TEXT,
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS security_evidence (
    id            TEXT PRIMARY KEY,
    candidate_id  TEXT NOT NULL REFERENCES security_candidates(id),
    kind          TEXT NOT NULL,
    content_hash  TEXT NOT NULL,
    target_commit TEXT NOT NULL,
    origin        TEXT NOT NULL DEFAULT 'unknown',
    created_at    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS security_proofs (
    proof_id                TEXT PRIMARY KEY,
    candidate_id            TEXT NOT NULL REFERENCES security_candidates(id),
    scan_id                 TEXT NOT NULL,
    repo                    TEXT NOT NULL,
    target_commit           TEXT NOT NULL,
    oracle_digest           TEXT NOT NULL,
    surface                 TEXT NOT NULL,
    risk_class              TEXT NOT NULL,
    outcome                 TEXT NOT NULL,
    vulnerability_confirmed INTEGER,
    patch_status            TEXT NOT NULL,
    after_endpoint          TEXT NOT NULL DEFAULT 'inconclusive',
    evidence_hash           TEXT NOT NULL DEFAULT '',
    record_json             TEXT NOT NULL,
    record_hash             TEXT NOT NULL,
    valid                   INTEGER NOT NULL DEFAULT 1,
    created_at              TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS scan_manifests (
    scan_id       TEXT PRIMARY KEY,
    repo          TEXT NOT NULL,
    target_commit TEXT NOT NULL,
    manifest_json TEXT NOT NULL,
    manifest_hash TEXT NOT NULL,
    requests_used INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS scan_threat_models (
    scan_id    TEXT PRIMARY KEY REFERENCES scan_manifests(scan_id),
    version    INTEGER NOT NULL,
    model_json TEXT NOT NULL,
    model_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS scan_coverage (
    scan_id       TEXT NOT NULL REFERENCES scan_manifests(scan_id),
    surface       TEXT NOT NULL,
    risk_class    TEXT NOT NULL,
    outcome       TEXT NOT NULL DEFAULT 'not_tested',
    evidence_hash TEXT,
    reason_code   TEXT,
    updated_at    TEXT NOT NULL,
    PRIMARY KEY (scan_id, surface, risk_class)
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
        self._security_lock = asyncio.Lock()

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
        # DEBT-04 RESOLVED: Composite index for sliding-window quota queries.
        # Covers: provider + timestamp range comparisons in check_and_record_llm_quota()
        # and get_openrouter_usage_today(). Without this, every quota check
        # was a full table scan on api_usage_log.
        await self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_api_usage ON api_usage_log(provider, timestamp)"
        )
        # Secondary index optimized for the periodic DELETE cleanup (timestamp ASC
        # for range deletes of old rows — different access pattern from the COUNT queries).
        await self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_api_usage_cleanup ON api_usage_log(timestamp)"
        )
        await self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_scan_events_scan ON scan_events(scan_id, stage)"
        )
        await self._db.execute(
            "CREATE INDEX IF NOT EXISTS idx_security_candidates_scan "
            "ON security_candidates(scan_id, status)"
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

        for col in (
            "after_endpoint TEXT NOT NULL DEFAULT 'inconclusive'",
            "evidence_hash TEXT NOT NULL DEFAULT ''",
        ):
            try:
                await self._db.execute(f"ALTER TABLE security_proofs ADD COLUMN {col}")
                await self._db.commit()
            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e).lower():
                    logger.debug("Schema migration skipped: %s", e)
                else:
                    logger.error("Schema migration failed critically: %s", e)
                    raise

        for table, col in (
            ("security_candidates", "root_cause_fingerprint TEXT"),
            ("security_candidates", "defer_reason TEXT"),
            ("security_candidates", "investigation_json TEXT"),
            ("security_evidence", "origin TEXT NOT NULL DEFAULT 'unknown'"),
        ):
            try:
                await self._db.execute(f"ALTER TABLE {table} ADD COLUMN {col}")
                await self._db.commit()
            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e).lower():
                    logger.debug("Schema migration skipped: %s", e)
                else:
                    logger.error("Schema migration failed critically: %s", e)
                    raise

        await self._db.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_security_candidates_root_cause "
            "ON security_candidates(repo, target_commit, root_cause_fingerprint) "
            "WHERE root_cause_fingerprint IS NOT NULL"
        )
        await self._db.commit()

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

    async def create_security_candidate(
        self, *, scan_id: str, repo: str, target_commit: str,
        file_path: str, title: str, root_cause_fingerprint: str | None = None,
        investigation_input: dict | None = None,
    ) -> str:
        """Admit one candidate. Idempotent when a root-cause fingerprint is given."""
        candidate_id = uuid.uuid4().hex
        now = datetime.now(UTC).isoformat()
        investigation_json = (
            json.dumps(investigation_input, sort_keys=True, separators=(",", ":"), default=str)
            if investigation_input else None
        )
        if root_cause_fingerprint:
            async with self._security_lock:
                await self._db.execute("BEGIN IMMEDIATE")
                try:
                    cursor = await self._db.execute(
                        "SELECT id FROM security_candidates "
                        "WHERE repo = ? AND target_commit = ? "
                        "AND root_cause_fingerprint = ?",
                        (repo, target_commit, root_cause_fingerprint),
                    )
                    row = await cursor.fetchone()
                    if row is not None:
                        await self._db.commit()
                        return row[0]
                    await self._db.execute(
                        """INSERT INTO security_candidates
                           (id, scan_id, repo, target_commit, file_path, title, status,
                            root_cause_fingerprint, investigation_json, created_at, updated_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (candidate_id, scan_id, repo, target_commit, file_path, title,
                         CandidateStatus.DISCOVERED, root_cause_fingerprint,
                         investigation_json, now, now),
                    )
                    await self._db.commit()
                    return candidate_id
                except Exception:
                    await self._db.rollback()
                    raise
        await self._db.execute(
            """INSERT INTO security_candidates
               (id, scan_id, repo, target_commit, file_path, title, status,
                investigation_json, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (candidate_id, scan_id, repo, target_commit, file_path, title,
             CandidateStatus.DISCOVERED, investigation_json, now, now),
        )
        await self._db.commit()
        return candidate_id

    async def defer_security_candidate(self, candidate_id: str, *, reason_code: str) -> None:
        """Park an uninvestigated candidate without closing it."""
        if not reason_code:
            raise SecurityGateError("Deferral requires a reason code")
        cursor = await self._db.execute(
            "UPDATE security_candidates SET status = ?, defer_reason = ?, updated_at = ? "
            "WHERE id = ? AND status IN ('DISCOVERED', 'DEFERRED')",
            (CandidateStatus.DEFERRED, reason_code, datetime.now(UTC).isoformat(), candidate_id),
        )
        await self._db.commit()
        if cursor.rowcount != 1:
            raise SecurityGateError("Candidate is missing or cannot be deferred")

    async def mark_candidate_investigating(self, candidate_id: str) -> None:
        cursor = await self._db.execute(
            "UPDATE security_candidates SET status = ?, updated_at = ? "
            "WHERE id = ? AND status IN ('DISCOVERED', 'DEFERRED')",
            (CandidateStatus.INVESTIGATING, datetime.now(UTC).isoformat(), candidate_id),
        )
        await self._db.commit()
        if cursor.rowcount != 1:
            raise SecurityGateError("Candidate is missing or already closed")

    async def list_candidate_fingerprints(self, repo: str, target_commit: str) -> set[str]:
        """Every root-cause fingerprint already admitted for this repo/commit."""
        cursor = await self._db.execute(
            "SELECT root_cause_fingerprint FROM security_candidates "
            "WHERE repo = ? AND target_commit = ? AND root_cause_fingerprint IS NOT NULL",
            (repo, target_commit),
        )
        return {row[0] for row in await cursor.fetchall()}

    async def list_pending_security_candidates(
        self, repo: str, target_commit: str,
    ) -> list[dict]:
        """Durable, resumable queue of admitted-but-uninvestigated candidates."""
        cursor = await self._db.execute(
            """SELECT id, scan_id, file_path, title, status, root_cause_fingerprint,
                      defer_reason, investigation_json
               FROM security_candidates
               WHERE repo = ? AND target_commit = ?
                 AND status IN ('DISCOVERED', 'DEFERRED')
               ORDER BY created_at""",
            (repo, target_commit),
        )
        rows = await cursor.fetchall()
        keys = [column[0] for column in cursor.description]
        return [dict(zip(keys, row, strict=True)) for row in rows]

    async def add_security_evidence(
        self, *, candidate_id: str, kind: EvidenceKind,
        content_hash: str, target_commit: str, origin: str = "unknown",
    ) -> str:
        evidence_id = uuid.uuid4().hex
        async with self._security_lock:
            cursor = await self._db.execute(
                "SELECT target_commit FROM security_candidates WHERE id = ?", (candidate_id,)
            )
            candidate = await cursor.fetchone()
            if candidate is None or candidate[0] != target_commit:
                raise SecurityGateError("Evidence target does not match the candidate")
            await self._db.execute(
                """INSERT INTO security_evidence
                   (id, candidate_id, kind, content_hash, target_commit, origin, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (evidence_id, candidate_id, kind, content_hash,
                 target_commit, origin, datetime.now(UTC).isoformat()),
            )
            await self._db.commit()
        return evidence_id

    async def store_security_proof(
        self, *, candidate_id: str, scan_id: str, repo: str,
        target_commit: str, result,
    ) -> str:
        """Persist a retrievable redacted proof; a non-confirming run invalidates priors."""
        proof_id = uuid.uuid4().hex
        record_json = json.dumps(
            result.record, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        )
        record_hash = hashlib.sha256(record_json.encode("utf-8")).hexdigest()
        confirmed = result.vulnerability_confirmed
        async with self._security_lock:
            await self._db.execute("BEGIN IMMEDIATE")
            try:
                cursor = await self._db.execute(
                    "SELECT target_commit FROM security_candidates WHERE id = ?",
                    (candidate_id,),
                )
                row = await cursor.fetchone()
                if row is None or row[0] != target_commit:
                    raise SecurityGateError("Proof target does not match the candidate")
                if confirmed is not True:
                    await self._db.execute(
                        "UPDATE security_proofs SET valid = 0 WHERE candidate_id = ? AND valid = 1",
                        (candidate_id,),
                    )
                await self._db.execute(
                    """INSERT INTO security_proofs
                       (proof_id, candidate_id, scan_id, repo, target_commit, oracle_digest,
                        surface, risk_class, outcome, vulnerability_confirmed, patch_status,
                        after_endpoint, evidence_hash, record_json, record_hash, valid, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)""",
                    (proof_id, candidate_id, scan_id, repo, target_commit,
                     result.record.get("oracle_digest", ""),
                     result.record.get("surface", ""), result.record.get("risk_class", ""),
                     result.outcome.value,
                     None if confirmed is None else int(confirmed),
                     result.patch_status, result.after_endpoint, result.evidence_hash,
                     record_json, record_hash,
                     datetime.now(UTC).isoformat()),
                )
                await self._db.commit()
            except Exception:
                await self._db.rollback()
                raise
        return proof_id

    async def get_security_proof(self, proof_id: str) -> dict | None:
        cursor = await self._db.execute(
            "SELECT * FROM security_proofs WHERE proof_id = ?", (proof_id,)
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return dict(zip((column[0] for column in cursor.description), row, strict=True))

    async def list_security_proofs(self, candidate_id: str) -> list[dict]:
        cursor = await self._db.execute(
            "SELECT * FROM security_proofs WHERE candidate_id = ? ORDER BY created_at",
            (candidate_id,),
        )
        rows = await cursor.fetchall()
        keys = [column[0] for column in cursor.description]
        return [dict(zip(keys, row, strict=True)) for row in rows]

    async def close_security_candidate(
        self, candidate_id: str, *, status: CandidateStatus,
        reason_code: str, evidence_id: str | None = None,
    ) -> None:
        if not reason_code:
            raise SecurityGateError("Candidate closure requires a reason code")
        if status not in {
            CandidateStatus.CONFIRMED, CandidateStatus.RULED_OUT,
            CandidateStatus.OPEN_PROOF_GAP, CandidateStatus.NEEDS_MANUAL_REVIEW,
        }:
            raise SecurityGateError("Invalid terminal candidate status")
        async with self._security_lock:
            await self._db.execute("BEGIN IMMEDIATE")
            try:
                cursor = await self._db.execute(
                    "SELECT status, target_commit FROM security_candidates WHERE id = ?",
                    (candidate_id,),
                )
                candidate = await cursor.fetchone()
                if candidate is None or candidate[0] not in {
                    CandidateStatus.DISCOVERED, CandidateStatus.INVESTIGATING,
                    CandidateStatus.DEFERRED, CandidateStatus.NEEDS_MANUAL_REVIEW,
                }:
                    raise SecurityGateError("Candidate is missing or already closed")
                if status in {CandidateStatus.CONFIRMED, CandidateStatus.RULED_OUT}:
                    if not evidence_id:
                        raise SecurityGateError("Conclusive closure requires evidence")
                    cursor = await self._db.execute(
                        """SELECT kind FROM security_evidence
                           WHERE id = ? AND candidate_id = ? AND target_commit = ?""",
                        (evidence_id, candidate_id, candidate[1]),
                    )
                    evidence = await cursor.fetchone()
                    required_kinds = (
                        {EvidenceKind.POC_TRIGGERED, EvidenceKind.SEMANTIC_PROOF}
                        if status == CandidateStatus.CONFIRMED
                        else {EvidenceKind.COUNTEREVIDENCE}
                    )
                    if evidence is None or evidence[0] not in required_kinds:
                        raise SecurityGateError("Evidence does not support closure")
                await self._db.execute(
                    """UPDATE security_candidates
                       SET status = ?, reason_code = ?, closing_evidence_id = ?,
                           updated_at = ? WHERE id = ?""",
                    (status, reason_code, evidence_id, datetime.now(UTC).isoformat(),
                     candidate_id),
                )
                await self._db.commit()
            except Exception:
                await self._db.rollback()
                raise

    async def get_security_candidate(self, candidate_id: str) -> dict | None:
        cursor = await self._db.execute(
            "SELECT * FROM security_candidates WHERE id = ?", (candidate_id,)
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return dict(zip((column[0] for column in cursor.description), row, strict=True))

    async def list_security_candidates(self, *, limit: int = 50) -> list[dict]:
        if limit < 1 or limit > 500:
            raise ValueError("Candidate list limit must be 1..500")
        cursor = await self._db.execute(
            """SELECT id, scan_id, repo, target_commit, file_path, title,
                      status, reason_code
               FROM security_candidates ORDER BY created_at DESC LIMIT ?""",
            (limit,),
        )
        rows = await cursor.fetchall()
        keys = [column[0] for column in cursor.description]
        return [dict(zip(keys, row, strict=True)) for row in rows]

    async def store_scan_manifest(self, manifest: ScanManifest) -> None:
        payload = json.dumps(manifest.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        await self._db.execute(
            """INSERT INTO scan_manifests
               (scan_id, repo, target_commit, manifest_json, manifest_hash, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (manifest.scan_id, manifest.scope.repo, manifest.scope.target_commit,
             payload, manifest.digest, datetime.now(UTC).isoformat()),
        )
        await self._db.commit()

    async def get_scan_manifest(self, scan_id: str) -> ScanManifest | None:
        cursor = await self._db.execute(
            "SELECT repo, target_commit, manifest_json, manifest_hash FROM scan_manifests WHERE scan_id = ?",
            (scan_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        try:
            manifest = ScanManifest.model_validate_json(row[2])
        except Exception as exc:
            raise SecurityGateError("Stored scan manifest is invalid") from exc
        if (manifest.scan_id != scan_id or manifest.scope.repo != row[0]
                or manifest.scope.target_commit != row[1] or manifest.digest != row[3]):
            raise SecurityGateError("Stored scan manifest failed integrity validation")
        return manifest

    async def reserve_scoped_request(
        self, scan_id: str, *, url: str, role: str, impact: str, method: str = "GET",
    ) -> int:
        """Atomically spend one request budget unit before network I/O."""
        async with self._security_lock:
            await self._db.execute("BEGIN IMMEDIATE")
            try:
                cursor = await self._db.execute(
                    """SELECT manifest_json, manifest_hash, requests_used
                       FROM scan_manifests WHERE scan_id = ?""",
                    (scan_id,),
                )
                row = await cursor.fetchone()
                if row is None:
                    raise SecurityGateError("Live scan has no authorized manifest")
                try:
                    manifest = ScanManifest.model_validate_json(row[0])
                except Exception as exc:
                    raise SecurityGateError("Stored scan manifest is invalid") from exc
                if manifest.scan_id != scan_id or manifest.digest != row[1]:
                    raise SecurityGateError("Stored scan manifest failed integrity validation")
                manifest.require_request(url, role, impact, method)
                if row[2] >= manifest.scope.max_requests:
                    raise SecurityGateError("Program request budget exhausted")
                await self._db.execute(
                    "UPDATE scan_manifests SET requests_used = requests_used + 1 WHERE scan_id = ?",
                    (scan_id,),
                )
                await self._db.commit()
                return row[2] + 1
            except Exception:
                await self._db.rollback()
                raise

    async def store_threat_model(self, model: ThreatModel, *, expected_version: int = 0) -> None:
        payload = json.dumps(model.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        async with self._security_lock:
            await self._db.execute("BEGIN IMMEDIATE")
            try:
                manifest = await self.get_scan_manifest(model.scan_id)
                if manifest is None or manifest.scope.target_commit != model.target_commit:
                    raise SecurityGateError("Threat model does not match an authorized scan")
                cursor = await self._db.execute(
                    "SELECT version FROM scan_threat_models WHERE scan_id = ?", (model.scan_id,)
                )
                row = await cursor.fetchone()
                current = row[0] if row else 0
                if current != expected_version or model.version != current + 1:
                    raise SecurityGateError("Threat model version conflict")
                await self._db.execute(
                    """INSERT INTO scan_threat_models (scan_id, version, model_json, model_hash)
                       VALUES (?, ?, ?, ?)
                       ON CONFLICT(scan_id) DO UPDATE SET
                       version=excluded.version, model_json=excluded.model_json,
                       model_hash=excluded.model_hash""",
                    (model.scan_id, model.version, payload, model.digest),
                )
                await self._db.commit()
            except Exception:
                await self._db.rollback()
                raise

    async def get_threat_model(self, scan_id: str) -> ThreatModel | None:
        cursor = await self._db.execute(
            "SELECT version, model_json, model_hash FROM scan_threat_models WHERE scan_id = ?",
            (scan_id,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        try:
            model = ThreatModel.model_validate_json(row[1])
        except Exception as exc:
            raise SecurityGateError("Stored threat model is invalid") from exc
        if model.scan_id != scan_id or model.version != row[0] or model.digest != row[2]:
            raise SecurityGateError("Stored threat model failed integrity validation")
        return model

    async def initialize_coverage(self, manifest: ScanManifest) -> None:
        pairs = [(manifest.scan_id, surface, risk, datetime.now(UTC).isoformat())
                 for surface in manifest.scope.surfaces for risk in manifest.scope.risk_classes]
        if len(pairs) > 10000:
            raise SecurityGateError("Coverage matrix exceeds the supported limit")
        await self._db.executemany(
            """INSERT INTO scan_coverage (scan_id, surface, risk_class, updated_at)
               VALUES (?, ?, ?, ?)""",
            pairs,
        )
        await self._db.commit()

    async def record_coverage(
        self, scan_id: str, surface: str, risk_class: str, outcome: CoverageOutcome,
        *, evidence_hash: str | None = None, reason_code: str | None = None,
    ) -> None:
        if outcome == CoverageOutcome.NOT_TESTED:
            raise SecurityGateError("Use initialization for not-tested coverage")
        if outcome == CoverageOutcome.TESTED:
            if not evidence_hash or not re.fullmatch(r"[0-9a-f]{64}", evidence_hash):
                raise SecurityGateError("Tested coverage requires an evidence hash")
        elif not reason_code:
            raise SecurityGateError("Blocked or inconclusive coverage requires a reason")
        cursor = await self._db.execute(
            """UPDATE scan_coverage SET outcome = ?, evidence_hash = ?, reason_code = ?,
               updated_at = ? WHERE scan_id = ? AND surface = ? AND risk_class = ?""",
            (outcome, evidence_hash, reason_code, datetime.now(UTC).isoformat(),
             scan_id, surface, risk_class),
        )
        await self._db.commit()
        if cursor.rowcount != 1:
            raise SecurityGateError("Coverage entry missing for this surface and risk class")

    async def get_coverage_summary(self, scan_id: str) -> CoverageSummary:
        cursor = await self._db.execute(
            "SELECT outcome, COUNT(*) FROM scan_coverage WHERE scan_id = ? GROUP BY outcome",
            (scan_id,),
        )
        counts = dict(await cursor.fetchall())
        return CoverageSummary(
            scan_id=scan_id, total=sum(counts.values()),
            tested=counts.get(CoverageOutcome.TESTED, 0),
            not_tested=counts.get(CoverageOutcome.NOT_TESTED, 0),
            blocked=counts.get(CoverageOutcome.BLOCKED, 0),
            inconclusive=counts.get(CoverageOutcome.INCONCLUSIVE, 0),
        )

    async def security_candidate_is_confirmed(self, candidate_id: str, repo: str) -> bool:
        cursor = await self._db.execute(
            """SELECT 1 FROM security_candidates c JOIN security_evidence e
               ON e.id = c.closing_evidence_id AND e.candidate_id = c.id
               WHERE c.id = ? AND c.repo = ? AND c.status = 'CONFIRMED'
                 AND e.kind IN ('POC_TRIGGERED', 'SEMANTIC_PROOF')
                 AND e.target_commit = c.target_commit
                 AND c.target_commit != 'unknown'""",
            (candidate_id, repo),
        )
        return await cursor.fetchone() is not None

    @staticmethod
    def _canonical_record(record_json: str, record_hash: str) -> dict | None:
        """Return the record only when its canonical hash matches the stored hash."""
        try:
            canonical = json.dumps(
                json.loads(record_json), sort_keys=True,
                separators=(",", ":"), ensure_ascii=False,
            )
        except (TypeError, ValueError):
            return None
        if hashlib.sha256(canonical.encode("utf-8")).hexdigest() != record_hash:
            return None
        return json.loads(canonical)

    async def security_candidate_has_semantic_proof(self, candidate_id: str) -> bool:
        """True only for a self-consistent proof bound to this candidate's evidence."""
        cursor = await self._db.execute(
            "SELECT scan_id, repo, target_commit, status, closing_evidence_id "
            "FROM security_candidates WHERE id = ?",
            (candidate_id,),
        )
        candidate = await cursor.fetchone()
        if candidate is None or candidate[3] != CandidateStatus.CONFIRMED:
            return False
        scan_id, repo, commit, _status, closing_id = candidate
        if not closing_id:
            return False
        cursor = await self._db.execute(
            "SELECT kind, content_hash, candidate_id, target_commit "
            "FROM security_evidence WHERE id = ?",
            (closing_id,),
        )
        evidence = await cursor.fetchone()
        if (evidence is None or evidence[0] != EvidenceKind.SEMANTIC_PROOF
                or evidence[2] != candidate_id or evidence[3] != commit):
            return False
        evidence_hash = evidence[1]
        manifest = await self.get_scan_manifest(scan_id)
        if (manifest is None or manifest.scope.repo != repo
                or manifest.scope.target_commit != commit):
            return False
        threat = await self.get_threat_model(scan_id)
        if threat is None or threat.target_commit != commit:
            return False
        cursor = await self._db.execute(
            """SELECT candidate_id, scan_id, repo, target_commit, oracle_digest, surface,
                      risk_class, evidence_hash, record_json, record_hash
               FROM security_proofs
               WHERE candidate_id = ? AND valid = 1 AND vulnerability_confirmed = 1""",
            (candidate_id,),
        )
        for row in await cursor.fetchall():
            (p_candidate, p_scan, p_repo, p_commit, p_oracle, p_surface,
             p_risk, p_evidence_hash, p_record_json, p_record_hash) = row
            if (p_candidate != candidate_id or p_scan != scan_id or p_repo != repo
                    or p_commit != commit or p_evidence_hash != evidence_hash):
                continue
            if p_surface not in manifest.scope.surfaces:
                continue
            if p_risk not in manifest.scope.risk_classes:
                continue
            record = self._canonical_record(p_record_json, p_record_hash)
            if record is None:
                continue
            if (record.get("oracle_digest") != p_oracle
                    or record.get("surface") != p_surface
                    or record.get("risk_class") != p_risk
                    or record.get("target_commit") != commit):
                continue
            return True
        return False

    async def record_scan_event(
        self, *, scan_id: str, repo: str, pipeline: str, stage: str,
        outcome: str, candidate_id: str | None = None, reason_code: str | None = None,
        count: int = 1, duration_ms: int | None = None, model: str | None = None,
        input_tokens: int | None = None, output_tokens: int | None = None,
        cost_usd: float | None = None,
    ) -> None:
        """Store metadata-only M0 gate telemetry; never store prompts or PoC contents."""
        await self._db.execute(
            """INSERT INTO scan_events
               (scan_id, candidate_id, repo, pipeline, stage, outcome, reason_code,
                count, duration_ms, model, input_tokens, output_tokens, cost_usd, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (scan_id, candidate_id, repo, pipeline, stage, outcome, reason_code,
             count, duration_ms, model, input_tokens, output_tokens, cost_usd,
             datetime.now(UTC).isoformat()),
        )
        await self._db.commit()

    async def get_scan_events(self, scan_id: str) -> list[dict]:
        cursor = await self._db.execute(
            "SELECT * FROM scan_events WHERE scan_id = ? ORDER BY id", (scan_id,)
        )
        rows = await cursor.fetchall()
        columns = [column[0] for column in cursor.description]
        return [dict(zip(columns, row, strict=True)) for row in rows]

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
                """INSERT OR REPLACE INTO knowledge_base (repo_name, entry_type, content, created_at)
                   VALUES (?, 'qa_lesson', ?, ?)""",
                (repo_name, content, datetime.now(UTC).isoformat()),
            )
            await self._db.commit()
        except Exception as exc:
            logger.debug("Could not record QA lesson for %s: %s", repo_name, exc)

    async def add_filter_lesson(self, repo: str, layer: int, snippet_or_fix: str, critique: str) -> None:
        """Record a rejection lesson from Layer 1 or Layer 2 filters."""
        if self._db is None:
            return

        # Replace tricky quotes to avoid JSON issues, truncation.
        content = f"[Layer {layer}] Rejected due to: {critique}\nSnippet/Fix context:\n{snippet_or_fix[:500]}..."
        try:
            await self._db.execute(
                """INSERT OR REPLACE INTO knowledge_base (repo_name, entry_type, content, created_at)
                   VALUES (?, 'FILTER_REJECTION_LESSON', ?, ?)""",
                (repo, content, datetime.now(UTC).isoformat()),
            )
            await self._db.commit()
        except Exception as exc:
            logger.debug("Could not record filter lesson for %s: %s", repo, exc)

    async def get_knowledge(self, repo_name: str, entry_type: str) -> str:
        """Retrieve all knowledge base entries for a repo and type, joined as a string."""
        if self._db is None:
            return ""

        if "://" in repo_name:
            repo_name = repo_name.split("/")[-2] + "/" + repo_name.split("/")[-1]
        
        try:
            cursor = await self._db.execute(
                """SELECT content FROM knowledge_base
                   WHERE repo_name = ? AND entry_type = ?
                   ORDER BY created_at ASC""",
                (repo_name, entry_type),
            )
            rows = await cursor.fetchall()
            return "\n\n".join([r[0] for r in rows])
        except Exception as exc:
            logger.debug("Could not fetch knowledge for %s: %s", repo_name, exc)
            return ""

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
                    "Garbage Collection: purged %d stale knowledge base entries (older than %d days)",
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

        DEBT-04 FIX: Rewrote from date(timestamp, 'unixepoch') string comparison
        to a numeric Unix timestamp range. SQLite cannot use the (provider, timestamp)
        index when a function is applied to the indexed column, causing a full
        table scan on every Bloodhound call. The range comparison is index-seekable.
        """
        if self._db is None:
            return 0

        import time as _time
        try:
            # Compute UTC midnight as Unix timestamp for today
            import datetime as _dt
            now_utc = _dt.datetime.now(_dt.timezone.utc)
            midnight_utc = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
            day_start_ts = midnight_utc.timestamp()

            cursor = await self._db.execute(
                "SELECT COUNT(*) FROM api_usage_log"
                " WHERE provider = 'openrouter' AND timestamp >= ?",
                (day_start_ts,),
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
        except (json.JSONDecodeError, OSError) as exc:
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
               WHERE repo_url = (SELECT repo_url FROM target_repos WHERE LOWER(language) NOT IN ({placeholders}) ORDER BY COALESCE(scanned_at, 0) ASC, rowid ASC LIMIT 1) 
               RETURNING *"""
            params = (now_ts, *[lang.lower() for lang in excluded_languages])
        else:
            query = """UPDATE target_repos 
               SET scanned_at = ? 
               WHERE repo_url = (SELECT repo_url FROM target_repos ORDER BY COALESCE(scanned_at, 0) ASC, rowid ASC LIMIT 1) 
               RETURNING *"""
            params = (now_ts,)

        cursor = await self._db.execute(query, params)
        row = await cursor.fetchone()
        await self._db.commit()
        
        if row is None:
            return None

        cols = [d[0] for d in cursor.description]
        result = dict(zip(cols, row, strict=False))
        logger.info(f"[TARGET ACQUIRED] Repo: {result.get('repo_url')} | Language: {result.get('language')} | Bounty: {result.get('bounty_amount')} | Diamond: {result.get('diamond_target')}")
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

    # ── Safe Quota Tracking ──────────────────────────

    async def check_and_record_llm_quota(self, provider: str = "openrouter") -> None:
        """Sliding-window quota checker and recorder for LLM providers.
        
        Hardcoded safety limits: 1000 requests per 5 hours, 10000 per 7 days.
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
            "SELECT repo, style_summary, contributing_md, pr_template FROM repo_style_guides WHERE repo = ?",
            (repo,),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        cols = [d[0] for d in cursor.description]
        return dict(zip(cols, row, strict=False))

