import asyncio
import json
import logging
import sys

# Setup logging to stdout
logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler(sys.stdout)])

async def run_test():
    from unittest.mock import AsyncMock, patch, MagicMock
    from farm_agent.core.config import FarmAgentConfig
    from farm_agent.orchestrator.pipeline import FarmAgentPipeline
    from farm_agent.core.models import Repository, Finding, ContributionType, Severity, ImpactLevel, PRResult, Contribution, FileChange, AnalysisResult

    print("Step 1: Setup")
    repo = Repository(owner="owner", name="mock-repo", full_name="owner/mock-repo", description="A mock repo")
    
    config = FarmAgentConfig()
    pipeline = FarmAgentPipeline(config)
    pipeline._human_typing_lock = asyncio.Lock()
    
    pipeline._pr_manager = AsyncMock()
    pipeline._pr_manager.create_pr.return_value = PRResult(
        repo=repo, contribution=Contribution(finding=Finding(type=ContributionType.FEATURE_ADD, severity=Severity.HIGH, title='a', description='b', file_path='c', impact_level=ImpactLevel.CRITICAL), contribution_type=ContributionType.SECURITY_FIX, title='x', description='y', changes=[]), pr_number=1337, pr_url="x", branch_name="mock", fork_full_name="mock"
    )
    
    pipeline._sandbox = AsyncMock()
    pipeline._sandbox.run_in_sandbox.return_value = {"exit_code": 0, "stdout": "mock logs", "stderr": ""}

    pipeline._memory = AsyncMock()
    pipeline._memory.get_repo_prs.return_value = []
    pipeline._memory.get_today_pr_count.return_value = 0
    
    pipeline._analyzer = AsyncMock()
    
    pipeline._github = AsyncMock()
    pipeline._github.fetch_recent_maintainer_comments.return_value = []
    pipeline._github.list_pull_requests.return_value = []
    pipeline._github.get_file_tree.return_value = []
    pipeline._github.check_interaction_limits.return_value = False
    pipeline._github.get_file_content.return_value = "import os\nos.system(cmd)"
    
    class MockLLMProvider:
        def __init__(self): self.response_text = ""
        def set_task(self, task): pass
        async def complete(self, prompt, **kwargs): return self.response_text
        async def close(self): pass

    pipeline._llm = MockLLMProvider()
    pipeline._llm.response_text = json.dumps({"devil_advocate_critique": "safe", "is_real_vulnerability": True, "confidence_score": 95, "data_flow_proof": "x"})
    
    layer1_llm = MockLLMProvider()
    layer1_llm.response_text = json.dumps({"is_genuine_severe_vuln": True, "expert_critique": "Genuine critical bug."})
    
    layer2_llm = MockLLMProvider()
    layer2_llm.response_text = json.dumps({"final_approval": True, "rejection_reason": ""})

    pipeline._generator = AsyncMock()
    patch_change = FileChange(path="src/main.py", new_content="", is_new_file=False)
    pipeline._generator.generate.return_value = Contribution(
        finding=Finding(type=ContributionType.SECURITY_FIX, severity=Severity.CRITICAL, title="RCE", file_path="src/main.py", description="x"),
        contribution_type=ContributionType.SECURITY_FIX, title="Fix RCE", description="Fixed", changes=[patch_change]
    )

    finding = Finding(type=ContributionType.FEATURE_ADD, severity=Severity.HIGH, title="RCE in auth", description="import os; eval()", file_path="src/main.py", impact_level=ImpactLevel.CRITICAL)
    pipeline._analyzer.analyze.return_value = AnalysisResult(repo=repo, findings=[finding], analyzed_files=1)

    print("Step 2: Start test")
    
    with patch("farm_agent.llm.provider.create_llm_provider") as mock_create_llm:
        with patch("farm_agent.orchestrator.pipeline.fetch_repo_guidelines") as mock_guidelines:
            with patch.object(FarmAgentPipeline, "_clone_and_patch_repo") as mock_clone:
                with patch("farm_agent.orchestrator.pipeline.run_security_gate") as mock_sec_gate:
                    mock_create_llm.side_effect = [layer1_llm, layer2_llm]
                    mock_guidelines.return_value.has_guidelines = False
                    
                    async def _dummy_clone(*args, **kwargs): return "/tmp/mock"
                    mock_clone.side_effect = _dummy_clone
                    
                    mock_sec_gate.return_value = None
                    
                    print("Step 3: Execute")
                    res = await pipeline._process_repo(repo, dry_run=False)
                    print(f"Step 4: Done. PRs created: {res.prs_created}")

asyncio.run(run_test())
