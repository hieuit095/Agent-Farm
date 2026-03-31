import os
os.environ['GITHUB_TOKEN'] = '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'

import requests

token = os.environ['GITHUB_TOKEN']
session = requests.Session()
session.headers.update({
    "Authorization": f"token {token}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "git/2.43.0",
})

print("Testing requests from Windows host...")
r = session.get('https://api.github.com/repos/hieuit095/Money-tree-tools')
print(f"requests Status: {r.status_code}")
print(f"Rate limit remaining: {r.headers.get('x-ratelimit-remaining', 'N/A')}")
