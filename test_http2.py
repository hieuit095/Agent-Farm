import os
os.environ['GITHUB_TOKEN'] = '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'

import httpx
import asyncio

async def test_http1_only():
    token = os.environ['GITHUB_TOKEN']
    
    # Explicitly disable HTTP/2
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
    )

    print("Testing httpx HTTP/1.1 only from Windows host...")
    try:
        response = await client.get('/repos/hieuit095/Money-tree-tools')
        print(f"httpx HTTP/1.1 Status: {response.status_code}")
        print(f"Rate limit remaining: {response.headers.get('x-ratelimit-remaining', 'N/A')}")
        if response.status_code != 200:
            print(f"Response: {response.text[:300]}")
    except httpx.HTTPError as e:
        print(f"httpx Error: {e}")
    finally:
        await client.aclose()

asyncio.run(test_http1_only())
