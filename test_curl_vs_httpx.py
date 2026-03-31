import os
os.environ['GITHUB_TOKEN'] = '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'

import httpx
import httpcore
import urllib3

print(f"httpx version: {httpx.__version__}")
print(f"httpcore version: {httpcore.__version__}")
print(f"urllib3 version: {urllib3.__version__}")
print(f"certifi version: {__import__('certifi').__version__}")

# Try with certifi CA bundle
import certifi

async def test_with_certifi():
    token = os.environ['GITHUB_TOKEN']
    
    # Create client with explicit CA bundle
    import ssl
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    
    client = httpx.AsyncClient(
        base_url='https://api.github.com',
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "git/2.43.0",
        },
        timeout=30.0,
        http2=False,
        verify=certifi.where(),
    )

    print(f"\nCA bundle: {certifi.where()}")
    print("Testing httpx with certifi CA bundle...")
    try:
        response = await client.get('/repos/hieuit095/Money-tree-tools')
        print(f"Status: {response.status_code}")
        if response.status_code != 200:
            print(f"Response: {response.text[:200]}")
    except httpx.HTTPError as e:
        print(f"httpx Error: {e}")
    finally:
        await client.aclose()

import asyncio
asyncio.run(test_with_certifi())
