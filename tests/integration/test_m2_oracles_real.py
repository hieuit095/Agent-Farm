"""Four-phase oracles against running vulnerable and fixed loopback services."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import parse_qs, urlsplit
from urllib.request import urlopen

import pytest

from farm_agent.core.config import FarmAgentConfig
from farm_agent.core.models import ContributionType, Finding, Severity
from farm_agent.github.security_gate import handle_responsible_disclosure
from farm_agent.orchestrator.memory import Memory
from farm_agent.security.closure import require_confirmed_security_finding
from farm_agent.security.oracles import (
    OracleKind,
    OracleSpec,
    ProbeRequest,
    ProofOutcome,
    run_four_phase,
)
from farm_agent.security.scope import ProgramScope, ScanManifest
from farm_agent.security.state import CandidateStatus
from farm_agent.security.threat_model import ThreatModel
from farm_agent.security.transport import ScopedHttpClient
from farm_agent.security.verifier import SemanticVerifier


def _start_service(mode: str, witness_url: str, side_effect: Path):
    class Service(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlsplit(self.path)
            query = parse_qs(parsed.query)
            attack = query.get("attack") == ["1"]
            role = self.headers.get("X-Actor", "")
            status = 200
            body = b""
            if parsed.path == "/idor":
                if mode == "regression" and role == "owner":
                    status = 503
                elif mode in {"fixed", "regression"} and role == "attacker":
                    status = 403
                elif mode == "empty" and role == "attacker":
                    body = b"{}"
                else:
                    body = b'{"id":"order-7","tenant":"alpha","marker":"private-order"}'
            elif parsed.path == "/sql":
                rows = [{"marker": "normal-row"}]
                if attack and mode == "vulnerable":
                    rows.append({"marker": "secret-row"})
                body = json.dumps({"rows": rows}).encode()
            elif parsed.path == "/file":
                if attack and mode == "vulnerable":
                    body = b"outside-root-secret"
                elif attack:
                    status = 403
                else:
                    body = b"public-file"
            elif parsed.path == "/fetch":
                if attack and mode == "vulnerable":
                    with urlopen(witness_url, timeout=2) as response:
                        response.read()
                elif attack:
                    status = 403
                body = b"public-feed"
            elif parsed.path == "/execute":
                if attack and mode == "vulnerable":
                    with side_effect.open("ab") as output:
                        output.write(b"x")
                elif attack:
                    status = 403
                body = b"job-ok"
            else:
                status = 404
            self.send_response(status)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Service)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, f"http://127.0.0.1:{server.server_port}"


def _start_witness():
    class Witness(BaseHTTPRequestHandler):
        hits = 0

        def do_GET(self):
            Witness.hits += 1
            self.send_response(200)
            self.end_headers()

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Witness)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, f"http://127.0.0.1:{server.server_port}/hit", Witness


def _spec(kind: OracleKind, before: str, after: str) -> OracleSpec:
    endpoint = {
        OracleKind.IDOR: "idor", OracleKind.SQLI: "sql",
        OracleKind.TRAVERSAL: "file", OracleKind.SSRF: "fetch",
        OracleKind.COMMAND_INJECTION: "execute",
    }[kind]
    def benign(origin):
        return ProbeRequest(
            method="GET", url=f"{origin}/{endpoint}", role="owner", impact="read_only",
        )

    def malicious(origin):
        suffix = "" if kind == OracleKind.IDOR else "?attack=1"
        return ProbeRequest(
            method="GET", url=f"{origin}/{endpoint}{suffix}",
            role="attacker", impact="read_only",
        )
    marker = {
        OracleKind.IDOR: ("private-order", "private-order"),
        OracleKind.SQLI: ("normal-row", "secret-row"),
        OracleKind.TRAVERSAL: ("public-file", "outside-root-secret"),
        OracleKind.SSRF: ("public-feed", "callback"),
        OracleKind.COMMAND_INJECTION: ("job-ok", "side-effect"),
    }[kind]
    return OracleSpec(
        kind=kind, surface=f"/{endpoint}", risk_class=kind.value,
        benign_before=benign(before), malicious_before=malicious(before),
        malicious_after=malicious(after), benign_after=benign(after),
        benign_marker=marker[0], exploit_marker=marker[1],
        owner_tenant="alpha", attacker_tenant="beta", object_id="order-7",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", list(OracleKind))
async def test_real_four_phase_semantics(tmp_path, kind):
    witness_server, witness_thread, witness_url, witness = _start_witness()
    side_effect = tmp_path / "command-witness"
    before_server, before_thread, before = _start_service("vulnerable", witness_url, side_effect)
    after_server, after_thread, after = _start_service("fixed", witness_url, side_effect)
    memory = Memory(tmp_path / "oracle.db")
    await memory.init()
    try:
        policy = ProgramScope(
            program_id="local-oracle", repo="owner/repo", target_commit="a" * 40,
            allowed_origins=[before, after], max_requests=4,
            test_roles=["owner", "attacker"], allowed_impacts=["read_only"],
            allow_live_testing=True, policy_reference="local fixture authorization",
            allow_public_pr=True, allow_private_disclosure=True,
            surfaces=["/idor", "/sql", "/file", "/fetch", "/execute"],
            risk_classes=[kind.value], trust_boundaries=["tenant or process"],
            assets=["test records"], attacker_inputs=["query parameter"],
            attacker_stories=["controlled local impact"],
        )
        manifest = ScanManifest(scan_id="real-oracle", scope=policy, mode="live")
        await memory.store_scan_manifest(manifest)
        await memory.store_threat_model(ThreatModel.from_manifest(manifest))
        await memory.initialize_coverage(manifest)
        candidate_id = await memory.create_security_candidate(
            scan_id="real-oracle", repo="owner/repo", target_commit="a" * 40,
            file_path="src/app.py", title="Real local impact",
        )
        witness_counter = (
            (lambda: witness.hits) if kind == OracleKind.SSRF
            else (lambda: side_effect.stat().st_size if side_effect.exists() else 0)
            if kind == OracleKind.COMMAND_INJECTION else None
        )
        result = await SemanticVerifier(memory).verify_candidate(
            candidate_id, _spec(kind, before, after),
            role_headers={"owner": {"X-Actor": "owner"},
                          "attacker": {"X-Actor": "attacker"}},
            witness_counter=witness_counter,
        )
        assert result.outcome == ProofOutcome.VERIFIED, result.reason
        assert len(result.evidence_hash) == 64
        candidate = await memory.get_security_candidate(candidate_id)
        assert candidate["status"] == CandidateStatus.CONFIRMED
        assert (await memory.get_coverage_summary("real-oracle")).tested == 1
        finding = Finding(
            type=ContributionType.SECURITY_FIX, severity=Severity.HIGH,
            title="Real local impact", description="Fixture exploit", file_path="src/app.py",
            metadata={"security_candidate_id": candidate_id, "security_target_commit": "a" * 40},
        )
        await require_confirmed_security_finding(
            memory, finding, "owner/repo", channel="public_pr",
        )
        if kind == OracleKind.IDOR:
            config = FarmAgentConfig()
            config.bounty.bounty_reports_dir = str(tmp_path / "reports")
            report = await handle_responsible_disclosure(
                github=None, owner="owner", repo="repo", finding=finding,
                target_commit="a" * 40, config=config, memory=memory,
            )
            assert Path(report.report_file_path).is_file()
            assert "owner/repo" in Path(report.report_file_path).read_text(encoding="utf-8")
    finally:
        await memory.close()
        for server, thread in (
            (before_server, before_thread), (after_server, after_thread),
            (witness_server, witness_thread),
        ):
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)


@pytest.mark.asyncio
async def test_real_idor_empty_success_body_is_not_proof(tmp_path):
    witness_server, witness_thread, witness_url, _ = _start_witness()
    side_effect = tmp_path / "unused"
    before_server, before_thread, before = _start_service("empty", witness_url, side_effect)
    after_server, after_thread, after = _start_service("fixed", witness_url, side_effect)
    memory = Memory(tmp_path / "idor-negative.db")
    await memory.init()
    try:
        policy = ProgramScope(
            program_id="local-negative", repo="owner/repo", target_commit="b" * 40,
            allowed_origins=[before, after], max_requests=4,
            test_roles=["owner", "attacker"], allowed_impacts=["read_only"],
            allow_live_testing=True, policy_reference="local fixture authorization",
            surfaces=["/idor"], risk_classes=["idor"],
            trust_boundaries=["tenant"], assets=["orders"],
            attacker_inputs=["id"], attacker_stories=["cross tenant read"],
        )
        await memory.store_scan_manifest(ScanManifest(
            scan_id="empty-idor", scope=policy, mode="live",
        ))
        async with ScopedHttpClient(memory, "empty-idor") as client:
            result = await run_four_phase(
                _spec(OracleKind.IDOR, before, after), client, target_commit="b" * 40,
                role_headers={"owner": {"X-Actor": "owner"},
                              "attacker": {"X-Actor": "attacker"}},
            )
        assert result.outcome == ProofOutcome.NOT_TRIGGERED
    finally:
        await memory.close()
        for server, thread in (
            (before_server, before_thread), (after_server, after_thread),
            (witness_server, witness_thread),
        ):
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("after_mode", "expected"),
    [("vulnerable", ProofOutcome.PATCH_FAILED),
     ("regression", ProofOutcome.REGRESSION),
     ("closed", ProofOutcome.INCONCLUSIVE)],
)
async def test_real_idor_distinguishes_patch_failure_regression_and_transport(
    tmp_path, after_mode, expected,
):
    witness_server, witness_thread, witness_url, _ = _start_witness()
    side_effect = tmp_path / "unused"
    before_server, before_thread, before = _start_service("vulnerable", witness_url, side_effect)
    after_server, after_thread, after = _start_service(
        "fixed" if after_mode == "closed" else after_mode, witness_url, side_effect,
    )
    if after_mode == "closed":
        after_server.shutdown()
        after_server.server_close()
        after_thread.join(timeout=3)
    memory = Memory(tmp_path / "outcome.db")
    await memory.init()
    try:
        policy = ProgramScope(
            program_id="local-outcomes", repo="owner/repo", target_commit="c" * 40,
            allowed_origins=[before, after], max_requests=4,
            test_roles=["owner", "attacker"], allowed_impacts=["read_only"],
            allow_live_testing=True, policy_reference="local fixture authorization",
            surfaces=["/idor"], risk_classes=["idor"],
            trust_boundaries=["tenant"], assets=["orders"],
            attacker_inputs=["id"], attacker_stories=["cross tenant read"],
        )
        await memory.store_scan_manifest(ScanManifest(
            scan_id="outcome", scope=policy, mode="live",
        ))
        async with ScopedHttpClient(memory, "outcome") as client:
            result = await run_four_phase(
                _spec(OracleKind.IDOR, before, after), client, target_commit="c" * 40,
                role_headers={"owner": {"X-Actor": "owner"},
                              "attacker": {"X-Actor": "attacker"}},
            )
        assert result.outcome == expected, result.reason
    finally:
        await memory.close()
        services = [(before_server, before_thread), (witness_server, witness_thread)]
        if after_mode != "closed":
            services.append((after_server, after_thread))
        for server, thread in services:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)
