import re

with open('farm_agent/pr/patrol.py', 'r') as f:
    content = f.read()

# Fix long strings
content = content.replace(
    'Hostile maintainer detected. Repo <code>{pr[\'repo\']}</code> blacklisted.',
    'Hostile maintainer detected. Repo <code>{pr[\'repo\']}</code> \\\n                                blacklisted.'
)
content = content.replace(
    'comment="Closing this PR for now as I won\'t have time to address the remaining feedback. Thanks for the review!",',
    'comment=("Closing this PR for now as I won\'t have time to address the " \n                       "remaining feedback. Thanks for the review!"),'
)
content = content.replace(
    '"  ⚠️ LLM classification failed after %d retries — marking %d feedback items as ALREADY_HANDLED",',
    '"  ⚠️ LLM classification failed after %d retries — marking " \n            "%d feedback items as ALREADY_HANDLED",'
)
content = content.replace(
    'Mới check mail thấy có notification từ Maintainer. Bắt đầu đọc... (Simulating notification lag: %ds)',
    'Mới check mail thấy có notification từ Maintainer. Bắt đầu đọc... " \n            "(Simulating notification lag: %ds)'
)
content = content.replace(
    'f"Write a concise reply (1-3 sentences). Be direct. No apologies, no excessive politeness."',
    'f"Write a concise reply (1-3 sentences). Be direct. No apologies, no excessive " \\\n                f"politeness."'
)
content = content.replace(
    '# Strip emojis and non-ASCII (keep alphanumeric, spaces, hyphens, underscores, dots, slashes)',
    '# Strip emojis and non-ASCII (keep alphanumeric, spaces, hyphens, dots, slashes)'
)

# For the HTML strings
content = content.replace(
    'Pushed CI Fix\\nURL: {pr_data.get(\'html_url\', pr.get(\'pr_url\', \'\'))}"',
    'Pushed CI Fix\\n" \\\n                                f"URL: {pr_data.get(\'html_url\', pr.get(\'pr_url\', \'\'))}"'
)
content = content.replace(
    'Pushed Code Fix\\nURL: {pr_data.get(\'html_url\', pr.get(\'pr_url\', \'\'))}"',
    'Pushed Code Fix\\n" \\\n                                f"URL: {pr_data.get(\'html_url\', pr.get(\'pr_url\', \'\'))}"'
)
content = content.replace(
    'Replied to comment\\nURL: {pr_data.get(\'html_url\', pr.get(\'pr_url\', \'\'))}"',
    'Replied to comment\\n" \\\n                                f"URL: {pr_data.get(\'html_url\', pr.get(\'pr_url\', \'\'))}"'
)
content = content.replace(
    'e to max CI retries ({self.MAX_CI_RETRIES}/{self.MAX_CI_RETRIES}) hit on {repo_url}"',
    'e to max CI retries " \\\n                f"({self.MAX_CI_RETRIES}/{self.MAX_CI_RETRIES}) hit on {repo_url}"'
)


with open('farm_agent/pr/patrol.py', 'w') as f:
    f.write(content)
