"""Test the farm_agent GitHub client directly"""
import os
os.environ['GITHUB_TOKEN'] = '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'
os.environ['MINIMAX_API_KEY'] = 'sk-cp-Z4G537Cg5j_dS3BMexXLL69tDq3V6ULdPHuUnMlk8dY-tYVY66oCRXGaXRN2qAOFrrLOAB9uyhOzm4PX7v-gLi8uu8LykVcQMeytB4IsD1upPW9v0zj4ETo'

import sys
sys.path.insert(0, r'C:\Users\USER\Documents\GitHub\ContribAI\farm_agent')

from github.client import GitHubClient

async def test():
    token = os.environ['GITHUB_TOKEN']
    client = GitHubClient(token)
    
    print("Testing farm_agent GitHubClient...")
    try:
        data = await client._get('/repos/hieuit095/Money-tree-tools')
        print(f"Success! Repo: {data.get('full_name', 'unknown')}")
        print(f"Stars: {data.get('stargazers_count', 'unknown')}")
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")
    finally:
        await client.close()

import asyncio
asyncio.run(test())
