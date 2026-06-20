with open('farm_agent/pr/patrol.py', 'r') as f:
    content = f.read()

content = content.replace(
    'f"🛡️ <b>[PATROL]</b> Action Taken!\\nRepo: <code>{pr[\'repo\']}</code>\\n" \\',
    'f"🛡️ <b>[PATROL]</b> Action Taken!\\n" \\\n                                f"Repo: <code>{pr[\'repo\']}</code>\\n" \\'
)

with open('farm_agent/pr/patrol.py', 'w') as f:
    f.write(content)
