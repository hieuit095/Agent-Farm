with open('farm_agent/pr/patrol.py', 'r') as f:
    content = f.read()

# Fix long strings
content = content.replace(
    'f"🛡️ <b>[PATROL]</b> Action Taken!\\nRepo: <code>{pr[\'repo\']}</code>\\nAction: Pushed CI Fix\\n" \\',
    'f"🛡️ <b>[PATROL]</b> Action Taken!\\nRepo: <code>{pr[\'repo\']}</code>\\n" \\\n                                "Action: Pushed CI Fix\\n" \\'
)

content = content.replace(
    'f"⛔ <b>[ALERT]</b> Hostile maintainer detected. Repo <code>{pr[\'repo\']}</code> \\',
    'f"⛔ <b>[ALERT]</b> Hostile maintainer detected. " \\\n                                f"Repo <code>{pr[\'repo\']}</code> \\'
)

content = content.replace(
    'comment=("Closing this PR for now as I won\'t have time to address the "',
    'comment=("Closing this PR for now as I won\'t have time to " \\\n                                        "address the "'
)

content = content.replace(
    'f"🛡️ <b>[PATROL]</b> Action Taken!\\nRepo: <code>{pr[\'repo\']}</code>\\nAction: Pushed Code Fix\\n" \\',
    'f"🛡️ <b>[PATROL]</b> Action Taken!\\nRepo: <code>{pr[\'repo\']}</code>\\n" \\\n                            "Action: Pushed Code Fix\\n" \\'
)

content = content.replace(
    'f"🛡️ <b>[PATROL]</b> Action Taken!\\nRepo: <code>{pr[\'repo\']}</code>\\nAction: Replied to comment\\n" \\',
    'f"🛡️ <b>[PATROL]</b> Action Taken!\\nRepo: <code>{pr[\'repo\']}</code>\\n" \\\n            "Action: Replied to comment\\n" \\'
)

with open('farm_agent/pr/patrol.py', 'w') as f:
    f.write(content)
