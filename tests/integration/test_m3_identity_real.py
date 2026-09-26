"""M3 slices 1-2: durable admission/resume and root-cause identity.

Real SQLite throughout. Pipeline tests replace GitHub/LLM/sandbox; the identity,
uniqueness, evidence-merge and resume behaviour is real.
"""

import asyncio
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
from farm_agent.security.state import CandidateStatus, EvidenceKind, SecurityGateError
from tests.integration.test_m2_handoff_real import _common_patches, _repo, _wire

COMMIT = "a" * 40
FILE = "src/app.py"
MANY = [
    Finding(
        type=ContributionType.SECURITY_FIX, severity=Severity.HIGH,
        title=f"IDOR in handler {index}", description="cross tenant read",
        file_path=FILE, line_start=10 + index, suggestion="check ownership",
        impact_level=ImpactLevel.HIGH,
    )
    for index in range(30)
]


def _config(max_candidates=25):
    config = FarmAgentConfig()
    config.pipeline.max_candidates_investigated = max_candidates
    return config


async def _run_pipeline(memory, tmp_path, findings, limit):
    pipeline = FarmAgentPipeline(_config(limit))
    _wire(pipeline, memory, tmp_path)
    pipeline._sandbox = None
    pipeline._analyzer.analyze = AsyncMock(
        return_value=AnalysisResult(repo=_repo(), findings=list(findings))
    )
    pipeline._validate_findings = AsyncMock(side_effect=lambda items, _files: list(items))
    pipeline._github.list_pull_requests = AsyncMock(return_value=[])
    with ExitStack() as stack:
        for context in _common_patches():
            stack.enter_context(context)
        await pipeline._process_repo(_repo(), dry_run=True, max_prs=1)


async def _status_counts(memory):
    cursor = await memory._db.execute(
        "SELECT status, COUNT(*) FROM security_candidates GROUP BY status"
    )
    return dict(await cursor.fetchall())


@pytest.mark.asyncio
async def test_all_findings_admitted_and_resumed_on_restart(tmp_path):
    db_path = tmp_path / "admission.db"
    for limit, expect_deferred in ((5, 25), (30, 0)):
        memory = Memory(db_path)
        await memory.init()
        try:
            await _run_pipeline(memory, tmp_path, MANY, limit)
            counts = await _status_counts(memory)
        finally:
            await memory.close()
        assert sum(counts.values()) == 30, "no distinct finding may be dropped"
        assert counts.get("DEFERRED", 0) == expect_deferred

    reopened = Memory(db_path)
    await reopened.init()
    try:
        cursor = await reopened._db.execute(
            "SELECT COUNT(*), COUNT(DISTINCT root_cause_fingerprint) FROM security_candidates"
        )
        total, distinct = await cursor.fetchone()
        assert total == 30 and distinct == 30, "restart must not duplicate candidates"
    finally:
        await reopened.close()


@pytest.mark.asyncio
async def test_equal_titles_and_severity_stay_distinct(tmp_path):
    memory = Memory(tmp_path / "distinct.db")
    await memory.init()
    try:
        same = dict(
            type=ContributionType.SECURITY_FIX, severity=Severity.HIGH,
            title="Missing authorization check", description="fixture",
            file_path=FILE, impact_level=ImpactLevel.HIGH,
        )
        first = Finding(**same, line_start=11)
        second = Finding(**same, line_start=88)
        id_a = await memory.create_security_candidate(
            scan_id="s", repo="owner/repo", target_commit=COMMIT, file_path=FILE,
            title=first.title,
            root_cause_fingerprint=root_cause_identity(first, target_commit=COMMIT),
        )
        id_b = await memory.create_security_candidate(
            scan_id="s", repo="owner/repo", target_commit=COMMIT, file_path=FILE,
            title=second.title,
            root_cause_fingerprint=root_cause_identity(second, target_commit=COMMIT),
        )
        assert id_a != id_b
        cursor = await memory._db.execute("SELECT COUNT(*) FROM security_candidates")
        assert (await cursor.fetchone())[0] == 2
    finally:
        await memory.close()


