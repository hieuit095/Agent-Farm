"""Debug httpx vs requests difference"""
import os
import httpx
import requests
import asyncio

async def test_httpx():
    token = os.environ.get('GITHUB_TOKEN', '')
    
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
    
    req = client.build_request('GET', '/repos/hieuit095/Money-tree-tools')
    print("httpx request headers:")
    for k, v in req.headers.items():
        if k.lower() not in ['authorization']:
            print(f"  {k}: {v}")
    print(f"  Authorization: Bearer {token[:5]}...")
    
    try:
        response = await client.get('/repos/hieuit095/Money-tree-tools')
        print(f"httpx Status: {response.status_code}")
    except httpx.HTTPError as e:
        print(f"httpx Error: {e}")
    finally:
        await client.aclose()

def test_requests():
    token = os.environ.get('GITHUB_TOKEN', '')
    
    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "git/2.43.0",
    })
    
    print("\nrequests session headers:")
    for k, v in session.headers.items():
        if k.lower() not in ['authorization']:
            print(f"  {k}: {v}")
    print(f"  Authorization: Bearer {token[:5]}...")
    
    response = session.get('https://api.github.com/repos/hieuit095/Money-tree-tools')
    print(f"requests Status: {response.status_code}")

asyncio.run(test_httpx())
test_requests()
