"""Live integration test for the sandbox-backed CI self-correction loop."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from contribai.core.sandbox import DockerSandbox
from contribai.orchestrator.memory import Memory
from contribai.pr.patrol import PRPatrol


class ScriptedLLM:
    """Return a broken fix first, then a corrected fix."""

    def __init__(self):
        self.prompts: list[str] = []
        self._responses = [
            "```python\ndef broken(:\n    return 'nope'\n```",
            "```python\ndef fixed():\n    return 'ok'\n```",
        ]

    async def complete(self, prompt: str, **_: object) -> str:
        self.prompts.append(prompt)
        index = len(self.prompts) - 1
        if index >= len(self._responses):
            raise AssertionError("LLM was called more times than expected")
        return self._responses[index]


class RecordingSandbox(DockerSandbox):
    """Proxy the real sandbox and record every run result."""

    def __init__(self, sink: list[dict]):
        super().__init__()
        self._sink = sink

    async def run_in_sandbox(self, *args, **kwargs) -> dict:
        result = await super().run_in_sandbox(*args, **kwargs)
        self._sink.append(result)
        return result


@pytest.mark.asyncio
async def test_ci_sandbox_loop_self_corrects_before_push(tmp_path):
    """A broken first fix must fail locally and only the corrected second fix may push."""
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    source_path = repo_root / "src" / "app.py"
    source_path.parent.mkdir()
    source_path.write_text("def current():\n    return 'hello'\n", encoding="utf-8")

    async def get_file_content(_owner: str, _repo: str, path: str, ref: str | None = None) -> str:
        del ref
        return (repo_root / Path(path)).read_text(encoding="utf-8")

    github = MagicMock()
    github.get_authenticated_user = AsyncMock(
        return_value={"login": "bot", "name": "Bot", "email": "bot@example.com"}
    )
    github._get = AsyncMock(
        side_effect=[
            {
                "state": "open",
                "number": 42,
                "html_url": "https://github.com/owner/repo/pull/42",
                "head": {
                    "sha": "abc123",
                    "ref": "fix-branch",
                    "repo": {
                        "owner": {"login": "bot"},
                        "name": "repo",
                    },
                },
            },
            {"sha": "file-sha-123"},
        ]
    )
    github.get_pr_check_runs = AsyncMock(
        return_value=[
            {"id": 999, "name": "python-ci", "status": "completed", "conclusion": "failure"},
        ]
    )
    github.download_check_run_log = AsyncMock(
        return_value=(
            "Traceback (most recent call last)\n"
            '  File "/home/runner/work/repo/repo/src/app.py", line 1, in <module>\n'
            "    current()\n"
            "AssertionError: simulated CI failure\n"
        )
    )
    github.get_pr_diff = AsyncMock(
        return_value="--- a/src/app.py\n+++ b/src/app.py\n@@ -1,2 +1,2 @@\n-old\n+new\n"
    )
    github.get_pr_commits = AsyncMock(return_value=[])
    github.get_commit_diff = AsyncMock(return_value="")
    github.get_file_tree = AsyncMock(
        return_value=[
            {"path": "src/app.py", "type": "blob", "size": source_path.stat().st_size},
        ]
    )
    github.get_file_content = AsyncMock(side_effect=get_file_content)
    github.create_or_update_file = AsyncMock(return_value={"commit": {"sha": "newsha"}})
    github.create_pr_comment = AsyncMock(return_value={"id": 1})
    github.close_pull_request = AsyncMock()
    github.get_assigned_issues = AsyncMock(return_value=[])

    llm = ScriptedLLM()
    sandbox_runs: list[dict] = []

    memory = Memory(tmp_path / "memory.db")
    await memory.init()
    await memory.record_pr(
        "owner/repo",
        42,
        "https://github.com/owner/repo/pull/42",
        "fix: recover CI",
        "code_quality",
    )

    patrol = PRPatrol(
        github=github,
        llm=llm,
        memory=memory,
        enable_sandbox_validation=True,
        sandbox_factory=lambda: RecordingSandbox(sandbox_runs),
    )

    try:
        result = await patrol.patrol(
            [{"repo": "owner/repo", "pr_number": 42, "status": "open", "title": "fix: recover CI"}],
        )
    finally:
        await memory.close()

    assert len(sandbox_runs) == 2
    assert sandbox_runs[0]["exit_code"] != 0
    assert sandbox_runs[1]["exit_code"] == 0

    assert len(llm.prompts) == 2
    assert "Local Validation Failure" in llm.prompts[1]
    assert "SyntaxError" in llm.prompts[1]

    github.create_or_update_file.assert_called_once()
    pushed_content = github.create_or_update_file.call_args.args[3]
    assert "def fixed()" in pushed_content

    github.create_pr_comment.assert_called_once()
    github.close_pull_request.assert_not_called()
    assert result.ci_fixes_pushed == 1
