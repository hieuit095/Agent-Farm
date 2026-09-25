"""Four-phase oracles against running vulnerable and fixed loopback services."""

import json
import sqlite3
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from types import SimpleNamespace
from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlsplit
from urllib.request import urlopen

import pytest

from farm_agent.core.config import FarmAgentConfig
from farm_agent.core.models import (
    Contribution,
    ContributionType,
    Finding,
    Repository,
    Severity,
)
from farm_agent.github.security_gate import handle_responsible_disclosure, run_security_gate
from farm_agent.orchestrator.memory import Memory
from farm_agent.pr.manager import PRManager
from farm_agent.security.artifacts import ArtifactStore
from farm_agent.security.closure import require_confirmed_security_finding
from farm_agent.security.oracles import (
    OracleKind,
    OracleSpec,
    ProbeRequest,
    ProofOutcome,
    run_four_phase,
)
from farm_agent.security.scope import ProgramScope, ScanManifest
from farm_agent.security.state import CandidateStatus, SecurityGateError
from farm_agent.security.threat_model import ThreatModel
from farm_agent.security.transport import ScopedHttpClient
from farm_agent.security.verifier import SemanticVerifier


def _start_service(
    mode: str, witness_url: str, side_effect: Path, tamper_paths: list[Path] | None = None,
):
    class Service(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlsplit(self.path)
            query = parse_qs(parsed.query)
            attack = query.get("attack") == ["1"]
            role = self.headers.get("X-Actor", "")
            status = 200
            body = b""
            if parsed.path == "/idor":
                if mode == "vulnerable" and role == "attacker" and tamper_paths:
                    tamper_paths[0].chmod(0o666)
                    tamper_paths[0].write_bytes(b"tampered during attack")
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


def _policy(before: str, after: str, *, commit: str = "e" * 40, **overrides) -> ProgramScope:
    fields = {
        "program_id": "cli-local", "repo": "owner/repo", "target_commit": commit,
        "allowed_origins": [before, after], "max_requests": 4,
        "test_roles": ["owner", "attacker"], "allowed_impacts": ["read_only"],
        "allow_live_testing": True, "policy_reference": "local fixture authorization",
        "surfaces": ["/idor"], "risk_classes": ["idor"],
        "trust_boundaries": ["tenant"], "assets": ["orders"],
        "attacker_inputs": ["id"], "attacker_stories": ["cross tenant read"],
    }
    fields.update(overrides)
    return ProgramScope(**fields)


def _cli_harness(base_dir: Path, policy: ProgramScope, *, live: bool = True):
    """Real config file and CLI subprocess runner over one temp SQLite database."""
    base_dir.mkdir(parents=True, exist_ok=True)
    db_path = base_dir / "cli.db"
    config_path = base_dir / "config.json"
    config_path.write_text(json.dumps({
        "storage": {"db_path": str(db_path)},
        "bounty": {
            "oracle_store_dir": str(base_dir / "oracles"),
            "live_testing_enabled": live,
            "program_scopes": [policy.model_dump(mode="json")],
        },
    }), encoding="utf-8")
    root = Path(__file__).resolve().parents[2]
    base = [sys.executable, "-m", "farm_agent.cli.main", "--config", str(config_path)]

    def command(*args):
        return subprocess.run(
            [*base, *args], cwd=root, capture_output=True, text=True,
            timeout=30, check=False,
        )

    return db_path, command


def _headers_file(path: Path, roles: tuple[str, ...] = ("owner", "attacker")) -> Path:
    path.write_text(json.dumps({role: {"X-Actor": role} for role in roles}), encoding="utf-8")
    return path


def _write_spec(directory: Path, spec: OracleSpec) -> Path:
    path = directory / "spec.json"
    path.write_text(spec.model_dump_json(), encoding="utf-8")
    return path


def _sqlite_column(db_path, query: str, params: tuple = ()) -> list:
    with sqlite3.connect(db_path) as connection:
        return [row[0] for row in connection.execute(query, params)]


def _candidate_status(db_path, candidate_id: str):
    return next(iter(_sqlite_column(
        db_path, "SELECT status FROM security_candidates WHERE id = ?", (candidate_id,),
    )), None)


def _candidate_evidence(db_path, candidate_id: str) -> list:
    return _sqlite_column(
        db_path, "SELECT kind FROM security_evidence WHERE candidate_id = ?", (candidate_id,),
    )


def _requests_used(db_path, scan_id: str):
    return next(iter(_sqlite_column(
        db_path, "SELECT requests_used FROM scan_manifests WHERE scan_id = ?", (scan_id,),
    )), None)


def _coverage_outcomes(db_path, scan_id: str) -> list:
    return _sqlite_column(
        db_path, "SELECT outcome FROM scan_coverage WHERE scan_id = ?", (scan_id,),
    )


def _finding_for(candidate_id, *, file_path="src/app.py", title="IDOR", commit="e" * 40):
    return Finding(
        type=ContributionType.SECURITY_FIX, severity=Severity.HIGH,
        title=title, description="fixture", file_path=file_path,
        metadata={
            "security_candidate_id": candidate_id,
            "security_target_commit": commit,
        },
    )


async def _assert_publication_blocked(memory, candidate_id, *, file_path, title, commit):
    """Every real publication sink must refuse a candidate without valid proof."""
    finding = _finding_for(candidate_id, file_path=file_path, title=title, commit=commit)
    for channel in ("public_pr", "private_disclosure", "local_report"):
        with pytest.raises(SecurityGateError):
            await require_confirmed_security_finding(
                memory, finding, "owner/repo", target_commit=commit, channel=channel,
            )
    github = MagicMock()
    contribution = Contribution(
        finding=finding, contribution_type=ContributionType.SECURITY_FIX,
        title=title, description="fixture",
    )
    with pytest.raises(SecurityGateError):
        await PRManager(github=github, memory=memory).create_pr(
            contribution, Repository(owner="owner", name="repo", full_name="owner/repo"),
        )
    with pytest.raises(SecurityGateError):
        await run_security_gate(
            github=github, owner="owner", repo="repo",
            dossier=SimpleNamespace(vulnerabilities=[finding]), memory=memory,
        )
    with pytest.raises(SecurityGateError):
        await handle_responsible_disclosure(
            github=github, owner="owner", repo="repo", finding=finding,
            target_commit=commit, config=FarmAgentConfig(), memory=memory,
        )
    assert github.mock_calls == []


async def _publication_blocked(db_path, candidate_id, *, file_path, title, commit):
    memory = Memory(db_path)
    await memory.init()
    try:
        await _assert_publication_blocked(
            memory, candidate_id, file_path=file_path, title=title, commit=commit,
        )
    finally:
        await memory.close()


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
        store = ArtifactStore(tmp_path / "canonical-oracles")
        artifact = store.save(_spec(kind, before, after))
        result = await SemanticVerifier(memory).verify_candidate(
            candidate_id, artifact, store,
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


@pytest.mark.asyncio
async def test_oracle_modified_by_running_target_cannot_create_proof(tmp_path):
    witness_server, witness_thread, witness_url, _ = _start_witness()
    artifact_paths = []
    side_effect = tmp_path / "unused"
    before_server, before_thread, before = _start_service(
        "vulnerable", witness_url, side_effect, artifact_paths,
    )
    after_server, after_thread, after = _start_service("fixed", witness_url, side_effect)
    memory = Memory(tmp_path / "tamper.db")
    await memory.init()
    try:
        policy = ProgramScope(
            program_id="local-tamper", repo="owner/repo", target_commit="d" * 40,
            allowed_origins=[before, after], max_requests=4,
            test_roles=["owner", "attacker"], allowed_impacts=["read_only"],
            allow_live_testing=True, policy_reference="local fixture authorization",
            surfaces=["/idor"], risk_classes=["idor"],
            trust_boundaries=["tenant"], assets=["orders"],
            attacker_inputs=["id"], attacker_stories=["cross tenant read"],
        )
        manifest = ScanManifest(scan_id="tamper", scope=policy, mode="live")
        await memory.store_scan_manifest(manifest)
        await memory.store_threat_model(ThreatModel.from_manifest(manifest))
        await memory.initialize_coverage(manifest)
        candidate_id = await memory.create_security_candidate(
            scan_id="tamper", repo="owner/repo", target_commit="d" * 40,
            file_path="src/app.py", title="IDOR",
        )
        store = ArtifactStore(tmp_path / "oracles")
        artifact = store.save(_spec(OracleKind.IDOR, before, after))
        artifact_paths.append(artifact.path)
        with pytest.raises(SecurityGateError, match="hash changed"):
            await SemanticVerifier(memory).verify_candidate(
                candidate_id, artifact, store,
                role_headers={"owner": {"X-Actor": "owner"},
                              "attacker": {"X-Actor": "attacker"}},
            )
        candidate = await memory.get_security_candidate(candidate_id)
        assert candidate["status"] == CandidateStatus.DISCOVERED
        assert not await memory.security_candidate_has_semantic_proof(candidate_id)
        assert (await memory.get_coverage_summary("tamper")).not_tested == 1
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
async def test_operator_cli_runs_real_idor_proof_and_reports_coverage(tmp_path):
    witness_server, witness_thread, witness_url, _ = _start_witness()
    side_effect = tmp_path / "unused"
    before_server, before_thread, before = _start_service("vulnerable", witness_url, side_effect)
    after_server, after_thread, after = _start_service("fixed", witness_url, side_effect)
    db_path = tmp_path / "cli.db"
    oracle_dir = tmp_path / "oracles"
    config_path = tmp_path / "config.json"
    policy = ProgramScope(
        program_id="cli-local", repo="owner/repo", target_commit="e" * 40,
        allowed_origins=[before, after], max_requests=4,
        test_roles=["owner", "attacker"], allowed_impacts=["read_only"],
        allow_live_testing=True, policy_reference="local fixture authorization",
        surfaces=["/idor"], risk_classes=["idor"],
        trust_boundaries=["tenant"], assets=["orders"],
        attacker_inputs=["id"], attacker_stories=["cross tenant read"],
    )
    config_path.write_text(json.dumps({
        "storage": {"db_path": str(db_path)},
        "bounty": {
            "oracle_store_dir": str(oracle_dir),
            "live_testing_enabled": True,
            "program_scopes": [policy.model_dump(mode="json")],
        },
    }), encoding="utf-8")
    spec_path = tmp_path / "idor-spec.json"
    spec_path.write_text(_spec(OracleKind.IDOR, before, after).model_dump_json(), encoding="utf-8")
    headers_path = tmp_path / "role-headers.json"
    headers_path.write_text(json.dumps({
        "owner": {"X-Actor": "owner"}, "attacker": {"X-Actor": "attacker"},
    }), encoding="utf-8")
    root = Path(__file__).resolve().parents[2]
    base = [sys.executable, "-m", "farm_agent.cli.main", "--config", str(config_path)]

    def command(*args):
        return subprocess.run(
            [*base, *args], cwd=root, capture_output=True, text=True,
            timeout=30, check=False,
        )

    try:
        scan = command("register-live-scan", "owner/repo", "e" * 40)
        assert scan.returncode == 0, scan.stderr
        scan_id = json.loads(scan.stdout)["scan_id"]
        candidate = command(
            "register-candidate", scan_id,
            "--file-path", "src/app.py", "--title", "CLI IDOR",
        )
        assert candidate.returncode == 0, candidate.stderr
        candidate_id = json.loads(candidate.stdout)["candidate_id"]
        listed = command("security-candidates")
        assert listed.returncode == 0, listed.stderr
        assert any(row["id"] == candidate_id for row in json.loads(listed.stdout))
        registered = command("register-oracle", str(spec_path))
        assert registered.returncode == 0, registered.stderr
        digest = json.loads(registered.stdout)["digest"]
        initial = command("scope-report", scan_id)
        assert initial.returncode == 0, initial.stderr
        assert json.loads(initial.stdout)["coverage"]["not_tested"] == 1
        verified = command(
            "verify-candidate", candidate_id,
            "--oracle-digest", digest,
            "--role-headers-file", str(headers_path),
        )
        assert verified.returncode == 0, verified.stderr
        assert json.loads(verified.stdout)["outcome"] == "verified"
        final = command("scope-report", scan_id)
        assert final.returncode == 0, final.stderr
        assert json.loads(final.stdout)["coverage"]["tested"] == 1
        assert _candidate_status(db_path, candidate_id) == "CONFIRMED"
        assert _candidate_evidence(db_path, candidate_id) == ["SEMANTIC_PROOF"]
        assert _requests_used(db_path, scan_id) == 4
    finally:
        for server, thread in (
            (before_server, before_thread), (after_server, after_thread),
            (witness_server, witness_thread),
        ):
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)


@pytest.mark.asyncio
async def test_operator_cli_live_authorization_refusals(tmp_path):
    origins = ("http://127.0.0.1:9", "http://127.0.0.1:10")
    _, command = _cli_harness(tmp_path / "off", _policy(*origins), live=False)
    refused = command("register-live-scan", "owner/repo", "e" * 40)
    assert refused.returncode == 1 and "switch is disabled" in refused.stderr
    _, command = _cli_harness(tmp_path / "nomatch", _policy(*origins))
    refused = command("register-live-scan", "owner/other", "e" * 40)
    assert refused.returncode == 1 and "no exact program" in refused.stderr.lower()
    _, command = _cli_harness(
        tmp_path / "nolive", _policy(*origins, allow_live_testing=False),
    )
    refused = command("register-live-scan", "owner/repo", "e" * 40)
    assert refused.returncode == 1 and "live testing" in refused.stderr.lower()


@pytest.mark.asyncio
async def test_operator_cli_verify_rejections_leave_candidate_unproven(tmp_path):
    witness_server, witness_thread, witness_url, _ = _start_witness()
    side_effect = tmp_path / "unused"
    before_server, before_thread, before = _start_service("vulnerable", witness_url, side_effect)
    after_server, after_thread, after = _start_service("fixed", witness_url, side_effect)
    base = _spec(OracleKind.IDOR, before, after)

    def retag(spec, field, value):
        probes = ("benign_before", "malicious_before", "malicious_after", "benign_after")
        return spec.model_copy(update={
            name: getattr(spec, name).model_copy(update={field: value}) for name in probes
        })

    cases = [
        ("excluded", base, {"excluded_endpoints": ["/idor"]}),
        ("outside_origin", base, {"allowed_origins": ["http://127.0.0.1:9"]}),
        ("wrong_role", retag(base, "role", "admin"), {}),
        ("wrong_impact", retag(base, "impact", "destructive"), {}),
        ("budget", base, {"max_requests": 1}),
    ]
    try:
        for name, spec, overrides in cases:
            case_dir = tmp_path / name
            db_path, command = _cli_harness(case_dir, _policy(before, after, **overrides))
            spec_path = _write_spec(case_dir, spec)
            headers = _headers_file(case_dir / "headers.json", ("owner", "attacker", "admin"))
            scan = command("register-live-scan", "owner/repo", "e" * 40)
            assert scan.returncode == 0, scan.stderr
            scan_id = json.loads(scan.stdout)["scan_id"]
            candidate = command(
                "register-candidate", scan_id, "--file-path", "src/app.py", "--title", name,
            )
            candidate_id = json.loads(candidate.stdout)["candidate_id"]
            digest = json.loads(
                command("register-oracle", str(spec_path)).stdout
            )["digest"]
            verified = command(
                "verify-candidate", candidate_id, "--oracle-digest", digest,
                "--role-headers-file", str(headers),
            )
            assert verified.returncode == 1, (name, verified.stdout, verified.stderr)
            assert _candidate_status(db_path, candidate_id) == "DISCOVERED"
            assert _candidate_evidence(db_path, candidate_id) == []
            assert _coverage_outcomes(db_path, scan_id) == ["not_tested"]
            await _publication_blocked(
                db_path, candidate_id, file_path="src/app.py", title=name, commit="e" * 40,
            )
    finally:
        for server, thread in (
            (before_server, before_thread), (after_server, after_thread),
            (witness_server, witness_thread),
        ):
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)


