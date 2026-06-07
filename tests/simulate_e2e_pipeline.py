# ruff: noqa
"""
Ultimate End-to-End System Test & Protocol Verification
Phase 3 & 4: Dynamic End-to-End Mocked Simulations
"""

import asyncio
import json
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from farm_agent.core.config import FarmAgentConfig
from farm_agent.core.models import (
    Repository,
    Finding,
    Contribution,
    ImpactLevel,
    ContributionType,
    Severity,
    FileChange,
    PRResult,
)
from farm_agent.orchestrator.pipeline import FarmAgentPipeline
from farm_agent.analysis.analyzer import AnalysisResult


@pytest.fixture
def config():
    c = FarmAgentConfig()
    c.pipeline.sandbox_validation_enabled = True
    c.github.max_prs_per_day = 10
    return c


@pytest.fixture
async def pipeline(config):
    p = FarmAgentPipeline(config)
    p._human_typing_lock = AsyncMock()

    # Mock external boundaries
    p._github = AsyncMock()
    p._github.check_interaction_limits.return_value = False
    p._github.fetch_recent_maintainer_comments.return_value = []
    p._github.list_pull_requests.return_value = []
    p._github.get_file_tree.return_value = []
    p._github.get_file_content.return_value = ""

    p._memory = AsyncMock()
    p._memory.get_today_pr_count.return_value = 0
    p._memory.has_analyzed.return_value = False
    p._memory.get_repo_prs.return_value = []
    p._memory.get_knowledge.return_value = ""

    # Mock Guidelines
    p._analyzer = AsyncMock()
    p._analyzer.check_maintainer_vibe.return_value = "FRIENDLY"

    dummy_repo = Repository(
        full_name="mock/repo", name="repo", owner="mock", html_url="", clone_url=""
    )
    dummy_contrib = Contribution(
        finding=Finding(
            type=ContributionType.SECURITY_FIX,
            severity=Severity.CRITICAL,
            title="x",
            file_path="y",
            description="z",
        ),
        contribution_type=ContributionType.SECURITY_FIX,
        title="x",
        description="y",
    )
    p._pr_manager = AsyncMock()
    p._pr_manager.create_pr.return_value = PRResult(
        repo=dummy_repo,
        contribution=dummy_contrib,
        pr_number=1337,
        pr_url="https://github.com/mock/repo/pull/1337",
        branch_name="mock-branch",
        fork_full_name="mock/repo",
    )

    p._sandbox = AsyncMock()
    p._sandbox.run_in_sandbox.return_value = {"exit_code": 0, "stdout": "mock logs", "stderr": ""}

    return p


@pytest.fixture
def repo():
    return Repository(
        id=1,
        name="mock-repo",
        full_name="owner/mock-repo",
        owner="owner",
        html_url="https://github.com/owner/mock-repo",
        description="A mock repo",
        clone_url="https://github.com/owner/mock-repo.git",
        default_branch="main",
        stars=1000,
    )


class MockLLMProvider:
    def __init__(self, *args, **kwargs):
        self.response_text = ""

    def set_task(self, task):
        pass

    async def complete(self, prompt: str, system: str = "", **kwargs):
        return self.response_text

    async def close(self):
        pass


