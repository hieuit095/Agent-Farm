with open("tests/test_async_io_pipeline.py", "r") as f:
    content = f.read()

import re
content = re.sub(
    r'lambda \*args, \*\*kwargs: asyncio\.gather\(\*args\)',
    r'lambda *args, **kwargs: asyncio.gather(*args)',
    content
)

if 'lambda *args, **kwargs' not in content:
    content = content.replace('new_callable=unittest.mock.AsyncMock\n        ):', 'new_callable=unittest.mock.AsyncMock,\n            side_effect=lambda *args, **kwargs: asyncio.gather(*args)\n        ):')

with open("tests/test_async_io_pipeline.py", "w") as f:
    f.write(content)
