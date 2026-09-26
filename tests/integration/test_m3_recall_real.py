"""M3 slice 1: distinct same-file candidates survive investigation.

The two gates that dropped them were the per-repo ``[:2]`` cap and the
file-only dedupe against past PRs. Both are removed; investigation is now
bounded only by ``pipeline.max_candidates_investigated`` while publication keeps
its own ``max_prs`` cap. Real SQLite; GitHub/LLM/sandbox are replaced.
"""

from contextlib import ExitStack
from unittest.mock import AsyncMock

import pytest

from farm_agent.core.config import FarmAgentConfig
from farm_agent.core.models import (
    AnalysisResult,
    ContributionType,
    Finding,
    ImpactLevel,
    Severity,
)
from farm_agent.orchestrator.memory import Memory
from farm_agent.orchestrator.pipeline import FarmAgentPipeline
from tests.integration.test_m2_handoff_real import _common_patches, _repo, _wire

SAME_FILE = "src/app.py"
FINDINGS = [
    Finding(
        type=ContributionType.SECURITY_FIX, severity=Severity.HIGH,
        title="IDOR in get_order", description="cross tenant read", file_path=SAME_FILE,
        line_start=10, suggestion="check ownership", impact_level=ImpactLevel.HIGH,
    ),
    Finding(
        type=ContributionType.SECURITY_FIX, severity=Severity.HIGH,
        title="SQL injection in order search", description="unparameterized query",
        file_path=SAME_FILE, line_start=40, suggestion="parameterize",
        impact_level=ImpactLevel.HIGH,
    ),
    Finding(
        type=ContributionType.SECURITY_FIX, severity=Severity.HIGH,
        title="Path traversal in file download", description="unescaped path",
        file_path=SAME_FILE, line_start=70, suggestion="sanitize", impact_level=ImpactLevel.HIGH,
    ),
]


def _config(max_candidates=25):
    config = FarmAgentConfig()
    config.pipeline.max_candidates_investigated = max_candidates
    return config


async def _run(tmp_path, name, max_candidates, pull_requests):
    memory = Memory(tmp_path / f"{name}.db")
    await memory.init()
    pipeline = FarmAgentPipeline(_config(max_candidates))
    _wire(pipeline, memory, tmp_path)
    pipeline._sandbox = None  # no PoC generation; candidates close as proof gaps
    pipeline._analyzer.analyze = AsyncMock(
        return_value=AnalysisResult(repo=_repo(), findings=list(FINDINGS))
    )
    pipeline._validate_findings = AsyncMock(side_effect=lambda findings, _files: list(findings))
    pipeline._github.list_pull_requests = AsyncMock(return_value=pull_requests)
    with ExitStack() as stack:
        for context in _common_patches():
            stack.enter_context(context)
        await pipeline._process_repo(_repo(), dry_run=True, max_prs=1)
    return memory


@pytest.mark.asyncio
async def test_same_file_distinct_findings_survive_investigation(tmp_path):
    memory = await _run(
        tmp_path, "recall", 25,
        [{"title": "Refactor logging", "body": "touches `src/app.py`",
          "head": {"label": "farm_agent/logging"}}],
    )
    try:
        cursor = await memory._db.execute(
            "SELECT title, file_path FROM security_candidates ORDER BY title"
        )
        rows = await cursor.fetchall()
        assert len(rows) == 3, "a past PR on the same file must not drop a distinct finding"
        assert {row[1] for row in rows} == {SAME_FILE}
        assert {row[0] for row in rows} == {finding.title for finding in FINDINGS}
        events = await memory._db.execute(
            "SELECT outcome, count FROM scan_events WHERE repo = 'owner/repo' AND stage = 'dedupe'"
        )
        assert ("survived", 3) in await events.fetchall()
    finally:
        await memory.close()


@pytest.mark.asyncio
async def test_all_findings_admitted_with_active_limit_and_deferral(tmp_path):
    memory = await _run(tmp_path, "limit", 2, [])
    try:
        cursor = await memory._db.execute(
            "SELECT status, COUNT(*) FROM security_candidates GROUP BY status"
        )
        counts = dict(await cursor.fetchall())
        assert sum(counts.values()) == 3, "every distinct finding must be admitted durably"
        assert counts.get("DEFERRED") == 1, "surplus work must be visible and resumable"
        events = await memory._db.execute(
            "SELECT outcome, count, reason_code FROM scan_events "
            "WHERE repo = 'owner/repo' AND stage = 'candidate_limit'"
        )
        assert ("admitted", 3, "INVESTIGATION_LIMIT") in await events.fetchall()
    finally:
        await memory.close()