@pytest.mark.asyncio
@patch("farm_agent.llm.provider.create_llm_provider")
@patch("farm_agent.orchestrator.pipeline.fetch_repo_guidelines")
@patch("farm_agent.orchestrator.pipeline.run_security_gate")
@patch.object(FarmAgentPipeline, "_clone_and_patch_repo")
async def test_happy_path(
    mock_clone, mock_sec_gate, mock_guidelines, mock_create_llm, pipeline, repo
):
    """TEST 1: The Happy Path (Complete Success)"""
    mock_guidelines.return_value.has_guidelines = False
    mock_sec_gate.return_value = None

    # Needs a mock Future/Coroutine returning "/tmp/mock" to simulate async return safely in Py 3.14
    async def _dummy_clone(*args, **kwargs):
        return "/tmp/mock"

    mock_clone.side_effect = _dummy_clone

    # Setup LLM mocks
    # We have several components using LLM: Devil's Advocate, Layer 1, Generator, Layer 2
    # pipeline._llm is used for DA and Analyzer (which we mock directly).
    # Layer 1 & 2 call create_llm_provider.

    pipeline._llm = MockLLMProvider()

    # Mock Devil's Advocate approval
    pipeline._llm.response_text = json.dumps(
        {
            "devil_advocate_critique": "Looks fine",
            "is_real_vulnerability": True,
            "confidence_score": 95,
            "data_flow_proof": "Flows from req.body to eval()",
        }
    )

    layer1_llm = MockLLMProvider()
    layer1_llm.response_text = json.dumps(
        {"is_genuine_severe_vuln": True, "expert_critique": "Genuine critical bug."}
    )

    layer2_llm = MockLLMProvider()
    layer2_llm.response_text = json.dumps({"final_approval": True, "rejection_reason": ""})

    # create_llm_provider is called by L1 and L2
    mock_create_llm.side_effect = [layer1_llm, layer2_llm]

    # Generator mockup
    pipeline._generator = AsyncMock()
    # It must return a contribution that passes Snippet Sanity Check (search != replace)
    patch_change = FileChange(
        path="src/main.py",
        new_content="",
        is_new_file=False,
    )

    pipeline._generator.generate.return_value = Contribution(
        finding=Finding(
            type=ContributionType.SECURITY_FIX,
            severity=Severity.CRITICAL,
            title="RCE",
            file_path="src/main.py",
            description="x",
        ),
        contribution_type=ContributionType.SECURITY_FIX,
        title="Fix RCE",
        description="Fixed",
        changes=[patch_change],
    )

    # Mock Analyzer returning 1 finding
    finding = Finding(
        type=ContributionType.FEATURE_ADD,  # Feature bypasses keyword blacklist
        severity=Severity.HIGH,
        title="RCE in auth",
        description="import os; eval()",
        file_path="src/main.py",
        impact_level=ImpactLevel.CRITICAL,
        priority_score=100,
    )
    pipeline._analyzer.analyze.return_value = AnalysisResult(
        repo=repo, findings=[finding], analyzed_files=1
    )
    pipeline._github.get_file_content.return_value = "import os\n os.system(cmd)"

    print(
        "DEBUG MOCK FILE CONTENT:", await pipeline._github.get_file_content("o", "r", "src/main.py")
    )

    # Execute
    res = await pipeline._process_repo(repo, dry_run=False)

    # Asserts
    assert res.prs_created == 1, "Happy Path failed to create PR"
    pipeline._pr_manager.create_pr.assert_called_once()
    mock_sec_gate.assert_called_once()
    mock_sandbox.run_in_sandbox.assert_called_once()


@pytest.mark.asyncio
@patch("farm_agent.llm.provider.create_llm_provider")
@patch("farm_agent.orchestrator.pipeline.fetch_repo_guidelines")
@patch.object(FarmAgentPipeline, "_clone_and_patch_repo")
async def test_snippet_sanity_trap(mock_clone, mock_guidelines, mock_create_llm, pipeline, repo):
    """TEST 2: The Snippet Sanity Trap ("requires login" string)"""
    finding = Finding(
        type=ContributionType.FEATURE_ADD,
        severity=Severity.HIGH,
        title="RCE",
        description="description",
        file_path="src/main.py",
        impact_level=ImpactLevel.CRITICAL,
        priority_score=100,
    )
    pipeline._analyzer.analyze.return_value = AnalysisResult(
        repo=repo, findings=[finding], analyzed_files=1
    )

    # Mock fetch content returning just the string
    pipeline._github.get_file_content.return_value = "requires login"

    pipeline._generator = AsyncMock()

    # Execute pipeline
    res = await pipeline._process_repo(repo, dry_run=False)

    # Assert
    assert res.prs_created == 0
    # Sanity check happens before Layer 1 (Wait, Snippet verification in _layer1_expert_appraisal)
    # Check if add_filter_lesson was NOT called because it naturally drops it
    pipeline._memory.add_filter_lesson.assert_not_called()
    pipeline._pr_manager.create_pr.assert_not_called()