@pytest.mark.asyncio
async def test_two_sensors_share_one_candidate_with_both_evidence(tmp_path):
    memory = Memory(tmp_path / "sensors.db")
    await memory.init()
    try:
        finding = MANY[0]
        fingerprint = root_cause_identity(finding, target_commit=COMMIT)
        first = await memory.create_security_candidate(
            scan_id="s", repo="owner/repo", target_commit=COMMIT, file_path=FILE,
            title=finding.title, root_cause_fingerprint=fingerprint,
        )
        second = await memory.create_security_candidate(
            scan_id="s", repo="owner/repo", target_commit=COMMIT, file_path=FILE,
            title="Same root cause, different sensor title",
            root_cause_fingerprint=fingerprint,
        )
        assert first == second
        await memory.add_security_evidence(
            candidate_id=first, kind=EvidenceKind.POC_TRIGGERED, content_hash="a" * 64,
            target_commit=COMMIT, origin="semgrep",
        )
        await memory.add_security_evidence(
            candidate_id=first, kind=EvidenceKind.SEMANTIC_PROOF, content_hash="b" * 64,
            target_commit=COMMIT, origin="llm-analyzer",
        )
        cursor = await memory._db.execute("SELECT COUNT(*) FROM security_candidates")
        assert (await cursor.fetchone())[0] == 1
        cursor = await memory._db.execute(
            "SELECT origin FROM security_evidence WHERE candidate_id = ? ORDER BY origin",
            (first,),
        )
        assert [row[0] for row in await cursor.fetchall()] == ["llm-analyzer", "semgrep"]
    finally:
        await memory.close()


@pytest.mark.asyncio
async def test_concurrent_workers_do_not_duplicate_candidates(tmp_path):
    db_path = tmp_path / "workers.db"
    worker_a = Memory(db_path)
    worker_b = Memory(db_path)
    await worker_a.init()
    await worker_b.init()
    try:
        finding = MANY[1]
        fingerprint = root_cause_identity(finding, target_commit=COMMIT)
        arguments = dict(
            scan_id="s", repo="owner/repo", target_commit=COMMIT, file_path=FILE,
            title=finding.title, root_cause_fingerprint=fingerprint,
        )
        ids = await asyncio.gather(
            worker_a.create_security_candidate(**arguments),
            worker_b.create_security_candidate(**arguments),
        )
        assert len(set(ids)) == 1
        cursor = await worker_a._db.execute("SELECT COUNT(*) FROM security_candidates")
        assert (await cursor.fetchone())[0] == 1
    finally:
        await worker_a.close()
        await worker_b.close()


@pytest.mark.asyncio
async def test_candidate_cannot_borrow_another_candidates_proof(tmp_path):
    memory = Memory(tmp_path / "borrow.db")
    await memory.init()
    try:
        ids = []
        for finding in MANY[:2]:
            ids.append(await memory.create_security_candidate(
                scan_id="s", repo="owner/repo", target_commit=COMMIT, file_path=FILE,
                title=finding.title,
                root_cause_fingerprint=root_cause_identity(finding, target_commit=COMMIT),
            ))
        evidence = await memory.add_security_evidence(
            candidate_id=ids[0], kind=EvidenceKind.SEMANTIC_PROOF, content_hash="c" * 64,
            target_commit=COMMIT, origin="semgrep",
        )
        await memory.close_security_candidate(
            ids[0], status=CandidateStatus.CONFIRMED,
            reason_code="SEMANTIC_IMPACT_PROVEN", evidence_id=evidence,
        )
        with pytest.raises(SecurityGateError):
            await memory.close_security_candidate(
                ids[1], status=CandidateStatus.CONFIRMED,
                reason_code="BORROWED", evidence_id=evidence,
            )
        assert (await memory.get_security_candidate(ids[1]))["status"] == "DISCOVERED"
        assert not await memory.security_candidate_has_semantic_proof(ids[1])
    finally:
        await memory.close()
