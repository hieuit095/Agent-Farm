from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from contribai.core.config import load_config
from contribai.core.exceptions import GitHubAPIError
from contribai.github.client import GitHubClient

CI_TRAP_PATH = ".github/workflows/ci-trap.yml"
CI_TRAP_CONTENT = """name: CI Trap
on: [pull_request]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: The Deliberate Failure
        run: |
          echo "Simulating a build failure..."
          echo "Traceback (most recent call last):"
          echo "  File 'src/index.ts', line 42, in <module>"
          echo "TypeError: Cannot read properties of undefined (reading 'config')"
          exit 1
"""


async def inject_ci_trap(config_path: str, owner: str, repo: str, branch: str) -> None:
    config = load_config(config_path)
    github = GitHubClient(
        token=config.github.token,
        rate_limit_buffer=config.github.rate_limit_buffer,
    )

    sha: str | None = None
    action = "created"
    try:
        try:
            existing = await github._get(
                f"/repos/{owner}/{repo}/contents/{CI_TRAP_PATH}",
                params={"ref": branch},
            )
            sha = existing.get("sha")
            if sha:
                action = "updated"
        except GitHubAPIError as exc:
            if exc.status_code != 404:
                raise

        await github.create_or_update_file(
            owner,
            repo,
            CI_TRAP_PATH,
            CI_TRAP_CONTENT,
            message="ci: add deliberate failing pull_request workflow",
            branch=branch,
            sha=sha,
        )

        file_url = f"https://github.com/{owner}/{repo}/blob/{branch}/{CI_TRAP_PATH}"
        raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/{CI_TRAP_PATH}"
        print(f"CI_TRAP_{action.upper()}=1")
        print(f"CI_TRAP_FILE_URL={file_url}")
        print(f"CI_TRAP_RAW_URL={raw_url}")
    finally:
        await github.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Inject a failing CI trap workflow into a repo")
    parser.add_argument(
        "--config",
        default="logs/config.auto_healing.yaml",
        help="Path to ContribAI YAML config with GitHub token",
    )
    parser.add_argument("--owner", default="hieuit095")
    parser.add_argument("--repo", default="gitvisualizer-ai")
    parser.add_argument("--branch", default="main")
    args = parser.parse_args()

    config_path = str(Path(args.config))
    asyncio.run(inject_ci_trap(config_path, args.owner, args.repo, args.branch))


if __name__ == "__main__":
    main()
