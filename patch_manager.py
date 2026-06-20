import re

with open('farm_agent/pr/manager.py', 'r') as f:
    content = f.read()

# Fix line 52-53
content = content.replace(
    '        if (stripped.startswith(("- [ ]", "* [ ]")) and any(term in stripped for term in allowed_terms)\n                and not any(danger in stripped for danger in ["breaking", "release", "deploy", "migration"])):\n                    lines[i] = line.replace("[ ]", "[x]", 1)',
    '        allowed = any(term in stripped for term in allowed_terms)\n        safe = not any(danger in stripped for danger in ["breaking", "release", "deploy", "migration"])\n        if stripped.startswith(("- [ ]", "* [ ]")) and allowed and safe:\n            lines[i] = line.replace("[ ]", "[x]", 1)'
)

# Fix line 62
content = content.replace(
    '    _LEDGER_HEADER = ["timestamp", "repo_url", "pr_url", "status", "error_details", "vulnerability_type"]',
    '    _LEDGER_HEADER = [\n        "timestamp", "repo_url", "pr_url", "status", "error_details", "vulnerability_type"\n    ]'
)

# Fix line 219
content = content.replace(
    '            author_email = user.get("email") or f"{user.get(\'id\', \'9919\')}+{user.get(\'login\', \'farm_agent\')}@users.noreply.github.com"',
    '            author_email = user.get("email") or (\n                f"{user.get(\'id\', \'9919\')}+{user.get(\'login\', \'farm_agent\')}"\n                "@users.noreply.github.com"\n            )'
)

# Fix line 220
content = content.replace(
    '            author_date = (datetime.now(UTC) - timedelta(minutes=random.randint(15, 45))).strftime("%Y-%m-%dT%H:%M:%SZ")',
    '            delay = timedelta(minutes=random.randint(15, 45))\n            author_date = (datetime.now(UTC) - delay).strftime("%Y-%m-%dT%H:%M:%SZ")'
)

# Fix line 248
content = content.replace(
    '            from farm_agent.core.models import ContributionType as _CT2',
    '            from farm_agent.core.models import ContributionType as _ct2'
)
content = content.replace('_CT2.ISSUE', '_ct2.ISSUE')
content = content.replace('_CT2.SECURITY', '_ct2.SECURITY')
content = content.replace('_CT2.PERFORMANCE', '_ct2.PERFORMANCE')
content = content.replace('_CT2.CODE_QUALITY', '_ct2.CODE_QUALITY')

with open('farm_agent/pr/manager.py', 'w') as f:
    f.write(content)