@pytest.mark.asyncio
async def test_operator_cli_verify_integrity_negatives(tmp_path):
    witness_server, witness_thread, witness_url, _ = _start_witness()
    side_effect = tmp_path / "unused"
    before_server, before_thread, before = _start_service("vulnerable", witness_url, side_effect)
    after_server, after_thread, after = _start_service("fixed", witness_url, side_effect)
    try:
        tamper_dir = tmp_path / "tamper"
        db_path, command = _cli_harness(tamper_dir, _policy(before, after))
        spec_path = _write_spec(tamper_dir, _spec(OracleKind.IDOR, before, after))
        headers = _headers_file(tamper_dir / "headers.json")
        scan = command("register-live-scan", "owner/repo", "e" * 40)
        scan_id = json.loads(scan.stdout)["scan_id"]
        candidate = command(
            "register-candidate", scan_id, "--file-path", "src/app.py", "--title", "tamper",
        )
        candidate_id = json.loads(candidate.stdout)["candidate_id"]
        registered = json.loads(command("register-oracle", str(spec_path)).stdout)
        Path(registered["path"]).chmod(0o666)
        Path(registered["path"]).write_bytes(b"tampered")
        tampered = command(
            "verify-candidate", candidate_id, "--oracle-digest", registered["digest"],
            "--role-headers-file", str(headers),
        )
        assert tampered.returncode == 1 and "hash changed" in tampered.stderr
        assert _candidate_status(db_path, candidate_id) == "DISCOVERED"
        assert _candidate_evidence(db_path, candidate_id) == []
        await _publication_blocked(
            db_path, candidate_id, file_path="src/app.py", title="tamper", commit="e" * 40,
        )

        ssrf_dir = tmp_path / "ssrf"
        ssrf_policy = _policy(before, after, surfaces=["/fetch"], risk_classes=["ssrf"])
        db_path, command = _cli_harness(ssrf_dir, ssrf_policy)
        spec_path = _write_spec(ssrf_dir, _spec(OracleKind.SSRF, before, after))
        headers = _headers_file(ssrf_dir / "headers.json")
        scan = command("register-live-scan", "owner/repo", "e" * 40)
        scan_id = json.loads(scan.stdout)["scan_id"]
        candidate = command(
            "register-candidate", scan_id, "--file-path", "src/app.py", "--title", "ssrf",
        )
        candidate_id = json.loads(candidate.stdout)["candidate_id"]
        digest = json.loads(command("register-oracle", str(spec_path)).stdout)["digest"]
        unwitnessed = command(
            "verify-candidate", candidate_id, "--oracle-digest", digest,
            "--role-headers-file", str(headers),
        )
        assert unwitnessed.returncode == 1 and "witness" in unwitnessed.stderr
        assert _requests_used(db_path, scan_id) == 0  # rejected before any probe
        assert _candidate_status(db_path, candidate_id) == "DISCOVERED"
        assert _candidate_evidence(db_path, candidate_id) == []
        assert _coverage_outcomes(db_path, scan_id) == ["not_tested"]
        await _publication_blocked(
            db_path, candidate_id, file_path="src/app.py", title="ssrf", commit="e" * 40,
        )

        cmd_dir = tmp_path / "cmd"
        cmd_policy = _policy(
            before, after, surfaces=["/execute"], risk_classes=["command_injection"],
        )
        db_path, command = _cli_harness(cmd_dir, cmd_policy)
        spec_path = _write_spec(cmd_dir, _spec(OracleKind.COMMAND_INJECTION, before, after))
        headers = _headers_file(cmd_dir / "headers.json")
        scan = command("register-live-scan", "owner/repo", "e" * 40)
        scan_id = json.loads(scan.stdout)["scan_id"]
        candidate = command(
            "register-candidate", scan_id, "--file-path", "src/app.py", "--title", "cmd",
        )
        candidate_id = json.loads(candidate.stdout)["candidate_id"]
        digest = json.loads(command("register-oracle", str(spec_path)).stdout)["digest"]
        unwitnessed = command(
            "verify-candidate", candidate_id, "--oracle-digest", digest,
            "--role-headers-file", str(headers),
        )
        assert unwitnessed.returncode == 1 and "witness" in unwitnessed.stderr
        assert _requests_used(db_path, scan_id) == 0  # rejected before any probe
        assert _candidate_status(db_path, candidate_id) == "DISCOVERED"
        assert _candidate_evidence(db_path, candidate_id) == []
        assert _coverage_outcomes(db_path, scan_id) == ["not_tested"]
        await _publication_blocked(
            db_path, candidate_id, file_path="src/app.py", title="cmd", commit="e" * 40,
        )
    finally:
        for server, thread in (
            (before_server, before_thread), (after_server, after_thread),
            (witness_server, witness_thread),
        ):
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)


