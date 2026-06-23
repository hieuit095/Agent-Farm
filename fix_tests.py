import re

with open("tests/test_async_io_pipeline.py", "r") as f:
    content = f.read()

content = content.replace('self.config = MagicMock()', 'self.config = MagicMock()\n        self.config.pipeline = MagicMock()\n        self.config.llm = MagicMock()')

with open("tests/test_async_io_pipeline.py", "w") as f:
    f.write(content)
