"""Test httpx request mimicking farm_agent's GitHub client"""
import os
import httpx
import asyncio

async def test():
    token = os.environ.get('GITHUB_TOKEN', '')
    print(f"Token: {token[:10]}...")

    client = httpx.AsyncClient(
        base_url='https://api.github.com',
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "git/2.43.0",
        },
        timeout=30.0,
    )

    print("\nMaking GET /repos/hieuit095/Money-tree-tools (async)...")
    try:
        response = await client.get('/repos/hieuit095/Money-tree-tools')
        print(f"Status: {response.status_code}")
        print(f"Rate limit remaining: {response.headers.get('x-ratelimit-remaining', 'N/A')}")
        print(f"Content-Type: {response.headers.get('Content-Type', 'N/A')[:50]}")
        if response.status_code != 200:
            print(f"Response: {response.text[:500]}")
    except httpx.HTTPError as e:
        print(f"HTTP Error: {e}")
    finally:
        await client.aclose()

asyncio.run(test())