@pytest.mark.asyncio
async def test_operator_cli_semantic_negatives_close_open_proof_gap(tmp_path):
    for name, before_mode, close_after in (
        ("empty", "empty", False), ("transport", "vulnerable", True),
    ):
        witness_server, witness_thread, witness_url, _ = _start_witness()
        side_effect = tmp_path / "unused"
        before_server, before_thread, before = _start_service(
            before_mode, witness_url, side_effect,
        )
        after_server, after_thread, after = _start_service("fixed", witness_url, side_effect)
        if close_after:
            after_server.shutdown()
            after_server.server_close()
            after_thread.join(timeout=3)
        case_dir = tmp_path / name
        db_path, command = _cli_harness(case_dir, _policy(before, after))
        spec_path = _write_spec(case_dir, _spec(OracleKind.IDOR, before, after))
        headers = _headers_file(case_dir / "headers.json")
        try:
            scan = command("register-live-scan", "owner/repo", "e" * 40)
            scan_id = json.loads(scan.stdout)["scan_id"]
            candidate = command(
                "register-candidate", scan_id, "--file-path", "src/app.py", "--title", name,
            )
            candidate_id = json.loads(candidate.stdout)["candidate_id"]
            digest = json.loads(command("register-oracle", str(spec_path)).stdout)["digest"]
            verified = command(
                "verify-candidate", candidate_id, "--oracle-digest", digest,
                "--role-headers-file", str(headers),
            )
            assert verified.returncode == 2, (name, verified.stdout, verified.stderr)
            assert json.loads(verified.stdout)["outcome"] != "verified"
            assert _candidate_status(db_path, candidate_id) == "OPEN_PROOF_GAP"
            assert _coverage_outcomes(db_path, scan_id) == ["inconclusive"]
            await _publication_blocked(
                db_path, candidate_id, file_path="src/app.py", title=name, commit="e" * 40,
            )
        finally:
            servers = [(before_server, before_thread), (witness_server, witness_thread)]
            if not close_after:
                servers.append((after_server, after_thread))
            for server, thread in servers:
                server.shutdown()
                server.server_close()
                thread.join(timeout=3)


