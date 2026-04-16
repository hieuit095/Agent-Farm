"""Tests for JsonTargetDiscovery, DatabaseTargetDiscovery, and crash-safe circular target rotation."""

import json
from datetime import UTC, datetime

import pytest

from farm_agent.core.models import TargetRepoEntry
from farm_agent.github.discovery import JsonTargetDiscovery, DatabaseTargetDiscovery
from farm_agent.orchestrator.memory import Memory

@pytest.fixture
def sample_entries():
    return [
        {
            "entry_type": "repo",
            "repo_url": "https://github.com/owner/repo1",
            "language": "Python",
            "status": "PENDING",
            "scanned_at": "2026-04-01T10:00:00Z",
        },
        {
            "entry_type": "repo",
            "repo_url": "https://github.com/owner/repo2",
            "language": "Go",
            "status": "COMPLETED_NO_VULN",
            "scanned_at": "2026-04-05T12:00:00Z",
        },
        {
            "entry_type": "repo",
            "repo_url": "https://github.com/owner/repo3",
            "language": "Rust",
            "status": "PENDING",
            "scanned_at": None,
        },
    ]


@pytest.fixture
def json_file(sample_entries, tmp_path):
    path = tmp_path / "target_repo.json"
    path.write_text(json.dumps(sample_entries), encoding="utf-8")
    return str(path)


class TestJsonTargetDiscovery:
    def test_get_next_target_oldest_first(self, json_file):
        discovery = JsonTargetDiscovery(json_path=json_file)
        target = discovery.get_next_target()
        assert target is not None
        assert target.repo_url == "https://github.com/owner/repo3"

    def test_get_next_target_sorted_by_scanned_at(self, json_file):
        discovery = JsonTargetDiscovery(json_path=json_file)
        target = discovery.get_next_target()
        assert target.repo_url == "https://github.com/owner/repo3"

        discovery.mark_scanned("https://github.com/owner/repo3")
        target = discovery.get_next_target()
        assert target.repo_url == "https://github.com/owner/repo1"

    def test_mark_scanned_updates_timestamp(self, json_file):
        discovery = JsonTargetDiscovery(json_path=json_file)
        before = datetime.now(UTC)
        discovery.mark_scanned("https://github.com/owner/repo1")
        after = datetime.now(UTC)

        entries = discovery._load_entries()
        repo1 = next(e for e in entries if e.repo_url == "https://github.com/owner/repo1")
        assert before <= repo1.scanned_at <= after

    def test_mark_scanned_persists_to_file(self, json_file):
        discovery = JsonTargetDiscovery(json_path=json_file)
        discovery.mark_scanned("https://github.com/owner/repo2")

        discovery2 = JsonTargetDiscovery(json_path=json_file)
        target = discovery2.get_next_target()
        assert target.repo_url == "https://github.com/owner/repo3"

    def test_crash_safe_rotation(self, json_file):
        discovery = JsonTargetDiscovery(json_path=json_file)
        target = discovery.get_next_target()
        assert target.repo_url == "https://github.com/owner/repo3"

        discovery.mark_scanned(target.repo_url)

        discovery2 = JsonTargetDiscovery(json_path=json_file)
        next_target = discovery2.get_next_target()
        assert next_target.repo_url == "https://github.com/owner/repo1"

    def test_no_status_filtering(self, json_file):
        discovery = JsonTargetDiscovery(json_path=json_file)
        target = discovery.get_next_target()
        assert target.repo_url == "https://github.com/owner/repo3"
        discovery.mark_scanned(target.repo_url)

        target = discovery.get_next_target()
        assert target.repo_url == "https://github.com/owner/repo1"
        discovery.mark_scanned(target.repo_url)

        target = discovery.get_next_target()
        assert target.repo_url == "https://github.com/owner/repo2"

    def test_missing_file_returns_none(self, tmp_path):
        discovery = JsonTargetDiscovery(json_path=str(tmp_path / "nonexistent.json"))
        assert discovery.get_next_target() is None

    def test_empty_file_returns_none(self, tmp_path):
        path = tmp_path / "target_repo.json"
        path.write_text("[]", encoding="utf-8")
        discovery = JsonTargetDiscovery(json_path=str(path))
        assert discovery.get_next_target() is None

    def test_atomic_write_no_partial_corruption(self, json_file):
        discovery = JsonTargetDiscovery(json_path=json_file)
        discovery.mark_scanned("https://github.com/owner/repo3")

        from pathlib import Path

        content = Path(json_file).read_text(encoding="utf-8")
        data = json.loads(content)
        assert len(data) == 3

        tmp_path = Path(json_file).with_suffix(".tmp")
        assert not tmp_path.exists()

    def test_round_robin_full_cycle(self, json_file):
        discovery = JsonTargetDiscovery(json_path=json_file)

        urls = []
        for _ in range(3):
            target = discovery.get_next_target()
            urls.append(target.repo_url)
            discovery.mark_scanned(target.repo_url)

        assert len(set(urls)) == 3

        target = discovery.get_next_target()
        assert target.repo_url in urls

    def test_target_repo_entry_model_defaults(self):
        entry = TargetRepoEntry(repo_url="https://github.com/test/repo")
        assert entry.entry_type == "repo"
        assert entry.status == "PENDING"
        assert entry.scanned_at is None
        assert entry.stars == 0
        assert entry.diamond_target is False
        assert entry.language is None


