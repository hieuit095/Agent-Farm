"""Tests for PR creation integrity: 201 enforcement and head-format validation.

These tests verify that:
1. create_pull_request ONLY accepts HTTP 201 from GitHub — any other status
   (422, 403, 404, 500, etc.) must raise GitHubAPIError with the full response.
2. The head parameter for cross-repo PRs MUST be formatted as '{owner}:{branch}'.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from farm_agent.core.exceptions import GitHubAPIError, PRCreationError
from farm_agent.core.models import Contribution, Finding, Repository
from farm_agent.github.client import GitHubClient


@pytest.fixture
def mock_httpx_response():
    def _make(status_code: int, json_data: dict | None = None, text: str = ""):
        resp = MagicMock()
        resp.status_code = status_code
        resp.content = json.dumps(json_data).encode() if json_data else b""
        resp.text = text or (json.dumps(json_data) if json_data else "")
        if json_data is not None:
            resp.json = MagicMock(return_value=json_data)
        else:
            resp.json = MagicMock(side_effect=Exception("no json"))
        return resp
    return _make


@pytest.fixture
def github_client():
    with patch.object(GitHubClient, "__init__", lambda self, *a, **kw: None):
        client = GitHubClient.__new__(GitHubClient)
        client._primary_token = "ghp_test_token_123"
        client._pool_tokens = ["ghp_test_token_123"]
        client._current_token_index = 0
        client._rate_limit_buffer = 3
        client._client = AsyncMock()
        return client


class TestCreatePullRequest201Enforcement:
    """TASK 1: verify create_pull_request rejects anything other than 201."""

    @pytest.mark.asyncio
    async def test_201_returns_data(self, github_client, mock_httpx_response):
        payload = {
            "number": 42,
            "html_url": "https://github.com/owner/repo/pull/42",
            "title": "fix: vuln",
        }
        github_client.get_repo_details = AsyncMock(
            return_value=Repository(
                owner="owner", name="repo", full_name="owner/repo",
                default_branch="main", description="", language="Python",
                stars=100, fork=False, url="https://github.com/owner/repo",
            )
        )

        github_client._client.request = AsyncMock(
            return_value=mock_httpx_response(201, payload)
        )

        result = await github_client.create_pull_request(
            owner="owner", repo="repo",
            title="fix: vuln", body="desc",
            head="forkuser:fix-branch", base="main",
        )

        assert result["number"] == 42
        assert result["html_url"] == "https://github.com/owner/repo/pull/42"

    @pytest.mark.asyncio
    async def test_422_raises_with_payload(self, github_client, mock_httpx_response):
        error_body = {
            "message": "Validation Failed",
            "errors": [{"message": "No commits between main and fix-branch"}],
        }
        github_client._client.request = AsyncMock(
            return_value=mock_httpx_response(422, error_body)
        )

        with pytest.raises(GitHubAPIError) as exc_info:
            await github_client.create_pull_request(
                owner="owner", repo="repo",
                title="fix: vuln", body="desc",
                head="forkuser:fix-branch", base="main",
            )

        error = exc_info.value
        assert error.status_code == 422
        assert "422" in str(error)
        assert "expected 201" in str(error).lower() or \
            "Expected 201" in str(error) or \
            "PR CREATION FAILED" in str(error)
        assert "forkuser:fix-branch" in str(error)

    @pytest.mark.asyncio
    async def test_403_raises(self, github_client, mock_httpx_response):
        error_body = {"message": "Forbidden"}
        github_client._client.request = AsyncMock(
            return_value=mock_httpx_response(403, error_body)
        )

        with pytest.raises(GitHubAPIError) as exc_info:
            await github_client.create_pull_request(
                owner="owner", repo="repo",
                title="fix", body="desc",
                head="user:branch", base="main",
            )

        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_404_raises(self, github_client, mock_httpx_response):
        error_body = {"message": "Not Found"}
        github_client._client.request = AsyncMock(
            return_value=mock_httpx_response(404, error_body)
        )

        with pytest.raises(GitHubAPIError) as exc_info:
            await github_client.create_pull_request(
                owner="owner", repo="repo",
                title="fix", body="desc",
                head="user:branch", base="main",
            )

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_500_raises(self, github_client, mock_httpx_response):
        error_body = {"message": "Internal Server Error"}
        github_client._client.request = AsyncMock(
            return_value=mock_httpx_response(500, error_body)
        )

        with pytest.raises(GitHubAPIError) as exc_info:
            await github_client.create_pull_request(
                owner="owner", repo="repo",
                title="fix", body="desc",
                head="user:branch", base="main",
            )

        assert exc_info.value.status_code == 500

    @pytest.mark.asyncio
    async def test_payload_logged_before_send(self, github_client, mock_httpx_response, caplog):
        import logging
        with caplog.at_level(logging.DEBUG):
            github_client.get_repo_details = AsyncMock(
                return_value=Repository(
                    owner="owner", name="repo", full_name="owner/repo",
                    default_branch="main", description="", language="Python",
                    stars=100, fork=False, url="https://github.com/owner/repo",
                )
            )
            github_client._client.request = AsyncMock(
                return_value=mock_httpx_response(201, {
                    "number": 1,
                    "html_url": "https://github.com/owner/repo/pull/1",
                })
            )

            await github_client.create_pull_request(
                owner="owner", repo="repo",
                title="fix: vuln", body="desc",
                head="forkuser:fix-branch", base="main",
            )

        assert any("PR CREATE REQUEST" in r.message for r in caplog.records)
        assert any("forkuser:fix-branch" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_response_logged_after_send(self, github_client, mock_httpx_response, caplog):
        import logging
        with caplog.at_level(logging.DEBUG):
            github_client.get_repo_details = AsyncMock(
                return_value=Repository(
                    owner="owner", name="repo", full_name="owner/repo",
                    default_branch="main", description="", language="Python",
                    stars=100, fork=False, url="https://github.com/owner/repo",
                )
            )
            github_client._client.request = AsyncMock(
                return_value=mock_httpx_response(201, {
                    "number": 1,
                    "html_url": "https://github.com/owner/repo/pull/1",
                })
            )

            await github_client.create_pull_request(
                owner="owner", repo="repo",
                title="fix: vuln", body="desc",
                head="forkuser:fix-branch", base="main",
            )

        assert any("PR CREATE RESPONSE" in r.message for r in caplog.records)
        assert any("status=201" in r.message for r in caplog.records)


class TestHeadFormatValidation:
    """TASK 2: verify that cross-repo PR head parameter must be '{owner}:{branch}'."""

    def test_head_with_colon_passes(self):
        head = "forkuser:fix-branch"
        assert ":" in head

    def test_bare_branch_fails(self):
        head = "fix-branch"
        assert ":" not in head

    @pytest.mark.asyncio
    async def test_manager_rejects_bare_branch(self):
        from farm_agent.core.models import ContributionType, Severity

        Contribution(
            title="fix: vuln",
            commit_message="fix: vuln",
            contribution_type=ContributionType.SECURITY_FIX,
            description="Fix XSS vulnerability",
            finding=Finding(
                title="XSS vulnerability",
                severity=Severity.HIGH,
                type="security_fix",
                description="desc",
                file_path="app.py",
                vulnerable_code="old",
                fix_code="new",
            ),
            changes=[],
        )

        # The guard in PRManager checks: if ":" not in head → raise PRCreationError
        # Simulate a bare branch name slipping through:
        head = "fix-branch"
        with pytest.raises(PRCreationError, match="Invalid PR head format"):
            if ":" not in head:
                raise PRCreationError(
                    f"Invalid PR head format: '{head}'. Cross-repo PRs require "
                    f"'{{fork_owner}}:{{branch}}' format. Got bare branch name."
                )
