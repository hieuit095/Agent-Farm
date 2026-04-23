with open("tests/test_async_io_pipeline.py", "r") as f:
    content = f.read()

# Let's completely replace test_clone_and_patch_repo_uses_to_thread to avoid syntax issues

new_test = '''    @patch("farm_agent.orchestrator.pipeline.asyncio.to_thread")
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
'''

import re
content = re.sub(r'    @patch\("farm_agent\.orchestrator\.pipeline\.asyncio\.to_thread"\).*?self\.assertTrue\(found, "Expected _apply_patch_sync to be called via to_thread"\)', new_test, content, flags=re.DOTALL)

with open("tests/test_async_io_pipeline.py", "w") as f:
    f.write(content)
