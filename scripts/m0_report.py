"""Print metadata-only scan gate counts from the local M0 SQLite ledger."""

import argparse
import json
import sqlite3
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("db", nargs="?", type=Path, default=Path("data/memory.db"))
    parser.add_argument("--scan-id")
    args = parser.parse_args()

    uri = f"file:{args.db.resolve().as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as db:
        db.row_factory = sqlite3.Row
        where = "WHERE scan_id = ?" if args.scan_id else ""
        params = (args.scan_id,) if args.scan_id else ()
        rows = db.execute(
            "SELECT scan_id, repo, pipeline, stage, outcome, reason_code, "
            "SUM(count) AS items, MAX(duration_ms) AS duration_ms, "
            "SUM(input_tokens) AS input_tokens, SUM(output_tokens) AS output_tokens, "
            "SUM(cost_usd) AS cost_usd "
            f"FROM scan_events {where} "
            "GROUP BY scan_id, repo, pipeline, stage, outcome, reason_code "
            "ORDER BY scan_id, stage, outcome",
            params,
        ).fetchall()
    print(json.dumps([dict(row) for row in rows], indent=2))


if __name__ == "__main__":
    main()
