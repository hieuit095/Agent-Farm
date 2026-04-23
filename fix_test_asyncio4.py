with open("tests/test_async_io_pipeline.py", "r") as f:
    content = f.read()

# We need to correctly patch asyncio.gather by returning an async mock that actually runs gather
# The proper way to do this in Python 3.12 is just passing an async function to side_effect.

# We'll replace the existing mock with a proper implementation.
content = content.replace('''
        with patch(
            "farm_agent.orchestrator.pipeline.asyncio.gather",
            new_callable=unittest.mock.AsyncMock
        ):''', '''
        async def _mock_gather(*args, **kwargs):
            import asyncio
            return await asyncio.gather(*args, **kwargs)

        with patch(
            "farm_agent.orchestrator.pipeline.asyncio.gather",
            new_callable=unittest.mock.AsyncMock,
            side_effect=_mock_gather
        ):''')

with open("tests/test_async_io_pipeline.py", "w") as f:
    f.write(content)
