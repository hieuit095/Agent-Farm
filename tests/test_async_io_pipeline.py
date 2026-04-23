
import asyncio
import os
import unittest
from unittest.mock import MagicMock, patch

from farm_agent.core.models import FileChange
from farm_agent.orchestrator.pipeline import ContribPipeline


class TestAsyncIOPipeline(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.config = MagicMock()
        self.config.notifications.telegram_token = None
        self.config.notifications.telegram_chat_id = None
        self.pipeline = ContribPipeline(self.config)

    @patch("farm_agent.orchestrator.pipeline.asyncio.to_thread")
    @patch("farm_agent.orchestrator.pipeline.os.path.join")
    @patch("farm_agent.orchestrator.pipeline.tempfile.gettempdir")
    async def test_clone_and_patch_repo_uses_to_thread(self, mock_gettempdir, mock_join, mock_to_thread):
        mock_gettempdir.return_value = "/tmp"
        mock_join.return_value = "/tmp/clone"

        async def mock_to_thread_func(func, *args, **kwargs):
            if func == os.makedirs:
                return None
            return None

        mock_to_thread.side_effect = mock_to_thread_func
        changes = [FileChange(path="test.py", new_content="print(1)", is_new_file=True)]
        tests_added = []
        self.pipeline._apply_patch_sync = MagicMock()

        async def _mock_gather(*args, **kwargs):
            for arg in args:
                await arg
            return []

        with patch("farm_agent.orchestrator.pipeline.asyncio.gather", new_callable=unittest.mock.AsyncMock, side_effect=_mock_gather):
            self.pipeline._clone_cache = {"url": "/tmp/clone"}
            await self.pipeline._clone_and_patch_repo("url", changes, tests_added)

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
            patch("farm_agent.orchestrator.pipeline.os.path.dirname", return_value="/tmp/clone")
        ):
            self.pipeline._apply_patch_sync(clone_path, change)

            # Check if makedirs and open were called
            mock_makedirs.assert_called()
            mock_open.assert_called_with("/tmp/clone/new.py", "w", encoding="utf-8")
            mock_open().__enter__().write.assert_called_with("print('hello')")