@pytest.mark.asyncio
@patch("farm_agent.llm.provider.create_llm_provider")
@patch("farm_agent.orchestrator.pipeline.fetch_repo_guidelines")
@patch.object(FarmAgentPipeline, "_clone_and_patch_repo")
async def test_kimi_rejection(mock_clone, mock_guidelines, mock_create_llm, pipeline, repo):
    """TEST 3: The Kimi Rejection (Layer 1)"""
    mock_guidelines.return_value.has_guidelines = False

    pipeline._llm = MockLLMProvider()
    pipeline._llm.response_text = json.dumps(
        {
            "devil_advocate_critique": "Looks fine",
            "is_real_vulnerability": True,
            "confidence_score": 95,
            "data_flow_proof": "Flows from req.body to eval()",
        }
    )

    layer1_llm = MockLLMProvider()
    layer1_llm.response_text = json.dumps(
        {"is_genuine_severe_vuln": False, "expert_critique": "Mocked hallucination"}
    )
    mock_create_llm.side_effect = [layer1_llm]

    finding = Finding(
        type=ContributionType.FEATURE_ADD,
        severity=Severity.HIGH,
        title="RCE",
        description="import os; eval()",
        file_path="src/main.py",
        impact_level=ImpactLevel.CRITICAL,
        priority_score=100,
    )
    pipeline._analyzer.analyze.return_value = AnalysisResult(
        repo=repo, findings=[finding], analyzed_files=1
    )
    pipeline._github.get_file_content.return_value = "def real_looking_code(); pass"

    pipeline._generator = AsyncMock()  # Should never be called

    # Execute
    res = await pipeline._process_repo(repo, dry_run=False)

    # Assert
    assert res.prs_created == 0
    pipeline._generator.generate.assert_not_called()
    # Confirm DB lesson recorded
    pipeline._memory.add_filter_lesson.assert_called_once()
    args, kwargs = pipeline._memory.add_filter_lesson.call_args
    assert args[1] == 1  # layer=1
    assert "Mocked hallucination" in args[3]


@pytest.mark.asyncio
@patch("farm_agent.llm.provider.create_llm_provider")
@patch("farm_agent.orchestrator.pipeline.fetch_repo_guidelines")
@patch.object(FarmAgentPipeline, "_clone_and_patch_repo")
async def test_gemini_rejection_lazy_code(
    mock_clone, mock_guidelines, mock_create_llm, pipeline, repo
):
    """TEST 4: The Gemini Rejection (Layer 2) / Lazy Code"""
    mock_guidelines.return_value.has_guidelines = False

    async def _dummy_clone(*args, **kwargs):
        return "/tmp/mock"

    mock_clone.side_effect = _dummy_clone

    pipeline._llm = MockLLMProvider()
    pipeline._llm.response_text = json.dumps(
        {
            "devil_advocate_critique": "Looks fine",
            "is_real_vulnerability": True,
            "confidence_score": 95,
            "data_flow_proof": "Flows from req.body to eval()",
        }
    )

    layer1_llm = MockLLMProvider()
    layer1_llm.response_text = json.dumps(
        {"is_genuine_severe_vuln": True, "expert_critique": "Good."}
    )
    layer2_llm = MockLLMProvider()
    layer2_llm.response_text = json.dumps(
        {"final_approval": False, "rejection_reason": "Contains TODO placeholder"}
    )
    mock_create_llm.side_effect = [layer1_llm, layer2_llm]

    finding = Finding(
        type=ContributionType.FEATURE_ADD,
        severity=Severity.HIGH,
        title="RCE",
        description="import os; eval()",
        file_path="src/main.py",
        impact_level=ImpactLevel.CRITICAL,
        priority_score=100,
    )
    pipeline._analyzer.analyze.return_value = AnalysisResult(
        repo=repo, findings=[finding], analyzed_files=1
    )
    pipeline._github.get_file_content.return_value = "def real_looking_code(); pass"

    # Generator mockup with TODO
    pipeline._generator = AsyncMock()
    patch_change = FileChange(
        path="src/main.py",
        new_content="",
        is_new_file=False,
    )

    pipeline._generator.generate.return_value = Contribution(
        finding=finding,
        contribution_type=ContributionType.SECURITY_FIX,
        title="Fix RCE",
        description="Fixed with TODO",
        changes=[patch_change],
    )

    # Execute
    res = await pipeline._process_repo(repo, dry_run=False)

    # Assert
    assert res.prs_created == 0
    pipeline._pr_manager.create_pr.assert_not_called()

    # Confirm DB lesson recorded for Layer 2
    pipeline._memory.add_filter_lesson.assert_called_once()
    args, kwargs = pipeline._memory.add_filter_lesson.call_args
    assert args[1] == 2  # layer=2
    assert (
        "Contains TODO placeholder" in kwargs.get("critique") or "Contains TODO placeholder" in args
    )
