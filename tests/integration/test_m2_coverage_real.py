"""Threat assumptions and coverage survive a real SQLite restart."""

import pytest

from farm_agent.orchestrator.memory import Memory
from farm_agent.security.coverage import CoverageOutcome
from farm_agent.security.scope import ProgramScope, ScanManifest
from farm_agent.security.state import SecurityGateError
from farm_agent.security.threat_model import ThreatModel


@pytest.mark.asyncio
async def test_threat_versions_and_coverage_are_persisted_without_false_clean(tmp_path):
    path = tmp_path / "scan.db"
    manifest = ScanManifest(
        scan_id="scan-coverage", scope=ProgramScope(
            program_id="authorized-local", repo="owner/repo", target_commit="a" * 40,
            policy_reference="operator scope revision 1",
            surfaces=["/orders/{id}", "/files/{name}"],
            risk_classes=["idor", "traversal"],
            test_roles=["owner", "attacker"], trust_boundaries=["tenant boundary"],
            assets=["orders", "files"], attacker_inputs=["id", "name"],
            attacker_stories=["cross tenant read", "read outside root"],
        ),
    )
    memory = Memory(path)
    await memory.init()
    try:
        await memory.store_scan_manifest(manifest)
        original = ThreatModel.from_manifest(manifest)
        await memory.store_threat_model(original)
        with pytest.raises(SecurityGateError, match="version conflict"):
            await memory.store_threat_model(original)
        amended = original.amended(
            "Add service account boundary", provenance="operator review 2",
            changes={"actors": ["owner", "attacker", "service_account"]},
        )
        await memory.store_threat_model(amended, expected_version=1)
        assert (await memory.get_threat_model("scan-coverage")).actors[-1] == "service_account"

        await memory.initialize_coverage(manifest)
        summary = await memory.get_coverage_summary("scan-coverage")
        assert summary.total == 4 and summary.not_tested == 4
        assert not summary.complete and "4 not tested" in summary.statement
        with pytest.raises(SecurityGateError, match="evidence hash"):
            await memory.record_coverage(
                "scan-coverage", "/orders/{id}", "idor", CoverageOutcome.TESTED,
            )
        await memory.record_coverage(
            "scan-coverage", "/orders/{id}", "idor", CoverageOutcome.TESTED,
            evidence_hash="b" * 64,
        )
        await memory.record_coverage(
            "scan-coverage", "/files/{name}", "traversal", CoverageOutcome.BLOCKED,
            reason_code="SANDBOX_UNAVAILABLE",
        )
        # A later observation updates the same coverage cell instead of being rejected.
        await memory.record_coverage(
            "scan-coverage", "/orders/{id}", "idor", CoverageOutcome.TESTED,
            evidence_hash="c" * 64,
        )
    finally:
        await memory.close()

    reopened = Memory(path)
    await reopened.init()
    try:
        summary = await reopened.get_coverage_summary("scan-coverage")
        assert (summary.tested, summary.blocked, summary.not_tested) == (1, 1, 2)
        assert not summary.complete
        assert "1 blocked" in summary.statement
        cursor = await reopened._db.execute(
            "SELECT evidence_hash FROM scan_coverage "
            "WHERE scan_id = ? AND surface = ? AND risk_class = ?",
            ("scan-coverage", "/orders/{id}", "idor"),
        )
        assert (await cursor.fetchone())[0] == "c" * 64
        assert (await reopened.get_threat_model("scan-coverage")).version == 2
    finally:
        await reopened.close()
