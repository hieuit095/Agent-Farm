import pytest
import sys
import os
import tempfile
from unittest.mock import MagicMock, AsyncMock, patch

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

from farm_agent.core.models import Finding, ContributionType, Severity, ImpactLevel, Contribution, FileChange, RepoContext, Repository
from farm_agent.generator.reviewer import ReviewerAgent
from farm_agent.core.sandbox import DockerSandbox

@pytest.fixture
def mock_llm():
    llm = MagicMock()
    llm.complete = AsyncMock(return_value='{"decision": "APPROVE", "critique": ""}')
    return llm

@pytest.fixture
def repository():
    return Repository(
        owner="owner",
        name="repo",
        full_name="owner/repo",
        clone_url="https://github.com/owner/repo.git"
    )

@pytest.fixture
def contribution(repository):
    finding = Finding(
        type=ContributionType.SECURITY_FIX,
        severity=Severity.HIGH,
        title="SQL Injection",
        description="Vulnerability description",
        file_path="src/main.py",
        impact_level=ImpactLevel.HIGH,
        metadata={"module_dependencies": {"imports": ["auth.py"], "calls": ["db.py"], "dependents": ["src/server.py"]}}
    )
    return Contribution(
        finding=finding,
        contribution_type=ContributionType.SECURITY_FIX,
        title="Fix SQL Injection",
        description="Fixes injection in main.py",
        changes=[FileChange(path="src/main.py", original_content="query", new_content="query_safe")],
        commit_message="fix injection"
    )

@pytest.mark.asyncio
async def test_reviewer_agent_injects_blast_radius(mock_llm, contribution, repository):
    agent = ReviewerAgent(mock_llm)
    context = RepoContext(repo=repository, file_tree=[], relevant_files={})
    
    # Run review
    result = await agent.review(contribution, context)
    
    assert result["decision"] == "APPROVE"
    
    # Assert LLM was called and prompt contains the dependent modules
    mock_llm.complete.assert_called_once()
    called_prompt = mock_llm.complete.call_args[0][0]
    assert "Downstream Dependent Modules (Blast Radius)" in called_prompt
    assert "src/server.py" in called_prompt

@pytest.mark.asyncio
async def test_run_native_test_suite_no_tests():
    with tempfile.TemporaryDirectory() as temp_dir:
        with patch("farm_agent.core.sandbox.DockerSandbox.__init__", return_value=None):
            sandbox = DockerSandbox()
            
            # Executing on an empty directory should trigger tests_missing
            result = await sandbox.run_native_test_suite(repo_path=temp_dir, language="python")
            
            assert result["status"] == "tests_missing"
            assert result["exit_code"] == 0

@pytest.mark.asyncio
async def test_run_native_test_suite_success():
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a mock test file to trigger test detection
        test_file = os.path.join(temp_dir, "test_main.py")
        with open(test_file, "w") as f:
            f.write("def test_ok(): pass")
            
        with patch("farm_agent.core.sandbox.DockerSandbox.__init__", return_value=None):
            sandbox = DockerSandbox()
            
            mock_result = {
                "exit_code": 0,
                "stdout": "tests passed",
                "stderr": "",
                "timed_out": False
            }
            sandbox.run_in_sandbox = AsyncMock(return_value=mock_result)
            
            result = await sandbox.run_native_test_suite(repo_path=temp_dir, language="python")
            
            assert result["status"] == "success"
            assert result["exit_code"] == 0
            sandbox.run_in_sandbox.assert_called_once()

@pytest.mark.asyncio
async def test_run_native_test_suite_failed():
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a mock test folder to trigger test detection
        os.makedirs(os.path.join(temp_dir, "tests"))
            
        with patch("farm_agent.core.sandbox.DockerSandbox.__init__", return_value=None):
            sandbox = DockerSandbox()
            
            mock_result = {
                "exit_code": 1,
                "stdout": "",
                "stderr": "test failure",
                "timed_out": False
            }
            sandbox.run_in_sandbox = AsyncMock(return_value=mock_result)
            
            result = await sandbox.run_native_test_suite(repo_path=temp_dir, language="python")
            
            assert result["status"] == "failed"
            assert result["exit_code"] == 1
            sandbox.run_in_sandbox.assert_called_once()
