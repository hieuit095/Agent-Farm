"""The Ruthless Janitor — scans and destroys garbage PRs.

Independent of the main pipeline. Operates purely on what is live
on GitHub right now. Uses Minimax LLM to evaluate each PR's title
and body; closes and deletes anything classified as GARBAGE.
"""

from __future__ import annotations

import json
import logging
import re

from farm_agent.github.client import GitHubClient
from farm_agent.llm.provider import MinimaxProvider
from farm_agent.core.config import LLMConfig

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a ruthless, highly critical Principal Software Engineer cleaning up spam PRs.\n"
    "Evaluate the provided PR Title and Body honestly.\n\n"
    "If the PR is ANY of the following, classify it as GARBAGE:\n"
    "1. Exploratory — title says 'understand', 'explore', 'read', 'investigate', 'look at', "
    "'see current', or anything that suggests the agent just wanted to look at code.\n"
    "2. Documentation — typo fixes, README updates, docstring improvements, comment changes.\n"
    "3. Formatting — whitespace, indentation, PEP8, Prettier, linting, styling changes.\n"
    "4. Low-impact — anything that is purely cosmetic, a renaming, a chore, or a refactor "
    "with no real logic or security fix.\n"
    "5. Test-only — adding/removing/modifying tests as the primary change.\n\n"
    "ONLY classify as CRITICAL if the PR is a REAL logic bug fix, a proven security vulnerability "
    "fix, a memory/leak/race-condition fix, or a critical architectural correction.\n\n"
    "Output EXACTLY this JSON (no extra text, no markdown):\n"
    '{"classification": "GARBAGE", "reason": "<one sentence reason>"}\n'
    "or\n"
    '{"classification": "CRITICAL", "reason": "<one sentence reason>"}\n'
)


class PRJanitor:
    """Scans open PRs and destroys garbage ones."""

    def __init__(self, github: GitHubClient, username: str, llm_config: LLMConfig, llm=None):
        self._github = github
        self._username = username
        # Use Minimax for LLM evaluation; allow override for testing
        self._llm = llm if llm is not None else MinimaxProvider(llm_config)

    async def _classify_pr(self, title: str, body: str) -> dict:
        """Ask LLM to classify a PR as GARBAGE or CRITICAL."""
        prompt = f"PR Title: {title}\n\nPR Body:\n{body or '(no body)'}"
        try:
            response = await self._llm.complete(prompt, system=SYSTEM_PROMPT, temperature=0.1)
            text = response.strip() if response else "{}"

            # Try to extract JSON from the response (handles markdown fences)
            text_clean = re.sub(r"```json\s*", "", text, flags=re.IGNORECASE)
            text_clean = re.sub(r"```\s*", "", text_clean)
            result = json.loads(text_clean)

            classification = result.get("classification", "GARBAGE").upper()
            reason = result.get("reason", "No reason provided.")
            if classification not in ("GARBAGE", "CRITICAL"):
                classification = "GARBAGE"
                reason = f"LLM returned unexpected classification: {classification}"
            return {"classification": classification, "reason": reason}

        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            logger.warning("Failed to parse LLM response for '%s': %s. Treating as GARBAGE.", title, exc)
            return {"classification": "GARBAGE", "reason": f"LLM parse error: {exc}"}
        except Exception as exc:
            logger.error("LLM call failed for '%s': %s. Treating as GARBAGE.", title, exc)
            return {"classification": "GARBAGE", "reason": f"LLM call failed: {exc}"}

    async def sweep_and_destroy(self) -> dict:
        """Fetch all open PRs, classify them, destroy garbage ones.

        Returns a summary dict:
        {
          "total_scanned": int,
          "garbage_closed": int,
          "critical_spared": int,
          "errors": int,
          "details": [{"pr": "#N owner/repo", "title": "...", "action": "closed|spared", "reason": "..."}]
        }
        """
        summary = {
            "total_scanned": 0,
            "garbage_closed": 0,
            "critical_spared": 0,
            "errors": 0,
            "details": [],
        }

        logger.info("Janitor starting sweep for user: %s", self._username)
        try:
            open_prs = await self._github.fetch_user_open_prs(self._username)
        except Exception as exc:
            logger.error("Failed to fetch open PRs: %s", exc)
            summary["errors"] = 1
            summary["details"].append({
                "pr": "",
                "title": "",
                "action": "error",
                "reason": f"Could not fetch open PRs: {exc}",
            })
            return summary

        if not open_prs:
            logger.info("No open PRs found for %s.", self._username)
            return summary

        logger.info("Found %d open PRs. Evaluating...", len(open_prs))

        for pr in open_prs:
            pr_number = pr["pr_number"]
            repo = pr["repo"]
            title = pr["title"]
            body = pr["body"]
            head_branch = pr.get("head_branch", "")
            summary["total_scanned"] += 1

            logger.info("  Evaluating #%d %s — %s", pr_number, repo, title)

            verdict = await self._classify_pr(title, body)
            classification = verdict["classification"]
            reason = verdict["reason"]

            if classification == "GARBAGE":
                logger.warning(
                    "  [%s] #%d %s/%s — DESTROYING: %s",
                    classification,
                    pr_number,
                    repo,
                    title,
                    reason,
                )
                try:
                    # Extract owner/repo parts
                    if "/" not in repo:
                        logger.error("  Cannot parse repo '%s', skipping close.", repo)
                        summary["errors"] += 1
                        continue

                    owner, repo_name = repo.split("/", 1)
                    await self._github.close_pull_request(
                        owner,
                        repo_name,
                        pr_number,
                        comment=(
                            "Automated Janitor: This PR was classified as GARBAGE "
                            f"and closed to protect account reputation.\n\n"
                            f"Reason: {reason}\n\n"
                            "This is an automated action by ContribAI Janitor."
                        ),
                    )
                    # Also delete the branch if we have a branch name
                    if head_branch:
                        try:
                            await self._github.delete_branch(owner, repo_name, head_branch)
                        except Exception as exc:
                            logger.debug("  Branch '%s' already gone or delete failed: %s", head_branch, exc)

                    summary["garbage_closed"] += 1
                    summary["details"].append({
                        "pr": f"#{pr_number} {repo}",
                        "title": title,
                        "action": "closed",
                        "reason": reason,
                    })
                except Exception as exc:
                    logger.error("  Failed to close PR #%d: %s", pr_number, exc)
                    summary["errors"] += 1
            else:
                logger.info(
                    "  [%s] #%d %s/%s — SPARED (critical): %s",
                    classification,
                    pr_number,
                    repo,
                    title,
                    reason,
                )
                summary["critical_spared"] += 1
                summary["details"].append({
                    "pr": f"#{pr_number} {repo}",
                    "title": title,
                    "action": "spared",
                    "reason": reason,
                })

        logger.info(
            "Janitor sweep complete: scanned=%d, destroyed=%d, spared=%d, errors=%d",
            summary["total_scanned"],
            summary["garbage_closed"],
            summary["critical_spared"],
            summary["errors"],
        )
        return summary