@pytest.mark.asyncio
async def test_operator_cli_repeat_verification_is_fail_closed(tmp_path):
    witness_server, witness_thread, witness_url, _ = _start_witness()
    side_effect = tmp_path / "unused"
    before_server, before_thread, before = _start_service("vulnerable", witness_url, side_effect)
    after_server, after_thread, after = _start_service("fixed", witness_url, side_effect)
    db_path, command = _cli_harness(tmp_path, _policy(before, after))
    spec_path = _write_spec(tmp_path, _spec(OracleKind.IDOR, before, after))
    headers = _headers_file(tmp_path / "headers.json")
    try:
        scan = command("register-live-scan", "owner/repo", "e" * 40)
        scan_id = json.loads(scan.stdout)["scan_id"]
        candidate = command(
            "register-candidate", scan_id, "--file-path", "src/app.py", "--title", "IDOR",
        )
        candidate_id = json.loads(candidate.stdout)["candidate_id"]
        digest = json.loads(command("register-oracle", str(spec_path)).stdout)["digest"]
        first = command(
            "verify-candidate", candidate_id, "--oracle-digest", digest,
            "--role-headers-file", str(headers),
        )
        assert first.returncode == 0, first.stderr
        used = _requests_used(db_path, scan_id)
        assert used == 4
        second = command(
            "verify-candidate", candidate_id, "--oracle-digest", digest,
            "--role-headers-file", str(headers),
        )
        assert second.returncode == 1 and "already has semantic" in second.stderr
        assert _requests_used(db_path, scan_id) == used
        assert _candidate_status(db_path, candidate_id) == "CONFIRMED"
        assert _candidate_evidence(db_path, candidate_id) == ["SEMANTIC_PROOF"]
        memory = Memory(db_path)
        await memory.init()
        try:
            finding = _finding_for(
                candidate_id, file_path="src/app.py", title="IDOR", commit="e" * 40,
            )
            for channel in ("public_pr", "private_disclosure", "local_report"):
                with pytest.raises(SecurityGateError):
                    await require_confirmed_security_finding(
                        memory, finding, "owner/repo",
                        target_commit="e" * 40, channel=channel,
                    )
        finally:
            await memory.close()
    finally:
        for server, thread in (
            (before_server, before_thread), (after_server, after_thread),
            (witness_server, witness_thread),
        ):
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)


