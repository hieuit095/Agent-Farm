"""Unit tests for Differential PoC Verification (2-pass validation)."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from farm_agent.core.models import ContributionType, Finding, ImpactLevel, Severity
from farm_agent.generator.poc import PoCGenerator


@pytest.fixture
def finding():
    return Finding(
        type=ContributionType.SECURITY_FIX,
        severity=Severity.HIGH,
        title="SQL Injection",
        description="SQL injection in login parameter",
        file_path="src/login.py",
        impact_level=ImpactLevel.HIGH,
    )


@pytest.mark.asyncio
async def test_differential_poc_success_both_passes(finding):
    llm = MagicMock()
    # LLM evaluator says: Pass 1 is triggered
    llm.complete = AsyncMock(return_value="```json\n{\"is_triggered\": true, \"reason\": \"AssertionError: leaked\"}\n```")

    generator = PoCGenerator(llm)

    sandbox = MagicMock()
    # Mock pass 1: exit code 1 (crash)
    # Mock pass 2: exit code 0 (clean)
    sandbox.verify_vulnerability_with_poc = AsyncMock(side_effect=[
        {"exit_code": 1, "stdout": "", "stderr": "AssertionError: leaked", "timed_out": False},
        {"exit_code": 0, "stdout": "Clean", "stderr": "", "timed_out": False},
    ])

    patch_fn_called = False

    def apply_patch():
        nonlocal patch_fn_called
        patch_fn_called = True
        return True

    verified, details = await generator.verify_differential_poc(
        finding=finding,
        repo_path="/tmp/repo",
        poc_filename="test_poc.py",
        poc_content="assert False",
        poc_command="python test_poc.py",
        sandbox=sandbox,
        apply_patch_func=apply_patch,
    )

    assert verified is True
    assert patch_fn_called is True
    assert "Differential Verification Passed" in details
    assert sandbox.verify_vulnerability_with_poc.call_count == 2


@pytest.mark.asyncio
async def test_differential_poc_fails_pass1_untriggered(finding):
    llm = MagicMock()
    # LLM evaluator says: Not triggered
    llm.complete = AsyncMock(return_value="```json\n{\"is_triggered\": false, \"reason\": \"Exit code 0, no exploit\"}\n```")

    generator = PoCGenerator(llm)

    sandbox = MagicMock()
    # Pass 1 exits 0 (did not reproduce bug -> False Positive)
    sandbox.verify_vulnerability_with_poc = AsyncMock(return_value={
        "exit_code": 0, "stdout": "No error", "stderr": "", "timed_out": False
    })

    verified, details = await generator.verify_differential_poc(
        finding=finding,
        repo_path="/tmp/repo",
        poc_filename="test_poc.py",
        poc_content="assert False",
        poc_command="python test_poc.py",
        sandbox=sandbox,
        apply_patch_func=MagicMock(return_value=True),
    )

    assert verified is False
    assert "Pass 1 Failed" in details
    assert "False Positive" in details
    # Pass 2 should never run if Pass 1 fails!
    assert sandbox.verify_vulnerability_with_poc.call_count == 1


@pytest.mark.asyncio
async def test_differential_poc_fails_pass2_patch_fails(finding):
    llm = MagicMock()
    llm.complete = AsyncMock(return_value="```json\n{\"is_triggered\": true, \"reason\": \"AssertionError\"}\n```")

    generator = PoCGenerator(llm)

    sandbox = MagicMock()
    # Pass 1: crash (exit 1)
    # Pass 2: still crashes after patch (exit 1)
    sandbox.verify_vulnerability_with_poc = AsyncMock(side_effect=[
        {"exit_code": 1, "stdout": "", "stderr": "AssertionError", "timed_out": False},
        {"exit_code": 1, "stdout": "", "stderr": "AssertionError still present", "timed_out": False},
    ])

    verified, details = await generator.verify_differential_poc(
        finding=finding,
        repo_path="/tmp/repo",
        poc_filename="test_poc.py",
        poc_content="assert False",
        poc_command="python test_poc.py",
        sandbox=sandbox,
        apply_patch_func=lambda: True,
    )

    assert verified is False
    assert "Pass 2 Failed" in details
    assert sandbox.verify_vulnerability_with_poc.call_count == 2
