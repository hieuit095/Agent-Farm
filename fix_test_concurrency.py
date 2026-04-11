import sys
filepath = "tests/unit/test_concurrency_cap.py"

with open(filepath, "r") as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if line.startswith("from farm_agent.orchestrator.pipeline import ContribPipeline"):
        new_lines.insert(0, line)
    else:
        new_lines.append(line)

with open(filepath, "w") as f:
    f.writelines(new_lines)
