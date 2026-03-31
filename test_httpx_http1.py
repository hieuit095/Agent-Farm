"""Test httpx with HTTP/1.1"""
import os
import httpx
import asyncio

async def test():
    token = os.environ.get('GITHUB_TOKEN', '')
    
    # Try HTTP/1.1 explicitly
    client = httpx.AsyncClient(
        base_url='https://api.github.com',
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "git/2.43.0",
        },
        timeout=30.0,
        http2=False,  # Force HTTP/1.1
    )
    
    print("Testing with HTTP/1.1...")
    try:
        response = await client.get('/repos/hieuit095/Money-tree-tools')
        print(f"HTTP/1.1 Status: {response.status_code}")
        print(f"Rate limit remaining: {response.headers.get('x-ratelimit-remaining', 'N/A')}")
    except httpx.HTTPError as e:
        print(f"HTTP/1.1 Error: {e}")
    finally:
        await client.aclose()

asyncio.run(test())
