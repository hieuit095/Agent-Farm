"""Content-addressed canonical oracle artifacts outside patch workspaces."""

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

from farm_agent.security.oracles import OracleSpec
from farm_agent.security.state import SecurityGateError


@dataclass(frozen=True)
class ArtifactRef:
    path: Path
    digest: str


class ArtifactStore:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, spec: OracleSpec) -> ArtifactRef:
        data = json.dumps(
            spec.model_dump(mode="json"), sort_keys=True,
            separators=(",", ":"), ensure_ascii=False,
        ).encode("utf-8")
        digest = hashlib.sha256(data).hexdigest()
        path = self.root / f"{digest}.json"
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o444)
        except FileExistsError:
            ref = ArtifactRef(path, digest)
            self.load(ref)
            return ref
        try:
            with os.fdopen(descriptor, "wb") as output:
                output.write(data)
                output.flush()
                os.fsync(output.fileno())
            path.chmod(0o444)
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return ArtifactRef(path, digest)

    def load(self, ref: ArtifactRef) -> OracleSpec:
        if (ref.path.resolve().parent != self.root
                or ref.path.name != f"{ref.digest}.json"):
            raise SecurityGateError("Oracle artifact is outside its protected store")
        try:
            data = ref.path.read_bytes()
        except OSError as exc:
            raise SecurityGateError("Canonical oracle artifact is missing") from exc
        if hashlib.sha256(data).hexdigest() != ref.digest:
            raise SecurityGateError("Canonical oracle artifact hash changed")
        try:
            return OracleSpec.model_validate_json(data)
        except Exception as exc:
            raise SecurityGateError("Canonical oracle artifact is invalid") from exc
