with open("tests/test_async_io_pipeline.py", "r") as f:
    content = f.read()

import re
content = re.sub(
    r'lambda \*args, \*\*kwargs: asyncio\.gather\(\*args\)',
    r'lambda *args, **kwargs: __import__("asyncio").gather(*args)',
    content
)

# Fix the warning for never awaited coroutine
# Since it's returning a coroutine we need an async lambda
content = content.replace(
    r'lambda *args, **kwargs: __import__("asyncio").gather(*args)',
    r'''async def mock_gather(*args, **kwargs):
                return await asyncio.gather(*args)
            mock_to_thread.reset_mock()
            with patch(
                "farm_agent.orchestrator.pipeline.asyncio.gather",
                new_callable=unittest.mock.AsyncMock,
                side_effect=mock_gather
            ):'''
)

with open("tests/test_async_io_pipeline.py", "w") as f:
    f.write(content)
