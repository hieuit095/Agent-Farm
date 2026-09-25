"""Versioned scan-local threat assumptions supplied by the program operator."""

import hashlib
import json

from pydantic import BaseModel, Field

from farm_agent.security.scope import ScanManifest


class ThreatModel(BaseModel):
    scan_id: str
    target_commit: str
    version: int = Field(default=1, ge=1)
    provenance: str
    actors: list[str]
    trust_boundaries: list[str]
    assets: list[str]
    attacker_inputs: list[str]
    attacker_stories: list[str]
    amendments: list[str] = Field(default_factory=list)

    @classmethod
    def from_manifest(cls, manifest: ScanManifest) -> "ThreatModel":
        scope = manifest.scope
        return cls(
            scan_id=manifest.scan_id, target_commit=scope.target_commit,
            provenance=scope.policy_reference, actors=scope.test_roles,
            trust_boundaries=scope.trust_boundaries, assets=scope.assets,
            attacker_inputs=scope.attacker_inputs, attacker_stories=scope.attacker_stories,
        )

    @property
    def digest(self) -> str:
        payload = json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def amended(
        self, note: str, *, provenance: str, changes: dict[str, list[str]],
    ) -> "ThreatModel":
        if not note.strip() or not provenance.strip():
            raise ValueError("Threat model amendment needs a note and provenance")
        allowed = {"actors", "trust_boundaries", "assets", "attacker_inputs", "attacker_stories"}
        if not changes or not changes.keys() <= allowed:
            raise ValueError("Threat model amendment has no valid assumption changes")
        return ThreatModel.model_validate({
            **self.model_dump(), **changes,
            "version": self.version + 1,
            "provenance": provenance,
            "amendments": [*self.amendments, note],
        })
