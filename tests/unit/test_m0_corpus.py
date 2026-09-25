"""The corpus oracle must distinguish each vulnerable/fixed pair offline."""

import importlib.util
import json
from pathlib import Path

CORPUS = Path(__file__).resolve().parents[1] / "corpus"


def test_m0_corpus_ground_truth():
    manifest = json.loads((CORPUS / "manifest.json").read_text(encoding="utf-8"))
    spec = importlib.util.spec_from_file_location("m0_targets", CORPUS / "targets.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert {pair["class"] for pair in manifest["pairs"]} == {
        "IDOR", "SQLi", "SSRF", "Traversal"
    }
    assert module.authz_vulnerable("alice", "bob") == "bob-private"
    assert module.authz_fixed("alice", "bob") is None
    assert module.authz_fixed("bob", "bob") == "bob-private"

    payload = "' OR '1'='1"
    assert payload in module.sqli_vulnerable(payload)
    query, params = module.sqli_fixed(payload)
    assert payload not in query and params == (payload,)

    internal = "http://127.0.0.1/admin"
    assert module.ssrf_vulnerable(internal)
    assert not module.ssrf_fixed(internal)
    assert module.ssrf_fixed("https://public.example/resource")

    traversal = "../private.txt"
    assert module.traversal_vulnerable(traversal)
    assert not module.traversal_fixed(traversal)
    assert module.traversal_fixed("notes/public.txt")

    assert {case["expected"] for case in manifest["control_cases"]} == {
        "no_finding", "two_candidates", "proof_gap"
    }
