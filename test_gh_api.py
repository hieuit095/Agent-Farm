import requests
r = requests.get(
    'https://api.github.com/repos/hieuit095/Money-tree-tools',
    headers={'Authorization': 'token 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'}
)
print('Status:', r.status_code)
print('Rate limit remaining:', r.headers.get('x-ratelimit-remaining', 'N/A'))
print('Content type:', r.headers.get('Content-Type', 'N/A'))
