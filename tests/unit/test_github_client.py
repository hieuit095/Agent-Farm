"""Tests for GitHub API client."""

from unittest.mock import AsyncMock

import pytest

from farm_agent.core.exceptions import GitHubAPIError
from farm_agent.github.client import GitHubClient


@pytest.fixture
def client():
    c = GitHubClient(token="ghp_test_token")
    yield c


class TestParseRepo:
    def test_parse_full_repo(self):
        data = {
            "owner": {"login": "testowner"},
            "name": "testrepo",
            "full_name": "testowner/testrepo",
            "description": "A test repo",
            "language": "Python",
            "stargazers_count": 500,
            "forks_count": 50,
            "open_issues_count": 10,
            "topics": ["python"],
            "default_branch": "main",
            "html_url": "https://github.com/testowner/testrepo",
            "clone_url": "https://github.com/testowner/testrepo.git",
            "license": {"spdx_id": "MIT"},
        }
        repo = GitHubClient._parse_repo(data)
        assert repo.owner == "testowner"
        assert repo.name == "testrepo"
        assert repo.stars == 500
        assert repo.has_license is True

    def test_parse_minimal_repo(self):
        data = {
            "owner": {},
            "name": "x",
            "full_name": "a/x",
        }
        repo = GitHubClient._parse_repo(data)
        assert repo.owner == ""
        assert repo.stars == 0
        assert repo.has_license is False

    def test_parse_no_license(self):
        data = {
            "owner": {"login": "x"},
            "name": "y",
            "full_name": "x/y",
            "license": None,
        }
        repo = GitHubClient._parse_repo(data)
        assert repo.has_license is False


class TestClientHeaders:
    def test_auth_header(self, client):
        headers = client._client.headers
        assert "authorization" in {k.lower() for k in headers.keys()}


class TestContributingGuide:
    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self, client):
        client.get_file_content = AsyncMock(
            side_effect=GitHubAPIError("Not found", status_code=404)
        )
        result = await client.get_contributing_guide("owner", "repo")
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_content_when_found(self, client):
        client.get_file_content = AsyncMock(return_value="# Contributing\nPlease read...")
        result = await client.get_contributing_guide("owner", "repo")
        assert "Contributing" in result


class TestGetFileContent:
    @pytest.mark.asyncio
    async def test_passes_ref_when_requested(self, client):
        client._get = AsyncMock(
            return_value={
                "encoding": "base64",
                "content": "aGVsbG8=",
            }
        )

        result = await client.get_file_content("owner", "repo", "src/app.py", ref="feature-branch")

        assert result == "hello"
        client._get.assert_awaited_once_with(
            "/repos/owner/repo/contents/src/app.py",
            params={"ref": "feature-branch"},
        )
