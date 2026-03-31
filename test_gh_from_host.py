"""Test GitHub API from host using farm_agent's httpx client"""
import os
import sys
sys.path.insert(0, r'C:\Users\USER\Documents\GitHub\ContribAI\src')

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

    print("\nMaking GET /repos/hieuit095/Money-tree-tools...")
    try:
        response = await client.get('/repos/hieuit095/Money-tree-tools')
        print(f"Status: {response.status_code}")
        print(f"Rate limit remaining: {response.headers.get('x-ratelimit-remaining', 'N/A')}")
    except httpx.HTTPError as e:
        print(f"Error: {e}")
    finally:
        await client.aclose()

asyncio.run(test())
