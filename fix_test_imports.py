import os
import sys

def process_file(filepath):
    with open(filepath, "r") as f:
        content = f.read()

    new_content = content.replace("farm_agent", "farm_agent")

    # Specifically for tests/test_async_io_pipeline.py which threw an error during collection
    if filepath == "tests/test_async_io_pipeline.py":
        new_content = new_content.replace("from farm_agent.core.models import FileChange", "from farm_agent.core.models import FileChange")
        # Ensure imports aren't duplicated or improperly ordered

    with open(filepath, "w") as f:
        f.write(new_content)

for root, dirs, files in os.walk("tests"):
    for file in files:
        if file.endswith(".py"):
            process_file(os.path.join(root, file))
