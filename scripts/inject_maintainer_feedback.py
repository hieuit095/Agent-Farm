from __future__ import annotations

import argparse
import asyncio
import json
import re

import httpx

from contribai.core.config import load_config


def _pick_review_line(patch: str) -> int | None:
    """Pick the first added line number from a unified diff patch."""
    right_line = None

    for raw_line in patch.splitlines():
        if raw_line.startswith("@@"):
            match = re.search(r"\+(\d+)", raw_line)
            right_line = int(match.group(1)) if match else None
            continue

        if right_line is None:
            continue

        if raw_line.startswith("+") and not raw_line.startswith("+++"):
            return right_line

        if raw_line.startswith("-") and not raw_line.startswith("---"):
            continue

        right_line += 1

    return None


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inject a maintainer-style inline review comment into a live PR.",
    )
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--repo", required=True, help="owner/repo")
    parser.add_argument("--pr", required=True, type=int, help="PR number")
    parser.add_argument(
        "--body",
        default=(
            "[CONTROLLED_TEST] I don't like this naming convention. "
            "Please rename the variable to something more descriptive."
        ),
        help="Review comment body",
    )
    args = parser.parse_args()

    owner, repo = args.repo.split("/", 1)
    cfg = load_config(args.config)
    headers = {
        "Authorization": f"Bearer {cfg.github.token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    async with httpx.AsyncClient(
        base_url="https://api.github.com",
        headers=headers,
        timeout=30.0,
    ) as client:
        pr_resp = await client.get(f"/repos/{owner}/{repo}/pulls/{args.pr}")
        pr_resp.raise_for_status()
        pr_data = pr_resp.json()
        head_sha = pr_data["head"]["sha"]

        files_resp = await client.get(f"/repos/{owner}/{repo}/pulls/{args.pr}/files")
        files_resp.raise_for_status()
        files = files_resp.json()

        target = None
        for file_info in files:
            patch = file_info.get("patch") or ""
            line = _pick_review_line(patch)
            if not patch or line is None:
                continue
            target = {
                "path": file_info["filename"],
                "line": line,
            }
            break

        if target is None:
            raise RuntimeError("Could not find a diff line suitable for an inline review comment")

        body = args.body
        if "[CONTROLLED_TEST]" not in body:
            body = f"[CONTROLLED_TEST] {body}"

        payload = {
            "body": body,
            "commit_id": head_sha,
            "path": target["path"],
            "line": target["line"],
            "side": "RIGHT",
        }
        comment_resp = await client.post(
            f"/repos/{owner}/{repo}/pulls/{args.pr}/comments",
            json=payload,
        )
        comment_resp.raise_for_status()
        comment = comment_resp.json()

    print(
        json.dumps(
            {
                "repo": args.repo,
                "pr": args.pr,
                "comment_id": comment["id"],
                "path": target["path"],
                "line": target["line"],
                "html_url": comment["html_url"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
