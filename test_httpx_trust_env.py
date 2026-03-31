import os
os.environ['GITHUB_TOKEN'] = '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'

import httpx
import asyncio

async def test():
    token = os.environ['GITHUB_TOKEN']
    
    # Try with trust_env=False to ignore environment proxy settings
    # Also try with no explicit verify to use system default
    client = httpx.AsyncClient(
        base_url='https://api.github.com',
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        },
        timeout=30.0,
        trust_env=False,
    )

    print("Testing httpx with trust_env=False and browser-like UA...")
    try:
        response = await client.get('/repos/hieuit095/Money-tree-tools')
        print(f"httpx Status: {response.status_code}")
        print(f"Rate limit remaining: {response.headers.get('x-ratelimit-remaining', 'N/A')}")
        if response.status_code != 200:
            print(f"Response: {response.text[:200]}")
    except httpx.HTTPError as e:
        print(f"httpx Error: {e}")
    finally:
        await client.aclose()

asyncio.run(test())
