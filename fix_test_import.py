import re

with open('tests/unit/test_circular_target.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Add pydantic import directly into models mock scope
import_statement = "import pytest\n"
content = re.sub(r'import pytest\n', f'{import_statement}from pydantic import BaseModel, Field\n', content, 1)

with open('tests/unit/test_circular_target.py', 'w', encoding='utf-8') as f:
    f.write(content)
