"""A live-forbidden program yields a durable scope gap at a real pinned Git SHA.

The target SHA comes from a real local Git repository and the scan state is real
SQLite. Only the network clone, the LLM analyzer, the GitHub client and repo
guidelines are replaced, because they need a network or paid model. None of them
proves the security property under test.
"""

import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from farm_agent.core.config import FarmAgentConfig
from farm_agent.core.models import AnalysisResult, Repository
from farm_agent.orchestrator.memory import Memory
from farm_agent.orchestrator.pipeline import FarmAgentPipeline
from farm_agent.security.scope import ProgramScope
from farm_agent.security.state import SecurityGateError


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


@pytest.mark.asyncio
async def test_live_forbidden_program_yields_durable_scope_gap(tmp_path):
    repo_dir = tmp_path / "target"
    pinned_sha = _git_repo(repo_dir)
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
        pipeline = FarmAgentPipeline(config)
        pipeline._memory = memory
        pipeline._github = MagicMock()
        pipeline._github.check_interaction_limits = AsyncMock(return_value=False)
        pipeline._github.fetch_recent_maintainer_comments = AsyncMock(return_value=[])
        pipeline._analyzer = MagicMock()
        pipeline._analyzer.analyze = AsyncMock(
            return_value=AnalysisResult(repo=repo, findings=[])
        )
        pipeline._llm = MagicMock()
        pipeline._check_ai_policy = AsyncMock(return_value=False)
        guidelines = MagicMock(subsystem_docs={}, has_guidelines=False)
        guidelines.discover_subsystem_docs = AsyncMock(return_value={})
        with (
            patch("farm_agent.orchestrator.pipeline.fetch_repo_guidelines",
                  new=AsyncMock(return_value=guidelines)),
            # Clone needs the network; the SHA below is read from the real repo.
            patch.object(FarmAgentPipeline, "_clone_and_patch_repo",
                         new=AsyncMock(return_value=str(repo_dir))),
        ):
            result = await pipeline._process_repo(repo, dry_run=True, max_prs=1)
    finally:
        await memory.close()
        probe_server.shutdown()
        probe_server.server_close()
        probe_thread.join(timeout=3)

    assert probe.hits == 0, "a live-forbidden program must not send a live request"
    assert result.prs_created == 0
    reopened = Memory(tmp_path / "memory.db")
    await reopened.init()
    try:
        cursor = await reopened._db.execute("SELECT scan_id FROM scan_manifests")
        row = await cursor.fetchone()
        assert row is not None, "the scan is still authorized offline"
        manifest = await reopened.get_scan_manifest(row[0])
        assert manifest.mode == "offline"
        assert manifest.scope.target_commit == pinned_sha
        events = await reopened.get_scan_events(row[0])
        assert any(
            event["reason_code"] == "LIVE_TESTING_NOT_AUTHORIZED"
            and event["outcome"] == "blocked" for event in events
        )
        summary = await reopened.get_coverage_summary(row[0])
        assert summary.complete is False
        assert summary.statement.startswith("Coverage incomplete")
        with pytest.raises(SecurityGateError):
            manifest.require_publication("public_pr")
    finally:
        await reopened.close()
