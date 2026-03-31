import os
os.environ['GITHUB_TOKEN'] = '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'
os.environ['MINIMAX_API_KEY'] = 'sk-cp-Z4G537Cg5j_dS3BMexXLL69tDq3V6ULdPHuUnMlk8dY-tYVY66oCRXGaXRN2qAOFrrLOAB9uyhOzm4PX7v-gLi8uu8LykVcQMeytB4IsD1upPW9v0zj4ETo'

import httpx
import asyncio

async def test():
    token = os.environ['GITHUB_TOKEN']
    
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

    print("Testing httpx from Windows host...")
    try:
        response = await client.get('/repos/hieuit095/Money-tree-tools')
        print(f"httpx Status: {response.status_code}")
        print(f"Rate limit remaining: {response.headers.get('x-ratelimit-remaining', 'N/A')}")
        if response.status_code != 200:
            print(f"Response: {response.text[:500]}")
    except httpx.HTTPError as e:
        print(f"httpx Error: {e}")
    finally:
        await client.aclose()

asyncio.run(test())
