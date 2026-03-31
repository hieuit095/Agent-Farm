import os
os.environ['GITHUB_TOKEN'] = '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'

# Try using wininet directly via ctypes
import ctypes
import json

print("Testing WinHTTP directly...")
token = os.environ['GITHUB_TOKEN']

# WinHTTP constants
WINHTTP_ACCESS_TYPE_DEFAULT_PROXY = 0
WINHTTP_FLAG_SECURE = 0x00800000
HTTP_QUERY_STATUS_CODE = 19
HTTP_QUERY_RAW_HEADERS_CRLF = 22

# Try a simple urllib3 request with Windows certificate store
import urllib3
urllib3.disable_warnings()

pool = urllib3.PoolManager(
    num_pools=1,
    cert_reqs='CERT_REQUIRED',
    ca_certs=None,  # Use system CA certs on Windows
)

try:
    response = pool.request(
        'GET',
        'https://api.github.com/repos/hieuit095/Money-tree-tools',
        headers={
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28',
        }
    )
    print(f"urllib3 Status: {response.status}")
    print(f"Rate limit: {response.headers.get('x-ratelimit-remaining', 'N/A')}")
except Exception as e:
    print(f"urllib3 Error: {e}")
