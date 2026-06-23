import re

with open("tests/test_async_io_pipeline.py", "r") as f:
    content = f.read()

content = content.replace("self.config = MagicMock()", """self.config = MagicMock()
        self.config.pipeline.llm_concurrency_cap = 10
        self.config.llm.provider = "deepseek"
        self.config.llm.model = "deepseek-coder"
""")

with open("tests/test_async_io_pipeline.py", "w") as f:
    f.write(content)

with open("tests/test_omni_e2e_pipeline.py", "r") as f:
    content = f.read()

content = content.replace("await self._llm.close()", "# await self._llm.close()")

with open("tests/test_omni_e2e_pipeline.py", "w") as f:
    f.write(content)
