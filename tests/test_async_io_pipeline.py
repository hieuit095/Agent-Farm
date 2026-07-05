import asyncio
import os
import unittest
from unittest.mock import MagicMock, patch

from farm_agent.core.models import FileChange
from farm_agent.orchestrator.pipeline import FarmAgentPipeline


class TestAsyncIOPipeline(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        from farm_agent.core.config import FarmAgentConfig

        self.config = FarmAgentConfig()
        self.config.pipeline.llm_concurrency_cap = 5
        self.config.llm.provider = "openrouter"

        self.pipeline = FarmAgentPipeline(self.config)

    @patch("farm_agent.orchestrator.pipeline.asyncio.to_thread")
    @patch("farm_agent.orchestrator.pipeline.os.path.join")
    @patch("farm_agent.orchestrator.pipeline.tempfile.gettempdir")
    async def test_clone_and_patch_repo_uses_to_thread(
        self, mock_gettempdir, mock_join, mock_to_thread
    ):
        mock_gettempdir.return_value = "/tmp"
        mock_join.return_value = "/tmp/clone"

        # Mocking the clone behavior
        async def mock_to_thread_func(func, *args, **kwargs):
            if func == os.makedirs:
                return None
            return await asyncio.to_thread(func, *args, **kwargs)

        mock_to_thread.side_effect = mock_to_thread_func

        changes = [FileChange(path="test.py", new_content="print(1)", is_new_file=True)]
        tests_added = []

        # We need to mock _apply_patch_sync because it's called via to_thread
        self.pipeline._apply_patch_sync = MagicMock()

        # Also need to mock _do_clone inside the function or just mock the whole to_thread
        # Let's simplify and just check calls to mock_to_thread

        with patch(
            "farm_agent.orchestrator.pipeline.asyncio.gather", new_callable=unittest.mock.AsyncMock
        ):
            # Reset mock to avoid noise from previous setups
            mock_to_thread.reset_mock()

            # Mock _clone_cache
            self.pipeline._clone_cache = {"url": "/tmp/clone"}

            await self.pipeline._clone_and_patch_repo("url", changes, tests_added)

            # Verify that _apply_patch_sync was wrapped in to_thread
            # The first argument to to_thread should be self.pipeline._apply_patch_sync
            calls = mock_to_thread.call_args_list
            found = False
            for c in calls:
                if c[0][0] == self.pipeline._apply_patch_sync:
                    found = True
                    break
            self.assertTrue(found, "Expected _apply_patch_sync to be called via to_thread")

    @patch("farm_agent.orchestrator.pipeline.os.makedirs")
    @patch("farm_agent.orchestrator.pipeline.open", create=True)
    @patch("farm_agent.orchestrator.pipeline.os.path.exists")
    def test_apply_patch_sync_correctness(self, mock_exists, mock_open, mock_makedirs):
        clone_path = "/tmp/clone"
        change = FileChange(path="new.py", new_content="print('hello')", is_new_file=True)

        # Mock os.path.normpath to return a predictable path
        with (
            patch("farm_agent.orchestrator.pipeline.os.path.normpath", side_effect=lambda x: x),
            patch("farm_agent.orchestrator.pipeline.os.path.dirname", return_value="/tmp/clone"),
        ):
            self.pipeline._apply_patch_sync(clone_path, change)

            # Check if makedirs and open were called
            mock_makedirs.assert_called()
            mock_open.assert_called_with("/tmp/clone/new.py", "w", encoding="utf-8")
            mock_open().__enter__().write.assert_called_with("print('hello')")
