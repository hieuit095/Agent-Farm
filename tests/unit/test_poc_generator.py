import os
import sys
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure chromadb is mocked out
mock_chromadb = MagicMock()
sys.modules['chromadb'] = mock_chromadb

# Ensure docker is mocked out
mock_docker = MagicMock()
mock_docker_errors = MagicMock()
mock_docker_models = MagicMock()

class MockDockerException(Exception): pass
mock_docker_errors.APIError = MockDockerException
mock_docker_errors.ImageNotFound = MockDockerException
mock_docker_errors.NotFound = MockDockerException

sys.modules['docker'] = mock_docker
sys.modules['docker.errors'] = mock_docker_errors
sys.modules['docker.models.containers'] = mock_docker_models

from farm_agent.core.models import ContributionType, Finding, ImpactLevel, Severity
from farm_agent.core.sandbox import DockerSandbox
from farm_agent.generator.poc import PoCGenerator


@pytest.fixture
def mock_llm():
    llm = MagicMock()
    llm.complete = AsyncMock()
    return llm

@pytest.fixture
def finding():
    return Finding(
        type=ContributionType.SECURITY_FIX,
        severity=Severity.HIGH,
        title="SQL Injection",
        description="Vulnerability description",
        file_path="src/main.py",
        impact_level=ImpactLevel.HIGH,
        metadata={"module_dependencies": {"imports": ["auth.py"], "calls": ["db.py"], "dependents": []}}
    )

@pytest.mark.asyncio
async def test_generate_poc_success(mock_llm, finding):
    # Setup mock LLM response
    mock_llm.complete.return_value = """
    ```json
    {
        "filename": "poc.py",
        "content": "print('exploit')",
        "command": "python poc.py"
    }
    ```
    """
    generator = PoCGenerator(mock_llm)

    filename, content, command = await generator.generate_poc(finding, "def get_user(): pass")

    assert filename == "poc.py"
    assert content == "print('exploit')"
    assert command == "python poc.py"
    mock_llm.complete.assert_called_once()

@pytest.mark.asyncio
async def test_generate_poc_failure_fallback(mock_llm, finding):
    # Setup mock LLM response that fails to output valid JSON
    mock_llm.complete.return_value = "invalid response"
    generator = PoCGenerator(mock_llm)

    filename, content, command = await generator.generate_poc(finding, "def get_user(): pass")

    assert filename is None
    assert content is None
    assert command is None

@pytest.mark.asyncio
async def test_evaluate_poc_result_success(mock_llm, finding):
    # Setup mock LLM response for validation result
    mock_llm.complete.return_value = """
    ```json
    {
        "is_triggered": true,
        "reason": "AssertionError: SQL Injection successful"
    }
    ```
    """
    generator = PoCGenerator(mock_llm)

    sandbox_output = {
        "exit_code": 1,
        "stdout": "Running exploit...",
        "stderr": "AssertionError: SQL Injection successful",
        "timed_out": False
    }

    is_triggered, reason = await generator.evaluate_poc_result(finding, "print('exploit')", sandbox_output)

    assert is_triggered is True
    assert reason == "AssertionError: SQL Injection successful"
    mock_llm.complete.assert_called_once()

@pytest.mark.asyncio
async def test_evaluate_poc_result_fallback(mock_llm, finding):
    # Setup mock LLM response that fails to output valid JSON
    mock_llm.complete.return_value = "invalid response"
    generator = PoCGenerator(mock_llm)

    sandbox_output = {
        "exit_code": 1,
        "stdout": "Running exploit...",
        "stderr": "AssertionError: SQL Injection successful",
        "timed_out": False
    }

    is_triggered, reason = await generator.evaluate_poc_result(finding, "print('exploit')", sandbox_output)

    assert is_triggered is False
    assert "Failed to parse evaluation response" in reason

@pytest.mark.asyncio
async def test_verify_vulnerability_with_poc():
    # Setup temporary directory to act as repo path
    with tempfile.TemporaryDirectory() as temp_dir:
        # Mock DockerSandbox to avoid docker daemon dependencies
        with patch("farm_agent.core.sandbox.DockerSandbox.__init__", return_value=None):
            sandbox = DockerSandbox()

            # Setup mock execution result
            mock_result = {
                "exit_code": 1,
                "stdout": "Success",
                "stderr": "Error",
                "timed_out": False
            }
            sandbox.run_in_sandbox = AsyncMock(return_value=mock_result)

            poc_filename = "test_poc.py"
            poc_content = "import os\nprint('hello')"
            run_command = "python test_poc.py"

            # Before calling, file should not exist
            assert not os.path.exists(os.path.join(temp_dir, poc_filename))

            # Call verification
            result = await sandbox.verify_vulnerability_with_poc(
                repo_path=temp_dir,
                poc_filename=poc_filename,
                poc_content=poc_content,
                run_command=run_command,
                timeout=10
            )

            # Assert execution attributes returned correctly
            assert result["exit_code"] == 1
            assert result["stdout"] == "Success"
            assert result["stderr"] == "Error"
            assert result["timed_out"] is False

            # Assert file was cleaned up and is no longer present
            assert not os.path.exists(os.path.join(temp_dir, poc_filename))

            # Assert run_in_sandbox was called with correct command
            sandbox.run_in_sandbox.assert_called_once_with(
                repo_path=temp_dir,
                command=run_command,
                timeout=10
            )
