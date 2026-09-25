"""Explicit, commit-pinned program scope for security scans and publication."""

import fnmatch
import hashlib
import json
import re
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator, model_validator

from farm_agent.security.state import SecurityGateError

_SHA = re.compile(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}")
_REPO = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")


class ProgramScope(BaseModel):
    """Operator supplied authorization; an absent entry grants no publication rights."""

    program_id: str = Field(min_length=1)
    repo: str
    target_commit: str
    allowed_origins: list[str] = Field(default_factory=list)
    excluded_endpoints: list[str] = Field(default_factory=list)
    max_requests: int = Field(default=0, ge=0)
    test_roles: list[str] = Field(default_factory=list)
    allowed_impacts: list[str] = Field(default_factory=list)
    allow_live_testing: bool = False
    allow_public_pr: bool = False
    allow_private_disclosure: bool = False
    allow_local_report: bool = False
    policy_reference: str = Field(min_length=1)
    surfaces: list[str] = Field(default_factory=list)
    risk_classes: list[str] = Field(default_factory=list)
    trust_boundaries: list[str] = Field(default_factory=list)
    assets: list[str] = Field(default_factory=list)
    attacker_inputs: list[str] = Field(default_factory=list)
    attacker_stories: list[str] = Field(default_factory=list)

    @field_validator("repo")
    @classmethod
    def valid_repo(cls, value: str) -> str:
        if not _REPO.fullmatch(value):
            raise ValueError("repo must be an exact owner/name")
        return value

    @field_validator("target_commit")
    @classmethod
    def valid_sha(cls, value: str) -> str:
        if not _SHA.fullmatch(value):
            raise ValueError("target_commit must be a full SHA")
        return value.lower()

    @field_validator("allowed_origins")
    @classmethod
    def valid_origins(cls, values: list[str]) -> list[str]:
        for origin in values:
            parsed = urlsplit(origin)
            if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                    or parsed.username or parsed.password or parsed.path
                    or parsed.query or parsed.fragment
                    or origin != f"{parsed.scheme}://{parsed.netloc}"):
                raise ValueError(f"Invalid exact origin: {origin}")
        if len(values) != len(set(values)):
            raise ValueError("Duplicate allowed origin")
        return values

    @model_validator(mode="after")
    def live_requires_limits(self):
        if self.allow_live_testing and (
            not self.allowed_origins or not self.max_requests or not self.test_roles
            or not self.allowed_impacts or not self.surfaces or not self.risk_classes
            or not self.trust_boundaries or not self.assets
            or not self.attacker_inputs or not self.attacker_stories
        ):
            raise ValueError("Live testing requires explicit scope, limits and threat assumptions")
        return self


class ScanManifest(BaseModel):
    scan_id: str
    scope: ProgramScope
    mode: str = "offline"

    @model_validator(mode="after")
    def valid_mode(self):
        if self.mode not in {"offline", "live"}:
            raise ValueError("mode must be offline or live")
        if self.mode == "live" and not self.scope.allow_live_testing:
            raise ValueError("Program does not permit live testing")
        return self

    @property
    def digest(self) -> str:
        payload = json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def require_publication(self, channel: str) -> None:
        allowed = {
            "public_pr": self.scope.allow_public_pr,
            "private_disclosure": self.scope.allow_private_disclosure,
            "local_report": self.scope.allow_local_report,
        }
        if channel not in allowed or not allowed[channel]:
            raise SecurityGateError(f"Publication channel {channel} is outside program scope")

    def require_request(self, url: str, role: str, impact: str, method: str = "GET") -> None:
        if self.mode != "live":
            raise SecurityGateError("Live requests require an authorized live manifest")
        parsed = urlsplit(url)
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                or parsed.username or parsed.password or parsed.fragment
                or f"{parsed.scheme}://{parsed.netloc}" not in self.scope.allowed_origins):
            raise SecurityGateError("Request target is outside the exact origin allowlist")
        if role not in self.scope.test_roles or impact not in self.scope.allowed_impacts:
            raise SecurityGateError("Role or impact is outside program scope")
        if impact == "read_only" and method.upper() not in {"GET", "HEAD", "OPTIONS"}:
            raise SecurityGateError("Write method is not allowed under read-only impact")
        path = parsed.path or "/"
        if any(fnmatch.fnmatchcase(path, pattern) for pattern in self.scope.excluded_endpoints):
            raise SecurityGateError("Endpoint is excluded by program policy")


def matching_program(
    repo: str, target_commit: str, programs: list[ProgramScope],
) -> ProgramScope | None:
    """The exact program authorizing this repository and commit, if any."""
    matches = [p for p in programs if p.repo == repo and p.target_commit == target_commit]
    if len(matches) > 1:
        raise SecurityGateError("Ambiguous program scope for repository and commit")
    return matches[0] if matches else None


def manifest_for_scan(
    scan_id: str, repo: str, target_commit: str, programs: list[ProgramScope],
    *, mode: str = "offline",
) -> ScanManifest | None:
    scope = matching_program(repo, target_commit, programs)
    return ScanManifest(scan_id=scan_id, scope=scope, mode=mode) if scope else None
