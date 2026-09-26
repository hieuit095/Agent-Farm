"""Deterministic four-step security proof over real HTTP observations."""

import hashlib
import inspect
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from farm_agent.security.evidence import evidence_hash
from farm_agent.security.state import SecurityGateError
from farm_agent.security.transport import HttpObservation, ScopedHttpClient


class OracleKind(StrEnum):
    IDOR = "idor"
    SQLI = "sqli"
    SSRF = "ssrf"
    TRAVERSAL = "traversal"
    COMMAND_INJECTION = "command_injection"


class ProofOutcome(StrEnum):
    VERIFIED = "verified"
    NOT_TRIGGERED = "not_triggered"
    PATCH_FAILED = "patch_failed"
    REGRESSION = "regression"
    INCONCLUSIVE = "inconclusive"


class ProbeRequest(BaseModel):
    model_config = ConfigDict(frozen=True)

    method: str
    url: str
    role: str
    impact: str
    content: str | None = None


class OracleSpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: OracleKind
    surface: str
    risk_class: str
    benign_before: ProbeRequest
    malicious_before: ProbeRequest
    malicious_after: ProbeRequest
    benign_after: ProbeRequest
    benign_marker: str
    exploit_marker: str
    owner_tenant: str = ""
    attacker_tenant: str = ""
    object_id: str = ""

    @property
    def digest(self) -> str:
        payload = json.dumps(
            self.model_dump(mode="json"), sort_keys=True,
            separators=(",", ":"), ensure_ascii=False,
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class StepObservation:
    http: HttpObservation
    witness_hits: int = 0


@dataclass(frozen=True)
class ProofResult:
    outcome: ProofOutcome
    reason: str
    evidence_hash: str
    record: dict = field(default_factory=dict)

    @property
    def vulnerability_confirmed(self) -> bool | None:
        """Whether the malicious phase reproduced impact (independent of a patch)."""
        if self.outcome in {
            ProofOutcome.VERIFIED, ProofOutcome.PATCH_FAILED, ProofOutcome.REGRESSION,
        }:
            return True
        if self.outcome is ProofOutcome.NOT_TRIGGERED:
            return False
        return None

    @property
    def patch_status(self) -> str:
        """Mitigation state of the after-deployment, kept separate from confirmation."""
        return {
            ProofOutcome.VERIFIED: "effective",
            ProofOutcome.PATCH_FAILED: "failed",
            ProofOutcome.REGRESSION: "regressed",
        }.get(self.outcome, "unknown")


def _json(response: HttpObservation) -> dict | None:
    try:
        data = json.loads(response.body)
    except (ValueError, UnicodeDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _success(step: StepObservation) -> bool:
    return step.http.status_code is not None and 200 <= step.http.status_code < 300


def _record_matches(response: HttpObservation, spec: OracleSpec) -> bool:
    data = _json(response)
    return bool(data and str(data.get("id")) == spec.object_id
                and data.get("tenant") == spec.owner_tenant
                and data.get("marker") == spec.exploit_marker)


def _row_markers(response: HttpObservation) -> set[str] | None:
    data = _json(response)
    if data is None or not isinstance(data.get("rows"), list):
        return None
    rows = data["rows"]
    if not all(isinstance(row, dict) and isinstance(row.get("marker"), str) for row in rows):
        return None
    return {row["marker"] for row in rows}


_PHASES = ("benign_before", "malicious_before", "malicious_after", "benign_after")


def _redacted_step(phase: str, probe: ProbeRequest, step: StepObservation) -> dict:
    """Retrievable per-step observation with no headers, tokens or raw bodies."""
    return {
        "phase": phase,
        "method": probe.method,
        "url": probe.url,
        "role": probe.role,
        "impact": probe.impact,
        "status": step.http.status_code,
        "transport_error": step.http.transport_error,
        "body_sha256": hashlib.sha256(step.http.body).hexdigest(),
        "body_len": len(step.http.body),
        "witness_hits": step.witness_hits,
    }


def evaluate_four_phase(
    spec: OracleSpec,
    steps: tuple[StepObservation, StepObservation, StepObservation, StepObservation],
    *, target_commit: str,
) -> ProofResult:
    a, b, c, d = steps
    record = {
        "oracle": spec.kind.value,
        "oracle_digest": spec.digest,
        "target_commit": target_commit,
        "surface": spec.surface,
        "risk_class": spec.risk_class,
        "owner_tenant": spec.owner_tenant,
        "attacker_tenant": spec.attacker_tenant,
        "object_id": spec.object_id,
        "steps": [
            _redacted_step(phase, getattr(spec, phase), step)
            for phase, step in zip(_PHASES, steps, strict=True)
        ],
    }
    digest = evidence_hash(target_commit=target_commit, observation=record)

    def result(outcome: ProofOutcome, reason: str) -> ProofResult:
        return ProofResult(outcome, reason, digest, record)

    if any(step.http.transport_error or step.http.status_code is None for step in steps):
        return result(ProofOutcome.INCONCLUSIVE, "Transport or response-limit error")
    if c.http.status_code >= 500:
        return result(ProofOutcome.INCONCLUSIVE, "Patched attack caused a server error")
    if not _success(a):
        return result(ProofOutcome.INCONCLUSIVE, "Legitimate baseline failed")

    if spec.kind == OracleKind.IDOR:
        if (not spec.owner_tenant or not spec.attacker_tenant or not spec.exploit_marker
                or spec.owner_tenant == spec.attacker_tenant or not spec.object_id):
            return result(ProofOutcome.INCONCLUSIVE, "IDOR identities or object ID missing")
        if not _record_matches(a.http, spec):
            return result(ProofOutcome.INCONCLUSIVE, "Owner baseline lacks the expected object")
        exploited = _success(b) and _record_matches(b.http, spec)
        still_exploited = _success(c) and _record_matches(c.http, spec)
        benign_preserved = _success(d) and _record_matches(d.http, spec)
    elif spec.kind == OracleKind.SQLI:
        baseline = _row_markers(a.http)
        attack = _row_markers(b.http)
        after_attack = _row_markers(c.http)
        after_benign = _row_markers(d.http)
        if (baseline is None or attack is None or after_benign is None
                or (_success(c) and after_attack is None)
                or spec.benign_marker not in baseline
                or spec.exploit_marker in baseline):
            return result(ProofOutcome.INCONCLUSIVE, "SQL baseline or structured rows invalid")
        exploited = _success(b) and spec.exploit_marker in attack
        still_exploited = bool(after_attack and spec.exploit_marker in after_attack)
        benign_preserved = _success(d) and spec.benign_marker in after_benign
    elif spec.kind == OracleKind.TRAVERSAL:
        if (not spec.benign_marker or not spec.exploit_marker
                or spec.exploit_marker.encode() in a.http.body
                or spec.benign_marker.encode() not in a.http.body):
            return result(ProofOutcome.INCONCLUSIVE, "Traversal baseline marker invalid")
        exploited = spec.exploit_marker.encode() in b.http.body
        still_exploited = spec.exploit_marker.encode() in c.http.body
        benign_preserved = _success(d) and spec.benign_marker.encode() in d.http.body
    elif spec.kind in {OracleKind.SSRF, OracleKind.COMMAND_INJECTION}:
        if (a.witness_hits or d.witness_hits
                or not spec.benign_marker
                or spec.benign_marker.encode() not in a.http.body):
            return result(ProofOutcome.INCONCLUSIVE, "Legitimate request triggered side effect")
        exploited = b.witness_hits > 0
        still_exploited = c.witness_hits > 0
        benign_preserved = _success(d) and spec.benign_marker.encode() in d.http.body
    else:
        return result(ProofOutcome.INCONCLUSIVE, "Unsupported oracle")

    if not exploited:
        return result(ProofOutcome.NOT_TRIGGERED, "Malicious request did not prove impact")
    if still_exploited:
        return result(ProofOutcome.PATCH_FAILED, "Malicious impact persists after patch")
    if not benign_preserved:
        return result(ProofOutcome.REGRESSION, "Legitimate behavior changed after patch")
    return result(
        ProofOutcome.VERIFIED,
        "Impact reproduced before and blocked after; benign behavior preserved",
    )


async def run_four_phase(
    spec: OracleSpec, client: ScopedHttpClient, *, target_commit: str,
    role_headers: dict[str, dict[str, str]],
    witness_counter: Callable[[], int] | None = None,
) -> ProofResult:
    """Execute A/B/C/D in order; an independent witness counts external effects."""
    if spec.kind in {OracleKind.SSRF, OracleKind.COMMAND_INJECTION} and witness_counter is None:
        raise SecurityGateError("This oracle requires an independent witness counter")
    await client.require_target_commit(target_commit)
    if (spec.kind == OracleKind.IDOR and role_headers.get(spec.benign_before.role)
            == role_headers.get(spec.malicious_before.role)):
        raise SecurityGateError("IDOR owner and attacker credentials must differ")
    steps = []
    for request in (
        spec.benign_before, spec.malicious_before,
        spec.malicious_after, spec.benign_after,
    ):
        if request.role not in role_headers:
            raise SecurityGateError(f"No credentials supplied for role {request.role}")
        before = witness_counter() if witness_counter else 0
        if inspect.isawaitable(before):
            before = await before
        observation = await client.request(
            request.method, request.url, role=request.role, impact=request.impact,
            headers=role_headers[request.role],
            content=request.content.encode() if request.content is not None else None,
        )
        after = witness_counter() if witness_counter else 0
        if inspect.isawaitable(after):
            after = await after
        steps.append(StepObservation(observation, max(0, after - before)))
    return evaluate_four_phase(spec, tuple(steps), target_commit=target_commit)
