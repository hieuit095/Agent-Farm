import re
with open("tests/test_async_io_pipeline.py", "r") as f:
    content = f.read()

# Instead of passing the async lambda in the patch decorator which causes syntax errors,
# we should define the async mock function outside and reference it.
new_code = '''
        async def mock_gather(*args, **kwargs):
            import asyncio
            return await asyncio.gather(*args)

        with patch(
            "farm_agent.orchestrator.pipeline.asyncio.gather",
            new_callable=unittest.mock.AsyncMock,
            side_effect=mock_gather
        ):'''

content = re.sub(
    r'''async def mock_gather\(\*args, \*\*kwargs\):
                return await asyncio\.gather\(\*args\)
            mock_to_thread\.reset_mock\(\)
            with patch\(
                "farm_agent\.orchestrator\.pipeline\.asyncio\.gather",
                new_callable=unittest\.mock\.AsyncMock,
                side_effect=mock_gather
            \):''',
    new_code,
    content
)

# And fix any leftover `side_effect=async def`
content = re.sub(r'side_effect=async def .*?:\s+.*?\s+', 'side_effect=mock_gather', content)


with open("tests/test_async_io_pipeline.py", "w") as f:
    f.write(content)