@pytest.mark.asyncio
async def test_operator_cli_rejects_windows_drive_candidate_paths(tmp_path):
    origins = ("http://127.0.0.1:9", "http://127.0.0.1:10")
    db_path, command = _cli_harness(tmp_path, _policy(*origins))
    scan = command("register-live-scan", "owner/repo", "e" * 40)
    scan_id = json.loads(scan.stdout)["scan_id"]
    for bad in ("C:/Windows/evil.py", "C:\\Windows\\evil.py", "/etc/passwd", "a/../../b.py"):
        rejected = command(
            "register-candidate", scan_id, "--file-path", bad, "--title", "x",
        )
        assert rejected.returncode == 1, bad
    accepted = command(
        "register-candidate", scan_id, "--file-path", "src/app.py", "--title", "ok",
    )
    assert accepted.returncode == 0, accepted.stderr
    accepted_id = json.loads(accepted.stdout)["candidate_id"]
    assert _candidate_status(db_path, accepted_id) == "DISCOVERED"


@pytest.mark.asyncio
async def test_operator_cli_other_commit_is_rejected_and_unpublishable(tmp_path):
    origins = ("http://127.0.0.1:9", "http://127.0.0.1:10")
    other = "f" * 40
    db_path, command = _cli_harness(tmp_path, _policy(*origins))
    refused = command("register-live-scan", "owner/repo", other)
    assert refused.returncode == 1 and "no exact program" in refused.stderr.lower()
    assert not db_path.exists(), "a refused live scan must not persist anything"
    scan = command("register-live-scan", "owner/repo", "e" * 40)
    assert scan.returncode == 0, scan.stderr
    scan_id = json.loads(scan.stdout)["scan_id"]
    candidate = command(
        "register-candidate", scan_id, "--file-path", "src/app.py", "--title", "IDOR",
    )
    candidate_id = json.loads(candidate.stdout)["candidate_id"]
    assert _candidate_status(db_path, candidate_id) == "DISCOVERED"
    assert _candidate_evidence(db_path, candidate_id) == []
    assert _coverage_outcomes(db_path, scan_id) == ["not_tested"]
    await _publication_blocked(
        db_path, candidate_id, file_path="src/app.py", title="IDOR", commit="e" * 40,
    )
    memory = Memory(db_path)
    await memory.init()
    try:
        with pytest.raises(SecurityGateError):
            await require_confirmed_security_finding(
                memory, _finding_for(candidate_id, commit=other), "owner/repo",
                target_commit=other, channel="public_pr",
            )
    finally:
        await memory.close()


