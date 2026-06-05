with open("tests/test_async_io_pipeline.py", "r") as f:
    content = f.read()

content = content.replace('return asyncio.to_thread(func, *args, **kwargs)', 'return await asyncio.to_thread(func, *args, **kwargs)')
content = content.replace('async def mock_to_thread_func(func, *args, **kwargs):', 'def mock_to_thread_func(func, *args, **kwargs):')

with open("tests/test_async_io_pipeline.py", "w") as f:
    f.write(content)

with open("tests/test_async_io_pipeline.py", "r") as f:
    content = f.read()

content = content.replace('return await asyncio.to_thread(func, *args, **kwargs)', 'return asyncio.create_task(asyncio.to_thread(func, *args, **kwargs))')

with open("tests/test_async_io_pipeline.py", "w") as f:
    f.write(content)
