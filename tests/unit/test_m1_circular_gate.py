"""Scanner failures and empty prefilters cannot become clean circular scans."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from farm_agent.analysis.analyzer import BloodhoundAnalyzer, ScanIncompleteError
from farm_agent.core.config import FarmAgentConfig
from farm_agent.core.models import Repository, VulnerabilityDossier
from farm_agent.orchestrator.pipeline import FarmAgentPipeline


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("failure", "reason"),
    [("missing", "SCANNER_UNAVAILABLE"), ("timeout", "SCANNER_TIMEOUT"),
     ("invalid_json", "SCANNER_INVALID_JSON")],
)
async def test_semgrep_failure_is_not_an_empty_result(tmp_path, failure, reason):
    analyzer = object.__new__(BloodhoundAnalyzer)
    analyzer._config = MagicMock(semgrep_rulesets=["p/default"])
    analyzer.SEMGREP_TIMEOUT = 1
    analyzer._check_semgrep_available = lambda: failure != "missing"
    proc = MagicMock(returncode=0)
    proc.communicate = AsyncMock(
        side_effect=TimeoutError() if failure == "timeout" else None,
        return_value=(b"invalid json", b"") if failure == "invalid_json" else None,
    )
    with (
        patch("farm_agent.analysis.analyzer.asyncio.create_subprocess_exec",
              new=AsyncMock(return_value=proc)),
        pytest.raises(ScanIncompleteError) as exc,
    ):
        await analyzer._run_semgrep(Path(tmp_path))
    assert exc.value.reason_code == reason


@pytest.mark.asyncio
@pytest.mark.parametrize("scanner_error", [False, True])
async def test_circular_scan_marks_partial_not_clean(scanner_error):
    pipeline = FarmAgentPipeline(FarmAgentConfig())
    repo = Repository(owner="owner", name="repo", full_name="owner/repo")
    target = MagicMock(repo_url="https://github.com/owner/repo", scanned_at=None)
    memory = MagicMock()
    memory.get_today_pr_count = AsyncMock(return_value=0)
    memory.record_scan_event = AsyncMock()
    github = MagicMock()
    github.get_repo_details = AsyncMock(return_value=repo)

    async def initialize():
        pipeline._memory = memory
        pipeline._github = github

    pipeline._init_components = AsyncMock(side_effect=initialize)
    pipeline._cleanup = AsyncMock()
    discovery = MagicMock()
    discovery.initialize = AsyncMock()
    discovery.get_next_target = AsyncMock(return_value=target)
    discovery.mark_status = AsyncMock()
    dossier = VulnerabilityDossier(
        repo_url=target.repo_url, target_commit="a" * 40, vulnerabilities=[]
    )
    bloodhound = MagicMock()
    bloodhound.run_bloodhound = AsyncMock(
        side_effect=ScanIncompleteError("SCANNER_TIMEOUT") if scanner_error else None,
        return_value=dossier,
    )

    with (
        patch("farm_agent.orchestrator.pipeline.DatabaseTargetDiscovery",
              return_value=discovery),
        patch("farm_agent.orchestrator.pipeline.BloodhoundAnalyzer",
              return_value=bloodhound),
    ):
        result = await pipeline.run_circular(dry_run=True)

    discovery.mark_status.assert_awaited_once_with(target.repo_url, "PARTIAL_SCAN")
    assert result.prs_created == 0
    assert bool(result.errors) is scanner_error