class TestDatabaseTargetDiscovery:
    """Tests for the SQLite-backed DatabaseTargetDiscovery."""

    @pytest.fixture
    async def memory_db(self, tmp_path):
        db_path = str(tmp_path / "test_memory.db")
        mem = Memory(db_path)
        await mem.init()
        yield mem
        await mem.close()

    @pytest.mark.asyncio
    async def test_seed_from_json(self, json_file, memory_db):
        disc = DatabaseTargetDiscovery(memory=memory_db)
        inserted = await disc.initialize(json_path=json_file)
        assert inserted == 3

    @pytest.mark.asyncio
    async def test_get_next_target_nulls_first(self, json_file, memory_db):
        disc = DatabaseTargetDiscovery(memory=memory_db)
        await disc.initialize(json_path=json_file)
        target = await disc.get_next_target()
        assert target is not None
        assert target.repo_url == "https://github.com/owner/repo3"

    @pytest.mark.asyncio
    async def test_mark_scanned_updates_timestamp(self, json_file, memory_db):
        disc = DatabaseTargetDiscovery(memory=memory_db)
        await disc.initialize(json_path=json_file)

        target = await disc.get_next_target()
        assert target.repo_url == "https://github.com/owner/repo3"

        await disc.mark_scanned(target.repo_url)

        next_target = await disc.get_next_target()
        assert next_target is not None
        assert next_target.repo_url == "https://github.com/owner/repo1"

    @pytest.mark.asyncio
    async def test_mark_status_no_timestamp(self, json_file, memory_db):
        disc = DatabaseTargetDiscovery(memory=memory_db)
        await disc.initialize(json_path=json_file)

        target = await disc.get_next_target()
        assert target.repo_url == "https://github.com/owner/repo3"

        await disc.mark_status(target.repo_url, "COMPLETED_NO_VULN")

        row = await memory_db._db.execute(
            "SELECT status FROM target_repos WHERE repo_url = ?",
            (target.repo_url,),
        )
        result = await row.fetchone()
        assert result[0] == "COMPLETED_NO_VULN"

    @pytest.mark.asyncio
    async def test_crash_safe_rotation(self, json_file, memory_db):
        disc = DatabaseTargetDiscovery(memory=memory_db)
        await disc.initialize(json_path=json_file)

        target = await disc.get_next_target()
        assert target.repo_url == "https://github.com/owner/repo3"

        await disc.mark_scanned(target.repo_url)

        disc2 = DatabaseTargetDiscovery(memory=memory_db)
        next_target = await disc2.get_next_target()
        assert next_target.repo_url == "https://github.com/owner/repo1"

    @pytest.mark.asyncio
    async def test_seed_idempotent(self, json_file, memory_db):
        disc = DatabaseTargetDiscovery(memory=memory_db)
        inserted1 = await disc.initialize(json_path=json_file)
        assert inserted1 == 3

        inserted2 = await disc.initialize(json_path=json_file)
        assert inserted2 == 0

    @pytest.mark.asyncio
    async def test_empty_db_returns_none(self, memory_db):
        disc = DatabaseTargetDiscovery(memory=memory_db)
        target = await disc.get_next_target()
        assert target is None

    @pytest.mark.asyncio
    async def test_missing_json_file_seed(self, tmp_path, memory_db):
        disc = DatabaseTargetDiscovery(memory=memory_db)
        inserted = await disc.initialize(json_path=str(tmp_path / "nonexistent.json"))
        assert inserted == 0
        target = await disc.get_next_target()
        assert target is None
