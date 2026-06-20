with open('farm_agent/pr/manager.py', 'r') as f:
    content = f.read()

content = content.replace(
    '        safe = not any(danger in stripped for danger in ["breaking", "release", "deploy", "migration"])',
    '        dangers = ["breaking", "release", "deploy", "migration"]\n        safe = not any(d in stripped for d in dangers)'
)

content = content.replace('_CT2.README_FIX', '_ct2.README_FIX')
content = content.replace('_CT2.UI_UX_FIX', '_ct2.UI_UX_FIX')
content = content.replace('_CT2.FEATURE_ADD', '_ct2.FEATURE_ADD')
content = content.replace('_CT2.REFACTOR', '_ct2.REFACTOR')

# Fixing N813
content = content.replace('ContributionType as _ct2', 'ContributionType')
content = content.replace('_ct2.', 'ContributionType.')

with open('farm_agent/pr/manager.py', 'w') as f:
    f.write(content)
