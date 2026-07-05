#!/usr/bin/env python3
"""Script to ingest architectural constraints from PROJECT_MAP.md into memory.db."""

import re
import sqlite3
from pathlib import Path


def ingest():
    project_root = Path(__file__).resolve().parent.parent
    db_path = project_root / "data" / "memory.db"
    project_map_path = project_root / "PROJECT_MAP.md"

    if not db_path.exists():
        # Ensure directories exist
        db_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Connecting to database at {db_path}...")
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Ensure knowledge_base table exists
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS knowledge_base (
        repo_name   TEXT NOT NULL,
        entry_type  TEXT NOT NULL,
        content     TEXT NOT NULL,
        created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(repo_name, entry_type, content)
    );
    """)
    conn.commit()

    if not project_map_path.exists():
        print(f"Error: {project_map_path} does not exist.")
        return

    print(f"Reading constraints from {project_map_path}...")
    content = project_map_path.read_text(encoding="utf-8")

    # Extract specific architectural sections:
    # 1. Standard Pipeline (Route A / Route B)
    # 2. Adaptive Concurrency & Throttling
    # 3. PR Patrol Daemon & CI Auto-Fix Loop
    # 4. Omniscient Context Engine & Subsystems

    constraints = []

    # Regex search for sections
    sections = [
        ("Standard Pipeline & Hybrid Routing", r"### 3A\. Standard Pipeline.*?(?=### 3B\.)"),
        ("Adaptive Concurrency & Throttling", r"## 4\. Adaptive Concurrency.*?(?=## 5\.)"),
        ("PR Patrol & CI Auto-Fix Loop", r"## 5\. PR Patrol.*?(?=## 6\.)"),
        ("Omniscient Context Engine", r"## 6\. Omniscient Context.*?(?=## 7\.)"),
    ]

    for title, pattern in sections:
        match = re.search(pattern, content, re.DOTALL)
        if match:
            extracted_text = match.group(0).strip()
            constraints.append(f"### {title}\n{extracted_text}")
            print(f"Extracted section: {title}")
        else:
            print(f"Warning: Could not find section matching: {title}")

    # Fallback: if no specific sections matched, ingest the whole file
    if not constraints:
        print("Warning: No sections extracted. Ingesting full PROJECT_MAP.md as context.")
        constraints.append(content)

    # Ingest constraints under 'global' and '*' repo keys for maximum compatibility
    ingested_count = 0
    for block in constraints:
        for repo_key in ("global", "*"):
            try:
                cursor.execute(
                    """
                INSERT OR REPLACE INTO knowledge_base (repo_name, entry_type, content)
                VALUES (?, 'ARCHITECTURE_CONTEXT', ?)
                """,
                    (repo_key, block),
                )
                ingested_count += 1
            except Exception as e:
                print(f"Failed to ingest block for {repo_key}: {e}")

    conn.commit()
    conn.close()

    print(
        f"Successfully ingested {ingested_count} architectural constraints into the knowledge_base!"
    )


if __name__ == "__main__":
    ingest()
