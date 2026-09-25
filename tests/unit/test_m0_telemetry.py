"""M0 events persist without storing prompts, source, or PoC output."""

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from farm_agent.core.config import FarmAgentConfig
from farm_agent.core.models import Repository
from farm_agent.orchestrator.memory import Memory
from farm_agent.orchestrator.pipeline import FarmAgentPipeline, PipelineResult


@pytest.mark.asyncio
async def test_scan_events_roundtrip(tmp_path):
    memory = Memory(tmp_path / "m0.sqlite")
    await memory.init()
    try:
        await memory.record_scan_event(
            scan_id="scan-1", candidate_id="candidate-1", repo="owner/repo",
            pipeline="standard", stage="poc", outcome="error",
            reason_code="TimeoutError", duration_ms=45,
        )
        events = await memory.get_scan_events("scan-1")
        assert len(events) == 1
        assert events[0]["candidate_id"] == "candidate-1"
        assert events[0]["reason_code"] == "TimeoutError"
        assert events[0]["duration_ms"] == 45
        assert await memory.get_scan_events("other") == []
        report_script = Path(__file__).resolve().parents[2] / "scripts" / "m0_report.py"
        report = subprocess.run(
            [sys.executable, str(report_script), str(tmp_path / "m0.sqlite"),
             "--scan-id", "scan-1"],
            check=True, capture_output=True, text=True,
        )
        summary = json.loads(report.stdout)
        assert summary[0]["items"] == 1
        assert summary[0]["input_tokens"] is None
    finally:
        await memory.close()


@pytest.mark.asyncio
async def test_standard_scan_span_closes_on_early_return():
    pipeline = FarmAgentPipeline(FarmAgentConfig())
    pipeline._memory = AsyncMock()
    pipeline._process_repo_impl = AsyncMock(return_value=PipelineResult())
    repo = Repository(owner="owner", name="repo", full_name="owner/repo")

    await pipeline._process_repo(repo, dry_run=True)

    events = [call.kwargs for call in pipeline._memory.record_scan_event.await_args_list]
    assert [event["outcome"] for event in events] == ["started", "finished"]
    assert events[0]["scan_id"] == events[1]["scan_id"]
    assert events[1]["duration_ms"] >= 0
