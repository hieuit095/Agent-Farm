import re

with open("tests/test_async_io_pipeline.py", "r") as f:
    content = f.read()

content = content.replace("self.config.pipeline.llm_concurrency_cap = 10", """self.config.pipeline.llm_concurrency_cap = 10
        self.config.llm.provider_cap = 10""")

with open("tests/test_async_io_pipeline.py", "w") as f:
    f.write(content)
