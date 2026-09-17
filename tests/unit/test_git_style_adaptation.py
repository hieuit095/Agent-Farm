"""Unit tests for Git Style Adaptation in PRManager."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from farm_agent.core.models import Contribution, ContributionType, Finding, Severity
from farm_agent.pr.manager import PRManager


@pytest.fixture
def manager():
    github = MagicMock()
    return PRManager(github=github)


@pytest.mark.asyncio
async def test_detect_repo_git_style_conventional(manager):
    manager._github._get = AsyncMock(return_value=[
        {"commit": {"message": "feat(core): add authentication helper"}},
        {"commit": {"message": "fix(db): resolve connection pool leak"}},
        {"commit": {"message": "docs: update getting started guide"}},
        {"commit": {"message": "chore(deps): bump httpx from 0.27 to 0.28"}},
    ])

    style = await manager.detect_repo_git_style("owner", "repo")
    assert style["commit_style"] == "conventional"


@pytest.mark.asyncio
async def test_detect_repo_git_style_title_case(manager):
    manager._github._get = AsyncMock(return_value=[
        {"commit": {"message": "Fix Null Pointer in User Service"}},
        {"commit": {"message": "Update Documentation for API V2"}},
        {"commit": {"message": "Add Support for PostgreSQL 16"}},
    ])

    style = await manager.detect_repo_git_style("owner", "repo")
    assert style["commit_style"] == "title_case"


@pytest.mark.asyncio
async def test_detect_repo_git_style_lowercase(manager):
    manager._github._get = AsyncMock(return_value=[
        {"commit": {"message": "fix null pointer in user service"}},
        {"commit": {"message": "update readme"}},
        {"commit": {"message": "cleanup unused imports"}},
    ])

    style = await manager.detect_repo_git_style("owner", "repo")
    assert style["commit_style"] == "lowercase"


def test_adapt_commit_message_to_conventional():
    # Input has no prefix, target style is conventional
    res = PRManager.adapt_commit_message("resolve memory leak in worker", {"commit_style": "conventional"})
    assert res.startswith("fix: resolve memory leak")

    # Input already conventional
    res2 = PRManager.adapt_commit_message("fix(worker): resolve memory leak", {"commit_style": "conventional"})
    assert res2 == "fix(worker): resolve memory leak"


def test_adapt_commit_message_to_title_case():
    # Input is conventional, target style is Title Case
    res = PRManager.adapt_commit_message("fix: resolve memory leak in worker", {"commit_style": "title_case"})
    assert res == "Resolve memory leak in worker"


def test_adapt_commit_message_to_lowercase():
    # Input is conventional or Title Case, target style is lowercase
    res = PRManager.adapt_commit_message("Fix: Resolve Memory Leak", {"commit_style": "lowercase"})
    assert res == "resolve memory leak"


def test_generate_adapted_branch_name(manager):
    finding = Finding(
        type=ContributionType.SECURITY_FIX,
        severity=Severity.HIGH,
        title="SQL Injection in auth",
        description="test",
        file_path="auth.py",
    )
    contrib = Contribution(
        finding=finding,
        contribution_type=ContributionType.SECURITY_FIX,
        title="Fix SQL Injection in auth",
        description="test",
    )

    branch_slash = manager.generate_adapted_branch_name(contrib, {"branch_style": "prefix_slash"})
    assert branch_slash.startswith("fix/security/")
    assert "sql-injection-in-auth" in branch_slash

    branch_hyphen = manager.generate_adapted_branch_name(contrib, {"branch_style": "prefix_hyphen"})
    assert branch_hyphen.startswith("fix-security-")
