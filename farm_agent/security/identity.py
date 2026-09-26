"""Root-cause identity for durable candidate admission and deduplication.

Identity is bound to the pinned target SHA plus the observed actor, resource,
security boundary, source, control and sink. Title and severity are excluded, so
two distinct defects with matching titles stay distinct, and a title alone can
never merge unrelated findings. When no structural component is known, the title
is folded in so unknown fields do not merge unrelated findings.
"""

import hashlib
import json

_CLASS_HINTS = (
    ("sql_injection", ("sql injection", "sqli", "unparameterized sql")),
    ("ssrf", ("ssrf", "server-side request", "server side request")),
    ("path_traversal", ("path traversal", "traversal")),
    ("command_injection", ("command injection", "os command", "shell injection")),
    ("idor", ("idor", "insecure direct object", "cross tenant", "cross-tenant")),
)
_STRUCTURAL_KEYS = ("actor", "resource", "security_boundary", "source", "control", "sink")


def vulnerability_class(finding) -> str:
    metadata = finding.metadata if isinstance(finding.metadata, dict) else {}
    explicit = metadata.get("vulnerability_class")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip().lower()
    text = f"{finding.title} {finding.description}".lower()
    for name, needles in _CLASS_HINTS:
        if any(needle in text for needle in needles):
            return name
    return "unknown"


def _component(metadata: dict, key: str, default: str) -> str:
    value = metadata.get(key)
    if isinstance(value, str) and value.strip():
        return value.strip()
    return default


def root_cause_identity(finding, *, target_commit: str) -> str:
    """Opaque, commit-pinned root-cause identity for a finding."""
    metadata = finding.metadata if isinstance(finding.metadata, dict) else {}
    sink_default = f"{finding.file_path}:{finding.line_start or 0}"
    payload = {
        "target_commit": target_commit,
        "class": vulnerability_class(finding),
        "actor": _component(metadata, "actor", "unauthenticated"),
        "resource": _component(metadata, "resource", finding.file_path or "unknown"),
        "boundary": _component(metadata, "security_boundary", "unknown"),
        "source": _component(metadata, "source", finding.file_path or "unknown"),
        "control": _component(metadata, "control", "none"),
        "sink": _component(metadata, "sink", sink_default),
    }
    has_structure = (
        finding.line_start is not None
        or any(metadata.get(key) for key in _STRUCTURAL_KEYS)
    )
    if not has_structure:
        payload["title"] = finding.title.strip().lower()
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