@pytest.mark.asyncio
async def test_operator_cli_does_not_leak_credentials_or_response_secrets(tmp_path):
    role_secret = "SECRET-ROLE-CREDENTIAL-9137"
    response_marker = "private-order"
    witness_server, witness_thread, witness_url, _ = _start_witness()
    side_effect = tmp_path / "unused"
    before_server, before_thread, before = _start_service("vulnerable", witness_url, side_effect)
    after_server, after_thread, after = _start_service("fixed", witness_url, side_effect)
    db_path, command = _cli_harness(tmp_path, _policy(before, after))
    spec_path = _write_spec(tmp_path, _spec(OracleKind.IDOR, before, after))
    headers_path = tmp_path / "headers.json"
    headers_path.write_text(json.dumps({
        "owner": {"X-Actor": "owner", "Authorization": f"Bearer {role_secret}"},
        "attacker": {"X-Actor": "attacker", "Authorization": f"Bearer {role_secret}"},
    }), encoding="utf-8")
    observed = []

    def run(*args):
        proc = command(*args)
        observed.extend((proc.stdout, proc.stderr))
        return proc

    try:
        scan = run("register-live-scan", "owner/repo", "e" * 40)
        assert scan.returncode == 0, scan.stderr
        scan_id = json.loads(scan.stdout)["scan_id"]
        candidate = run(
            "register-candidate", scan_id, "--file-path", "src/app.py", "--title", "IDOR",
        )
        candidate_id = json.loads(candidate.stdout)["candidate_id"]
        registered = run("register-oracle", str(spec_path))
        digest = json.loads(registered.stdout)["digest"]
        verified = run(
            "verify-candidate", candidate_id, "--oracle-digest", digest,
            "--role-headers-file", str(headers_path),
        )
        assert verified.returncode == 0, verified.stderr
        run("security-candidates")
        run("scope-report", scan_id)
    finally:
        for server, thread in (
            (before_server, before_thread), (after_server, after_thread),
            (witness_server, witness_thread),
        ):
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    assert role_secret in headers_path.read_text(encoding="utf-8")
    assert response_marker == _spec(OracleKind.IDOR, before, after).exploit_marker
    assert all(role_secret not in text for text in observed)
    assert all(response_marker not in text for text in observed)
    assert _candidate_status(db_path, candidate_id) == "CONFIRMED"
