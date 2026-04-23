with open("tests/test_async_io_pipeline.py", "r") as f:
    content = f.read()

# We want to replace the `new_callable=unittest.mock.AsyncMock` with a proper mocked return
# that awaits the coroutines in *args to avoid "never awaited" warnings.

replacement = '''
        async def _mock_gather(*args, **kwargs):
            for arg in args:
                await arg
            return []

        with patch(
            "farm_agent.orchestrator.pipeline.asyncio.gather",
            new_callable=unittest.mock.AsyncMock,
            side_effect=_mock_gather
        ):'''

content = content.replace('''
        with patch(
            "farm_agent.orchestrator.pipeline.asyncio.gather",
            new_callable=unittest.mock.AsyncMock
        ):''', replacement)

with open("tests/test_async_io_pipeline.py", "w") as f:
    f.write(content)
