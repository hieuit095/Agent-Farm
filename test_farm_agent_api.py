"""Test script that mimics farm_agent's GitHub API call"""
import os
import sys
import json

# Test direct API call with requests (mimicking farm_agent)
import requests

token = os.environ.get('GITHUB_TOKEN', '')
print(f"Token from env: {token[:10]}..." if token else "No token!")
print(f"Token length: {len(token)}")

# Mimic farm_agent's request headers
headers = {
    'Accept': 'application/vnd.github+json',
    'Authorization': f'Bearer {token}',
    'X-GitHub-Api-Version': '2022-11-28',
}

session = requests.Session()
session.headers.update(headers)

print("\nMaking GET /repos/hieuit095/Money-tree-tools...")
r = session.get('https://api.github.com/repos/hieuit095/Money-tree-tools')
print(f"Status: {r.status_code}")
print(f"Rate limit remaining: {r.headers.get('x-ratelimit-remaining', 'N/A')}")
print(f"Content-Type: {r.headers.get('Content-Type', 'N/A')[:50]}")
if r.status_code != 200:
    print(f"Response: {r.text[:500]}")
