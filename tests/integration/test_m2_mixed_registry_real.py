"""A live-forbidden program blocks live proof for a real candidate at a real SHA.

Real collaborators: a local Git repository and commit, the pipeline's own
``_clone_and_patch_repo`` and ``_repo_head_sha``, SQLite persistence, and the
loopback request counter.

Replaced collaborators (none proves the property under test):
- GitHub client, LLM analyzer/generator: no network, no paid model.
- sandbox: left ``None`` so no PoC/Docker runs.
- repo guidelines, dependency mapper, ``_read_all_repo_files_sync``,
  ``_validate_findings`` and ``_layer1_expert_appraisal``: not security gates.
- ``tempfile.gettempdir``: redirected to the test scratch so the real clone does
  not collide with a shared OS temp path; the clone and HEAD lookup stay real.
"""

import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from farm_agent.core.config import FarmAgentConfig
from farm_agent.core.models import ContributionType, Finding, Repository, Severity
from farm_agent.orchestrator.memory import Memory
from farm_agent.orchestrator.pipeline import FarmAgentPipeline
from farm_agent.security.closure import require_confirmed_security_finding
from farm_agent.security.scope import ProgramScope
from farm_agent.security.state import CandidateStatus, SecurityGateError


def _git_repo(path: Path) -> str:
    path.mkdir(parents=True, exist_ok=True)

    def run(*args):
        return subprocess.run(
            ["git", *args], cwd=path, check=True, capture_output=True, text=True,
        ).stdout.strip()

    run("init", "-q")
    run("config", "user.email", "fixture@example.invalid")
    run("config", "user.name", "fixture")
    (path / "app.py").write_text("print('fixture')\n", encoding="utf-8")
    run("add", "app.py")
    run("commit", "-q", "-m", "fixture")
    return run("rev-parse", "HEAD")


def _hit_counter():
    class Probe(BaseHTTPRequestHandler):
        hits = 0

        def do_GET(self):
            Probe.hits += 1
            self.send_response(200)
            self.end_headers()

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Probe)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, f"http://127.0.0.1:{server.server_port}", Probe


def _finding() -> Finding:
    return Finding(
        type=ContributionType.SECURITY_FIX, severity=Severity.HIGH,
        title="IDOR", description="cross tenant read", file_path="src/app.py",
    )


@pytest.mark.asyncio
async def test_live_forbidden_program_blocks_live_proof_at_real_sha(tmp_path):
    repo_dir = tmp_path / "target"
    pinned_sha = _git_repo(repo_dir)
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    probe_server, probe_thread, probe_origin, probe = _hit_counter()
    memory = Memory(tmp_path / "memory.db")
    await memory.init()
    try:
        repo = Repository(
            owner="owner", name="repo", full_name="owner/repo", clone_url=str(repo_dir),
        )
        program = ProgramScope(
            program_id="no-live", repo="owner/repo", target_commit=pinned_sha,
            allowed_origins=[probe_origin], allow_live_testing=False,
            policy_reference="fixture forbids live testing",
        )
        config = FarmAgentConfig()
        config.bounty.live_testing_enabled = True
        config.bounty.program_scopes = [program]
        finding = _finding()
        pipeline = FarmAgentPipeline(config)
        pipeline._memory = memory
        pipeline._github = MagicMock()
        pipeline._github.check_interaction_limits = AsyncMock(return_value=False)
        pipeline._github.fetch_recent_maintainer_comments = AsyncMock(return_value=[])
        pipeline._github.get_file_tree = AsyncMock(return_value=[])
        pipeline._github.get_file_content = AsyncMock(return_value="source")
        pipeline._analyzer = MagicMock()
        pipeline._llm = MagicMock()
        pipeline._sandbox = None
        pipeline._check_ai_policy = AsyncMock(return_value=False)
        pipeline._validate_findings = AsyncMock(return_value=[finding])
        pipeline._layer1_expert_appraisal = AsyncMock(return_value=(True, "valid"))
        guidelines = MagicMock(subsystem_docs={}, has_guidelines=False)
        guidelines.discover_subsystem_docs = AsyncMock(return_value={})
        with (
            patch("farm_agent.orchestrator.pipeline.fetch_repo_guidelines",
                  new=AsyncMock(return_value=guidelines)),
            patch("farm_agent.orchestrator.pipeline._read_all_repo_files_sync",
                  return_value={}),
            patch("farm_agent.analysis.mapper.RepoMapper"),
            patch("farm_agent.orchestrator.pipeline.tempfile.gettempdir",
                  return_value=str(scratch)),
        ):
            result = await pipeline._process_repo(
                repo, dry_run=True, max_prs=1,
                candidate_findings_override=[finding],
                expected_target_commit=pinned_sha,
            )
    finally:
        await memory.close()
        probe_server.shutdown()
        probe_server.server_close()
        probe_thread.join(timeout=3)

    assert probe.hits == 0, "a live-forbidden program must not send a live request"
    assert result.prs_created == 0
    assert result.findings_total == 1
    assert any(str(scratch) in path for path in pipeline._clone_cache.values()), (
        "the real clone must have run in the isolated scratch"
    )
    pipeline._github.get_file_content.assert_awaited_with(
        "owner", "repo", "src/app.py", ref=pinned_sha,
    )

    reopened = Memory(tmp_path / "memory.db")
    await reopened.init()
    try:
        cursor = await reopened._db.execute("SELECT scan_id FROM scan_manifests")
        row = await cursor.fetchone()
        assert row is not None, "the scan is still authorized offline"
        scan_id = row[0]
        manifest = await reopened.get_scan_manifest(scan_id)
        assert manifest.mode == "offline"
        assert manifest.scope.target_commit == pinned_sha

        cursor = await reopened._db.execute(
            "SELECT requests_used FROM scan_manifests WHERE scan_id = ?", (scan_id,),
        )
        assert (await cursor.fetchone())[0] == 0, "no live request budget was spent"

        events = await reopened.get_scan_events(scan_id)
        assert any(
            event["reason_code"] == "LIVE_TESTING_NOT_AUTHORIZED"
            and event["outcome"] == "blocked" for event in events
        )

        cursor = await reopened._db.execute(
            "SELECT id, status, reason_code, target_commit FROM security_candidates"
        )
        candidates = await cursor.fetchall()
        assert len(candidates) == 1, "the concrete security candidate must exist"
        candidate_id, status, reason_code, candidate_commit = candidates[0]
        assert candidate_commit == pinned_sha
        assert status == CandidateStatus.OPEN_PROOF_GAP
        assert reason_code != "TARGET_COMMIT_CHANGED"  # real HEAD matched the pin
        cursor = await reopened._db.execute("SELECT COUNT(*) FROM security_evidence")
        assert (await cursor.fetchone())[0] == 0
        assert not await reopened.security_candidate_has_semantic_proof(candidate_id)

        summary = await reopened.get_coverage_summary(scan_id)
        assert summary.complete is False
        assert summary.statement.startswith("Coverage incomplete")
        with pytest.raises(SecurityGateError):
            manifest.require_publication("public_pr")

        finding_for_guard = Finding(
            type=ContributionType.SECURITY_FIX, severity=Severity.HIGH,
            title=finding.title, description="fixture", file_path=finding.file_path,
            metadata={
                "security_candidate_id": candidate_id,
                "security_target_commit": pinned_sha,
            },
        )
        with pytest.raises(SecurityGateError):
            await require_confirmed_security_finding(
                reopened, finding_for_guard, "owner/repo",
                target_commit=pinned_sha, channel="public_pr",
            )
    finally:
        await reopened.close()
