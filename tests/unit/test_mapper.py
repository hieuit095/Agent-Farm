"""Unit tests for RepoMapper skeleton extraction."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from farm_agent.analysis.mapper import RepoMapper


# ── Fixtures ──────────────────────────────────────────────────────────────


def _make_node(path: str, node_type: str = "blob") -> MagicMock:
    """Create a mock FileNode with path and type."""
    node = MagicMock()
    node.path = path
    node.type = node_type
    return node


# Sample Python source — MUST extract signatures, MUST NOT extract body
SAMPLE_PYTHON = '''\
import os

SECRET_KEY = "abc123"


class UserService(BaseService):
    """Manages users in the system."""

    MAX_RETRIES = 3

    def __init__(self, db):
        self._db = db
        self._cache = {}

    async def get_user(self, user_id: int) -> dict:
        """Fetch a user by ID."""
        result = await self._db.query("SELECT * FROM users WHERE id = ?", user_id)
        if not result:
            raise ValueError("User not found")
        return result

    def _validate_email(self, email: str) -> bool:
        return "@" in email and "." in email


def compute_score(items: list[int], *, multiplier: float = 1.0) -> float:
    total = sum(items)
    return total * multiplier
'''

# Internal logic strings that must NOT appear in the skeleton
PYTHON_BODY_STRINGS = [
    'self._db = db',
    'self._cache = {}',
    'await self._db.query',
    'raise ValueError("User not found")',
    '"@" in email',
    'total = sum(items)',
    'return total * multiplier',
    'SECRET_KEY = "abc123"',
]

# Sample JS source
SAMPLE_JS = '''\
class AuthController {
  constructor(authService) {
    this.authService = authService;
    this.tokenExpiry = 3600;
  }

  async login(username, password) {
    const token = await this.authService.authenticate(username, password);
    localStorage.setItem("token", token);
    return token;
  }
}

export function validateInput(data) {
  if (!data || typeof data !== "object") {
    throw new Error("Invalid input");
  }
  return true;
}

export const fetchUsers = async (page) => {
  const response = await fetch(`/api/users?page=${page}`);
  return response.json();
};
'''

JS_BODY_STRINGS = [
    'this.authService = authService',
    'this.tokenExpiry = 3600',
    'localStorage.setItem',
    'throw new Error("Invalid input")',
    'await fetch(`/api/users',
    'response.json()',
]


# ── Tests ─────────────────────────────────────────────────────────────────


class TestPythonExtraction:
    """Test Python AST-based signature extraction."""

    def test_extracts_class_and_methods(self):
        mapper = RepoMapper()
        sigs = mapper._extract_python_signatures(SAMPLE_PYTHON)
        sig_text = "\n".join(sigs)

        assert "class UserService(BaseService):" in sig_text
        assert "def __init__(self, db)" in sig_text
        assert "async def get_user(self, user_id: int) -> dict" in sig_text
        assert "def _validate_email(self, email: str) -> bool" in sig_text
        assert "def compute_score(items: list[int]" in sig_text

    def test_excludes_body_logic(self):
        mapper = RepoMapper()
        sigs = mapper._extract_python_signatures(SAMPLE_PYTHON)
        sig_text = "\n".join(sigs)

        for body_str in PYTHON_BODY_STRINGS:
            assert body_str not in sig_text, f"Body logic leaked: {body_str}"

    def test_handles_syntax_error(self):
        mapper = RepoMapper()
        sigs = mapper._extract_python_signatures("def broken(\nclass ???")
        assert sigs == []  # graceful empty, no crash


class TestJSTSExtraction:
    """Test JS/TS regex-based signature extraction."""

    def test_extracts_signatures(self):
        mapper = RepoMapper()
        sigs = mapper._extract_js_ts_signatures(SAMPLE_JS)
        sig_text = "\n".join(sigs)

        assert "class AuthController" in sig_text
        assert "validateInput" in sig_text
        assert "fetchUsers" in sig_text

    def test_excludes_body_logic(self):
        mapper = RepoMapper()
        sigs = mapper._extract_js_ts_signatures(SAMPLE_JS)
        sig_text = "\n".join(sigs)

        for body_str in JS_BODY_STRINGS:
            assert body_str not in sig_text, f"Body logic leaked: {body_str}"


class TestFileFiltering:
    """Test that non-code files are correctly excluded."""

    def test_skips_non_code_files(self):
        mapper = RepoMapper()
        assert mapper._is_code_file("README.md") is False
        assert mapper._is_code_file("package.json") is False
        assert mapper._is_code_file("yarn.lock") is False
        assert mapper._is_code_file("config.yaml") is False

    def test_includes_code_files(self):
        mapper = RepoMapper()
        assert mapper._is_code_file("main.py") is True
        assert mapper._is_code_file("app.ts") is True
        assert mapper._is_code_file("server.go") is True
        assert mapper._is_code_file("lib.rs") is True
        assert mapper._is_code_file("App.java") is True


class TestGenerateMap:
    """Test the full generate_map pipeline."""

    @pytest.mark.asyncio
    async def test_full_map_generation(self):
        mapper = RepoMapper()
        file_tree = [
            _make_node("src/main.py"),
            _make_node("README.md"),
            _make_node("src/utils.js"),
            _make_node("data", "tree"),  # directory, should be skipped
        ]

        content_map = {
            "src/main.py": SAMPLE_PYTHON,
            "src/utils.js": SAMPLE_JS,
        }

        async def mock_fetch(path: str) -> str:
            return content_map.get(path, "")

        result = await mapper.generate_map(file_tree, mock_fetch)

        # Should include Python file
        assert "src/main.py" in result
        assert "class UserService" in result
        assert "def compute_score" in result

        # Should include JS file
        assert "src/utils.js" in result
        assert "class AuthController" in result

        # Should NOT include README
        assert "README.md" not in result

    @pytest.mark.asyncio
    async def test_caps_at_max_files(self):
        """Verify that more than MAX_FILES files are capped."""
        from farm_agent.analysis.mapper import MAX_FILES

        mapper = RepoMapper()
        # Create 600 fake file nodes
        file_tree = [_make_node(f"src/file_{i}.py") for i in range(600)]

        async def mock_fetch(path: str) -> str:
            return "def hello(): pass"

        result = await mapper.generate_map(file_tree, mock_fetch)

        # Count how many files appear in output
        file_count = result.count("src/file_")
        assert file_count <= MAX_FILES

    @pytest.mark.asyncio
    async def test_survives_fetch_failure(self):
        """If fetch_content raises, the file is skipped gracefully."""
        mapper = RepoMapper()
        file_tree = [_make_node("src/broken.py")]

        async def failing_fetch(path: str) -> str:
            raise ConnectionError("Network error")

        result = await mapper.generate_map(file_tree, failing_fetch)
        # Should not crash, just produce empty or minimal output
        assert isinstance(result, str)
