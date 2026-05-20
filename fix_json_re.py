import re

with open('farm_agent/orchestrator/pipeline.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Add imports correctly at the top of the file
import_statement = "import json\nimport re\n"
content = re.sub(r'from dataclasses import dataclass, field', f'{import_statement}from dataclasses import dataclass, field', content, 1)

with open('farm_agent/orchestrator/pipeline.py', 'w', encoding='utf-8') as f:
    f.write(content)
