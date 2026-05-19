import re
from pathlib import Path

content = Path("tests/unit/test_pr_creation_integrity.py").read_text()
# Both tests expect 'PR CREATE REQUEST' and 'PR CREATE RESPONSE' at DEBUG level,
# but the tests use logging.INFO.
content = content.replace("caplog.at_level(logging.INFO)", "caplog.at_level(logging.DEBUG)")
Path("tests/unit/test_pr_creation_integrity.py").write_text(content)
