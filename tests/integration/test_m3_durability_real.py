"""M3 durability: no silent erasure of filtered findings, and exact resume input.

Real SQLite. Pipeline tests replace GitHub/LLM/sandbox; the filter recording,
persisted investigation input and resume behaviour are real.
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
from farm_agent.security.identity import root_cause_identity
from tests.integration.test_m2_handoff_real import _common_patches, _repo, _wire

COMMIT = "a" * 40


def _config(max_candidates=25):
    config = FarmAgentConfig()
    config.pipeline.max_candidates_investigated = max_candidates
    return config


def _finding(title, file_path, line, *, sensor=None):
    metadata = {"sensor": sensor} if sensor else {}
    return Finding(
        type=ContributionType.SECURITY_FIX, severity=Severity.HIGH, title=title,
        description="cross tenant read", file_path=file_path, line_start=line,
        suggestion="fix", impact_level=ImpactLevel.HIGH, metadata=metadata,
    )


async def _run(tmp_path, name, findings, *, limit=25, validate=None,
               appraisal=None, pull_requests=None):
    memory = Memory(tmp_path / f"{name}.db")
    await memory.init()
    pipeline = FarmAgentPipeline(_config(limit))
    _wire(pipeline, memory, tmp_path)
    pipeline._sandbox = None
    pipeline._analyzer.analyze = AsyncMock(
        return_value=AnalysisResult(repo=_repo(), findings=list(findings))
    )
    pipeline._validate_findings = AsyncMock(
        side_effect=validate or (lambda items, _files: list(items))
    )
    pipeline._layer1_expert_appraisal = AsyncMock(
        side_effect=appraisal or (lambda _finding, _content: (True, "ok"))
    )
    pipeline._github.list_pull_requests = AsyncMock(return_value=pull_requests or [])
    with ExitStack() as stack:
        for context in _common_patches():
            stack.enter_context(context)
        await pipeline._process_repo(_repo(), dry_run=True, max_prs=1)
    return memory


async def _reasons(memory):
    cursor = await memory._db.execute("SELECT title, reason_code FROM security_candidates")
    return dict(await cursor.fetchall())


@pytest.mark.asyncio
async def test_filtered_security_findings_are_recorded_not_erased(tmp_path):
    good = _finding("IDOR in orders", "src/app.py", 10)
    non_code = _finding("Committed secret key", "README.md", 1)
    rejected = _finding("Widened exception handler", "src/app.py", 50)
    memory = await _run(
        tmp_path, "nofilter", [good, non_code, rejected],
        appraisal=lambda finding, _content: (
            "exception" not in finding.title.lower(), "model says no",
        ),
    )
    try:
        cursor = await memory._db.execute("SELECT COUNT(*) FROM security_candidates")
        assert (await cursor.fetchone())[0] == 3, "no security finding may be erased"
        reasons = await _reasons(memory)
        assert reasons["Committed secret key"] == "FILTERED_NON_CODE_TARGET"
        assert reasons["Widened exception handler"] == "APPRAISAL_REJECTED"
        assert reasons["IDOR in orders"] == "SANDBOX_UNAVAILABLE"
    finally:
        await memory.close()


@pytest.mark.asyncio
async def test_validation_rejection_and_published_title_duplicate_are_recorded(tmp_path):
    finding = _finding("IDOR in orders", "src/app.py", 10)
    memory = await _run(tmp_path, "validate", [finding], validate=lambda _items, _files: [])
    try:
        assert (await _reasons(memory))["IDOR in orders"] == "VALIDATION_REJECTED"
    finally:
        await memory.close()

    duplicate = _finding("IDOR in orders", "src/app.py", 10)
    memory = await _run(
        tmp_path, "dedupe", [duplicate],
        pull_requests=[{"title": duplicate.title, "body": "", "head": {"label": ""}}],
    )
    try:
        assert (await _reasons(memory))["IDOR in orders"] == "DUPLICATE_PUBLISHED_TITLE"
    finally:
        await memory.close()


@pytest.mark.asyncio
async def test_deferred_investigation_input_survives_restart(tmp_path):
    first = _finding("IDOR in orders", "src/app.py", 10)
    second = _finding("SQL injection in search", "src/app.py", 40)
    memory = await _run(tmp_path, "durable", [first, second], limit=1)
    try:
        cursor = await memory._db.execute(
            "SELECT title, investigation_json FROM security_candidates WHERE status = 'DEFERRED'"
        )
        title, stored = await cursor.fetchone()
        assert stored and "line_start" in stored and "severity" in stored
    finally:
        await memory.close()

    reopened = Memory(tmp_path / "durable.db")
    await reopened.init()
    pipeline = FarmAgentPipeline(_config(1))
    _wire(pipeline, reopened, tmp_path)
    pipeline._sandbox = None
    pipeline._analyzer.analyze = AsyncMock(return_value=AnalysisResult(
        repo=_repo(), findings=[_finding("Completely different", "src/zzz.py", 7)],
    ))
    pipeline._validate_findings = AsyncMock(side_effect=lambda _items, _files: [])
    pipeline._github.list_pull_requests = AsyncMock(return_value=[])
    try:
        with ExitStack() as stack:
            for context in _common_patches():
                stack.enter_context(context)
            await pipeline._process_repo(_repo(), dry_run=True, max_prs=1)
        cursor = await reopened._db.execute(
            "SELECT status, investigation_json FROM security_candidates WHERE title = ?",
            (title,),
        )
        status, after = await cursor.fetchone()
        assert status == "OPEN_PROOF_GAP", "the deferred candidate must resume"
        assert after == stored, "resume must reuse the exact stored input"
    finally:
        await reopened.close()


@pytest.mark.asyncio
async def test_resume_does_not_depend_on_analyzer_and_flags_missing_input(tmp_path):
    memory = Memory(tmp_path / "resume.db")
    await memory.init()
    pipeline = FarmAgentPipeline(_config(5))
    pipeline._memory = memory
    try:
        finding = _finding("IDOR in orders", "src/app.py", 10)
        candidate_id = await memory.create_security_candidate(
            scan_id="s", repo="owner/repo", target_commit=COMMIT,
            file_path=finding.file_path, title=finding.title,
            root_cause_fingerprint=root_cause_identity(finding, target_commit=COMMIT),
            investigation_input=FarmAgentPipeline._investigation_input(finding),
        )
        await memory.defer_security_candidate(candidate_id, reason_code="INVESTIGATION_DEFERRED")
        legacy_id = await memory.create_security_candidate(
            scan_id="s", repo="owner/repo", target_commit=COMMIT,
            file_path="src/legacy.py", title="legacy candidate",
            root_cause_fingerprint="f" * 64,
        )
        # No analyzer result at all: the durable queue still resumes the exact input.
        queue = await pipeline._admission_queue(_repo(), COMMIT, [], "s")
        assert [entry["finding"].title for entry in queue] == ["IDOR in orders"]
        resumed = queue[0]["finding"]
        assert resumed.type == finding.type
        assert resumed.severity == finding.severity
        assert resumed.description == finding.description
        assert resumed.line_start == finding.line_start
        assert resumed.metadata == finding.metadata
        cursor = await memory._db.execute(
            "SELECT status, defer_reason FROM security_candidates WHERE id = ?", (legacy_id,)
        )
        assert await cursor.fetchone() == ("DEFERRED", "INVESTIGATION_INPUT_MISSING")
    finally:
        await memory.close()
