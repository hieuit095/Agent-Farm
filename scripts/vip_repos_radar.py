#!/usr/bin/env python3
"""
VIP Repos Radar
Audits your GitHub success rate by finding all merged PRs in repositories with >1000 stars.
"""

import asyncio
import os
import sys
from pathlib import Path

import httpx
import yaml
from dotenv import load_dotenv


# Configuration
CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"
GITHUB_API_BASE = "https://api.github.com"
RATE_LIMIT_DELAY = 0.5  # seconds between API calls to avoid rate limiting
STAR_THRESHOLD = 1000


def load_config() -> dict:
    """Load configuration from config.yaml."""
    if not CONFIG_PATH.exists():
        print(f"ERROR: config.yaml not found at {CONFIG_PATH}")
        sys.exit(1)

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    github_config = config.get("github", {})
    token = github_config.get("token", "")

    # Fall back to GITHUB_TOKEN environment variable if token is empty
    if not token:
        token = os.environ.get("GITHUB_TOKEN", "")

    if not token:
        print("ERROR: No GitHub token found in config.yaml or GITHUB_TOKEN env var")
        sys.exit(1)

    return token


def create_headers(token: str) -> dict:
    """Create HTTP headers for GitHub API requests."""
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


async def search_merged_prs(client: httpx.AsyncClient, headers: dict) -> list[dict]:
    """Search for all merged PRs by the authenticated user."""
    print("Searching for merged PRs...")

    all_prs = []
    page = 1
    per_page = 100

    while True:
        search_url = f"{GITHUB_API_BASE}/search/issues"
        params = {
            "q": "is:pr is:merged author:@me",
            "per_page": per_page,
            "page": page,
            "sort": "updated",
            "order": "desc",
        }

        response = await client.get(search_url, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()

        items = data.get("items", [])
        if not items:
            break

        all_prs.extend(items)

        # Check if we've reached the last page
        if len(items) < per_page:
            break

        page += 1
        await asyncio.sleep(RATE_LIMIT_DELAY)

    print(f"Found {len(all_prs)} merged PRs total")
    return all_prs


async def fetch_repo_stars(client: httpx.AsyncClient, headers: dict, repo_name: str) -> int | None:
    """Fetch star count for a repository."""
    url = f"{GITHUB_API_BASE}/repos/{repo_name}"

    try:
        response = await client.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            return data.get("stargazers_count", 0)
        elif response.status_code == 404:
            return None
        else:
            return None
    except Exception:
        return None


async def get_vip_repos(client: httpx.AsyncClient, headers: dict, prs: list[dict]) -> list[dict]:
    """Extract unique repos and filter those with >1000 stars."""
    # Extract unique repo names
    repo_names = set()
    for pr in prs:
        repo_url = pr.get("repository_url", "")
        if repo_url:
            # Extract owner/repo from the full URL
            parts = repo_url.rstrip("/").split("/")
            if len(parts) >= 2:
                owner = parts[-2]
                repo = parts[-1]
                repo_names.add(f"{owner}/{repo}")

    print(f"\nFound {len(repo_names)} unique repositories, checking star counts...")

    vip_repos = []
    total = len(repo_names)

    for i, repo_name in enumerate(sorted(repo_names), 1):
        stars = await fetch_repo_stars(client, headers, repo_name)
        await asyncio.sleep(RATE_LIMIT_DELAY)

        if stars is not None and stars > STAR_THRESHOLD:
            # Find the PR URLs for this repo
            pr_urls = []
            for pr in prs:
                repo_url = pr.get("repository_url", "")
                if repo_url.endswith(f"/{repo_name.split('/')[-1]}"):
                    pr_urls.append(pr.get("html_url", ""))

            vip_repos.append({
                "name": repo_name,
                "stars": stars,
                "pr_urls": pr_urls,
            })
            print(f"  [{i}/{total}] {repo_name}: {stars} stars")

        if i % 10 == 0:
            print(f"  Progress: {i}/{total} repos checked...")

    return vip_repos


def display_results(vip_repos: list[dict]) -> None:
    """Display the VIP repositories with rich formatting."""
    if not vip_repos:
        print("\nNo repositories with >1000 stars found.")
        return

    # Sort by star count descending
    vip_repos.sort(key=lambda x: x["stars"], reverse=True)

    print("\n" + "=" * 80)
    print("VIP REPOSITORIES (>1000 STARS) WITH SUCCESSFULLY MERGED PRs")
    print("=" * 80)
    print()

    total_stars = sum(r["stars"] for r in vip_repos)
    print(f"Found {len(vip_repos)} VIP repositories with a total of {total_stars:,} stars!")
    print()

    for repo in vip_repos:
        print(f"\n[{repo['stars']:,} stars] {repo['name']}")
        print("-" * 60)
        for pr_url in repo["pr_urls"]:
            print(f"  - {pr_url}")

    print("\n" + "=" * 80)


async def main():
    """Main execution function."""
    # Load environment variables from .env file first
    load_dotenv()

    print("=" * 80)
    print("VIP REPOS RADAR - GitHub Success Rate Audit")
    print("=" * 80)
    print()

    # Step 1: Load configuration
    token = load_config()
    headers = create_headers(token)

    # Step 2: Create async HTTP client
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Step 3: Search for merged PRs
        prs = await search_merged_prs(client, headers)

        if not prs:
            print("\nNo merged PRs found.")
            return

        # Step 4: Find VIP repos with >1000 stars
        vip_repos = await get_vip_repos(client, headers, prs)

    # Step 5: Display results
    display_results(vip_repos)


if __name__ == "__main__":
    asyncio.run(main())
