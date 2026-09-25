"""Hash observations without storing target output or PoC content in SQLite."""

import hashlib
import json


def evidence_hash(*, target_commit: str, observation: dict) -> str:
    payload = json.dumps(
        {"target_commit": target_commit, "observation": observation},
        sort_keys=True, separators=(",", ":"), ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
