"""PR Patrol — monitor and respond to review feedback on open PRs.

Scans Farm-Agent PRs for maintainer review comments, uses LLM to
classify feedback, generates code fixes, and pushes updates.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import random
import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import yaml

from farm_agent.core.exceptions import GitHubAPIError
from farm_agent.core.models import (
    ContributionType,
    FeedbackAction,
    FeedbackItem,
    PatrolResult,
)
from farm_agent.core.sandbox import DockerSandbox
from farm_agent.github.client import GitHubClient
from farm_agent.llm.provider import LLMProvider

logger = logging.getLogger(__name__)

_AUTO_FIXABLE_PR_TYPES = {kind.value for kind in ContributionType if kind != ContributionType.SECURITY_FIX}

# Comments we already posted — skip these
OUR_REPLY_MARKERS = [
    "I have read the CLA Document",
    "farm_agent",
    "<!-- farm_agent-patrol -->",
]

# ── Human Developer Persona ────────────────────────────────────────────────
# Randomized natural English phrases for all GitHub interactions.
# This is the soul of "Super Human Mode" — no bot should ever
# sound like a bot.  Every reply picks a variant via random.choice().

GITHUB_REPLIES: dict[str, list[str]] = {
    # After pushing a code fix in response to review feedback
    "FIX_APPLIED": [
        "Good catch, updated.",
        "Fixed in latest commit.",
        "Done, pushed the fix.",
        "Addressed — pushed.",
        "Updated.",
        "Pushed. Let me know.",
    ],
    # Commit messages for code fixes
    "COMMIT_FIX": [
        "fix: {summary}",
        "fix: review feedback — {summary}",
        "fix: address reviewer comment",
    ],
    # Prepended to LLM-generated question answers
    "QUESTION_OPENER": [
        "Yeah,",
        "Sure,",
        "Fair point,",
    ],
    # Appended to LLM-generated question answers
    "QUESTION_CLOSER": [
        "lmk if that works.",
        "hope that makes sense.",
        "let me know if you need more detail.",
    ],
    # When closing a PR due to hostile rejection
    "HOSTILE_CLOSE": [
        "Understood, closing this PR. Won't target this repo again.",
        "Fair enough, closing now.",
        "Got it, closing.",
    ],
    # Comment after pushing a CI fix
    "CI_FIX_APPLIED": [
        "`{check_name}` was failing — pushed a fix for `{file_path}`.",
        "Spotted the `{check_name}` failure and patched `{file_path}`.",
        "Fixed `{check_name}` failure in `{file_path}`.",
    ],
    # When closing PR after exhausting CI fix attempts
    "CI_LIMIT_CLOSE": [
        "CI still failing after {attempts} attempts. Closing to avoid noise.",
        "Couldn't get CI green after {attempts} tries. Closing.",
    ],
    # Surrender: max discussion retries reached
    "SURRENDER": [
        "Can't seem to get this right after a few tries. Closing so I don't pile on. Thanks for the reviews.",  # noqa: E501
        "Taking this as a signal I'm off base here. Closing — thanks for the feedback.",
    ],
    # Commit messages for CI fixes
    "COMMIT_CI_FIX": [
        "fix: resolve {check_name} CI failure",
        "fix: address failing {check_name} check",
        "fix: patch {check_name} error",
    ],
}

# Review bot logins to ignore (they look like users but are bots)
REVIEW_BOT_LOGINS = {
    "coderabbitai",
    "copilot",
    "github-actions",
    "dependabot",
    "renovate",
    "sweep-ai",
    "sourcery-ai",
    "codeclimate",
    "sonarcloud",
    "codecov",
    "deepsource-autofix",
}

CONTROLLED_TEST_MARKER = "[CONTROLLED_TEST]"

# CI check names and log patterns that indicate infrastructure/auth failures
# that CANNOT be fixed via code changes.  The bot must skip these.
# P1-OPSEC-3: Exact names (no substring false-positives) + prefix matches for namespaced bots
CI_INFRA_IGNORE_NAMES: frozenset[str] = {
    "vercel",
    "netlify",
    "codecov",
    "cloudflare",
    "pages",
    "cla-bot",
    "license-check",
}
CI_INFRA_IGNORE_PREFIXES: tuple[str, ...] = (
    "vercel/",
    "netlify/",
    "codecov/",
    "cla/",
    "license/",
)
CI_INFRA_IGNORE_PATTERNS: list[str] = [
    # Deployment preview services (require manual auth for fork PRs)
    # Missing credentials / secrets
    "no existing credentials found",
    "unauthorized",
    "authorization required",
    "missing secret",
    "secrets.",
    # Coverage-only checks (not fixable via code)
    "coverage",
]


class PRPatrol:
    """Monitor open PRs and respond to maintainer feedback."""

    def __init__(
        self,
        github: GitHubClient,
        llm: LLMProvider,
        memory=None,
        **kwargs,
    ):
        self._github = github
        self._llm = llm
        self._memory = memory
        self._notifier = kwargs.get("notifier")
        self._enable_sandbox_validation = kwargs.get(
            "enable_sandbox_validation",
            isinstance(github, GitHubClient),
        )
        self._sandbox_factory = kwargs.get("sandbox_factory", DockerSandbox)
        self._user: dict | None = None
        # Configurable safety limits — navigate validated Pydantic config path
        config = kwargs.get("config")
        pipeline_cfg = getattr(config, "pipeline", None) if config else None
        self.MAX_CI_RETRIES = getattr(pipeline_cfg, "max_ci_retries", 3) if pipeline_cfg else 3
        self.MAX_DISCUSSION_REPLIES = getattr(pipeline_cfg, "max_discussion_replies", 3) if pipeline_cfg else 3

    def _create_sandbox(self) -> DockerSandbox:
        """Create a sandbox instance for local validation."""
        return self._sandbox_factory()

    async def _get_user(self) -> dict:
        if not self._user:
            self._user = await self._github.get_authenticated_user()
        return self._user

    def _calculate_typing_delay(self, text_payload: str) -> int:
        """WPM Simulator: Calculate realistic typing delay based on payload size.

        Capped at 120 seconds to prevent the SuperHumanLoop from freezing
        on large payloads (unicode, long diffs, etc.).
        """
        base_delay = random.randint(30, 90)
        typing_time = len(text_payload) / 3.75
        return int(min(base_delay + typing_time, 120))

    def _get_contextual_greeting(self) -> str:
        """Contextual Small Talk: Day-of-the-week greetings in UTC."""
        from datetime import datetime
        now = datetime.now(UTC)
        if now.hour >= 12 and now.weekday() == 4:
            return random.choice(["Happy Friday! ", "Hope you have a great weekend ahead. "])
        elif now.hour < 12 and now.weekday() == 0:
            return random.choice(["Hope you had a good weekend! ", "Happy Monday! "])
        return ""

    @staticmethod
    def _is_controlled_test_feedback(body: str) -> bool:
        return CONTROLLED_TEST_MARKER in body

    def _build_signoff(self, user: dict) -> str | None:
        """Build DCO Signed-off-by string from user info."""
        name = user.get("name") or user.get("login", "")
        email = user.get("email")
        if not email:
            uid = user.get("id", "")
            login = user.get("login", "")
            email = f"{uid}+{login}@users.noreply.github.com"
        return f"{name} <{email}>" if name else None

    async def patrol(
        self,
        pr_records: list[dict],
        *,
        dry_run: bool = False,
        pr_filter: int | None = None,
    ) -> PatrolResult:
        """Main entry: scan open PRs for pending feedback.

        Args:
            pr_records: PR records from memory DB
            dry_run: If True, don't push fixes or reply
            pr_filter: If set, only check this specific PR number
        """
        result = PatrolResult()
        user = await self._get_user()
        username = user["login"]

        for pr in pr_records:
            if pr.get("status") not in ("open", "pending", "review_requested"):
                result.prs_skipped += 1
                continue

            if pr_filter and pr["pr_number"] != pr_filter:
                continue

            try:
                owner, repo_name = pr["repo"].split("/", 1)

                # Check live status first
                pr_data = await self._github._get(
                    f"/repos/{owner}/{repo_name}/pulls/{pr['pr_number']}"
                )
                if pr_data.get("state") != "open":
                    result.prs_skipped += 1
                    continue

                # Detect merged PRs
                if pr_data.get("merged") is True:
                    logger.info(
                        "  🎉 PR #%d on %s is MERGED — updating status",
                        pr["pr_number"],
                        pr["repo"],
                    )
                    result.prs_merged.append({
                        "repo": pr["repo"],
                        "pr_number": pr["pr_number"],
                        "url": pr_data.get("html_url", pr.get("pr_url", "")),
                    })
                    if self._memory:
                        await self._memory.update_pr_status(
                            pr["repo"], pr["pr_number"], "merged",
                        )
                    # Clean up the branch from the fork
                    head_node = pr_data.get("head", {})
                    branch_name = head_node.get("ref")
                    fork_owner = head_node.get("repo", {}).get("owner", {}).get("login")
                    fork_repo = head_node.get("repo", {}).get("name")
                    if branch_name and fork_owner and fork_repo:
                        try:
                            await self._github.delete_branch(fork_owner, fork_repo, branch_name)
                        except Exception as exc:
                            logger.warning(
                                "  ⚠️ Could not delete branch %s on %s/%s: %s",
                                branch_name, fork_owner, fork_repo, exc,
                            )
                    continue

                result.prs_checked += 1
                logger.info(
                    "🔍 Checking PR #%d on %s: %s",
                    pr["pr_number"],
                    pr["repo"],
                    pr.get("title", "")[:60],
                )

                # ── CI Auto-Healing: check for failed CI runs ───────────
                head_sha = pr_data.get("head", {}).get("sha", "")
                if head_sha:
                    ci_handled = await self._check_ci_failures(
                        owner, repo_name, pr, pr_data, head_sha, result, dry_run=dry_run,
                    )
                    if ci_handled:
                        if self._notifier and not dry_run:
                            await self._notifier.send_message(
                                f"🛡️ <b>[PATROL]</b> Action Taken!\nRepo: <code>{pr['repo']}</code>\nAction: Pushed CI Fix\nURL: {pr_data.get('html_url', pr.get('pr_url', ''))}"
                            )
                        continue  # skip human feedback this cycle

                # Gather all feedback
                feedback = await self._collect_feedback(owner, repo_name, pr["pr_number"], username)

                if not feedback:
                    logger.info("  ✅ No pending feedback on PR #%d", pr["pr_number"])
                    continue

                # Classify feedback via LLM
                classified = await self._classify_feedback(feedback)

                # ── Hostile rejection: close PR and blacklist repo ──────
                hostile = [
                    f for f in classified if f.action == FeedbackAction.HOSTILE_REJECT
                ]
                if hostile:
                    reason = hostile[0].body[:500]
                    logger.warning(
                        "  🚨 HOSTILE rejection on PR #%d (%s): %s",
                        pr["pr_number"],
                        pr["repo"],
                        reason[:120],
                    )
                    if not dry_run:
                        # Close the PR with an apology
                        try:
                            await self._github.close_pull_request(
                                owner,
                                repo_name,
                                pr["pr_number"],
                                comment=random.choice(GITHUB_REPLIES["HOSTILE_CLOSE"]),
                            )
                        except GitHubAPIError as exc:
                            logger.warning(
                                "  ⚠️ Could not close PR #%d (repo may be deleted): %s",
                                pr["pr_number"],
                                exc,
                            )
                        # Blacklist the repo permanently
                        if self._memory:
                            await self._memory.blacklist_repo(
                                owner, repo_name, reason, pr["pr_number"]
                            )
                        if self._notifier:
                            await self._notifier.send_message(
                                f"⛔ <b>[ALERT]</b> Hostile maintainer detected. Repo <code>{pr['repo']}</code> blacklisted."
                            )
                    result.prs_closed_hostile += 1
                    continue

                # ── Normal reject: skip without closing ────────────────
                rejected = [f for f in classified if f.action == FeedbackAction.REJECT]

                if rejected:
                    logger.info(
                        "  🚫 PR #%d rejected by maintainer — skipping",
                        pr["pr_number"],
                    )
                    continue

                # ── Actionable feedback ─────────────────────────────────
                actionable = [
                    f
                    for f in classified
                    if f.action
                    in (
                        FeedbackAction.CODE_CHANGE,
                        FeedbackAction.STYLE_FIX,
                        FeedbackAction.QUESTION,
                    )
                ]

                if not actionable:
                    logger.info(
                        "  ✅ All feedback on PR #%d already handled or approved",
                        pr["pr_number"],
                    )
                    continue

                logger.info(
                    "  📋 %d actionable item(s) on PR #%d",
                    len(actionable),
                    pr["pr_number"],
                )

                # ── Layer 2: Killswitch ─ discussion reply limit ──────
                reply_count = 0
                if self._memory:
                    reply_count = await self._memory.get_discussion_replies(
                        pr["repo"], pr["pr_number"],
                    )
                if reply_count >= self.MAX_DISCUSSION_REPLIES:
                    logger.warning(
                        "  🏳️ Discussion reply limit (%d) reached for PR #%d — surrendering",
                        self.MAX_DISCUSSION_REPLIES, pr["pr_number"],
                    )
                    if not dry_run:
                        if random.random() < 0.10:
                            # BEHV-02 fix: actively close the PR instead of ghosting
                            logger.warning(
                                "  👻 Chán cãi nhau rồi, bơ luôn PR #%d. (Ghosting the maintainer)",
                                pr["pr_number"],
                            )
                            try:
                                await self._github.close_pull_request(
                                    owner,
                                    repo_name,
                                    pr["pr_number"],
                                    comment="Closing this PR for now as I won't have time to address the remaining feedback. Thanks for the review!",
                                )
                            except GitHubAPIError as exc:
                                logger.warning(
                                    "  ⚠️ Could not close PR #%d: %s", pr["pr_number"], exc,
                                )
                            if self._memory:
                                await self._memory.update_pr_status(pr["repo"], pr["pr_number"], "ghosted")
                            result.prs_closed_hostile += 1
                            continue

                        try:
                            await self._github.close_pull_request(
                                owner, repo_name, pr["pr_number"],
                                comment=random.choice(GITHUB_REPLIES["SURRENDER"]),
                            )
                        except GitHubAPIError as exc:
                            logger.warning(
                                "  ⚠️ Could not close PR #%d: %s", pr["pr_number"], exc,
                            )
                        if self._notifier:
                            repo_url = pr_data.get(
                                "html_url", f"https://github.com/{pr['repo']}",
                            )
                            await self._notifier.send_message(
                                f"🏳️ [SURRENDER] PR closed due to max retries "
                                f"({self.MAX_DISCUSSION_REPLIES}/{self.MAX_DISCUSSION_REPLIES}) "
                                f"hit on {repo_url}"
                            )
                    result.prs_closed_hostile += 1
                    continue

                for item in actionable:
                    if dry_run:
                        logger.info(
                            "  [DRY RUN] Would %s: %s",
                            item.action.value,
                            item.body[:80],
                        )
                        continue

                    # ── Auto-Like: acknowledge receipt like a human dev ──
                    # A real contributor typically reacts with 👍 immediately
                    # to signal "I saw this" before spending time on the fix.
                    with contextlib.suppress(Exception):
                        await self._github.add_comment_reaction(
                            owner,
                            repo_name,
                            item.comment_id,
                            is_review_comment=item.is_inline,
                        )

                    if item.action in (
                        FeedbackAction.CODE_CHANGE,
                        FeedbackAction.STYLE_FIX,
                    ):
                        fixed = await self._handle_code_fix(owner, repo_name, pr, pr_data, item, dry_run=dry_run)
                        if fixed:
                            result.fixes_pushed += 1
                            result.replies_sent += 1
                            if self._memory:
                                await self._memory.increment_discussion_replies(
                                    pr["repo"], pr["pr_number"],
                                )
                            if self._notifier and not dry_run:
                                await self._notifier.send_message(
                                    f"🛡️ <b>[PATROL]</b> Action Taken!\nRepo: <code>{pr['repo']}</code>\nAction: Pushed Code Fix\nURL: {pr_data.get('html_url', pr.get('pr_url', ''))}"
                                )
                    elif item.action == FeedbackAction.QUESTION:
                        answered = await self._handle_question(owner, repo_name, pr, pr_data, item, dry_run=dry_run)
                        if answered:
                            result.replies_sent += 1
                            if self._memory:
                                await self._memory.increment_discussion_replies(
                                    pr["repo"], pr["pr_number"],
                                )
                            if self._notifier and not dry_run:
                                await self._notifier.send_message(
                                    f"🛡️ <b>[PATROL]</b> Action Taken!\nRepo: <code>{pr['repo']}</code>\nAction: Replied to comment\nURL: {pr_data.get('html_url', pr.get('pr_url', ''))}"
                                )

                # Re-check CLA after pushing fixes
                if result.fixes_pushed > 0 and not dry_run:
                    cla_done = await self._handle_cla_recheck(owner, repo_name, pr["pr_number"])
                    if cla_done:
                        result.cla_signed += 1

            except Exception as e:
                error_msg = f"Error patrolling PR #{pr.get('pr_number')}: {e}"
                logger.error("  ❌ %s", error_msg)
                result.errors.append(error_msg)

        # ── Check assigned issues across repos ─────────────────────────────
        seen_repos = {pr["repo"] for pr in pr_records if "/" in pr.get("repo", "")}
        await self._check_assigned_issues(seen_repos, username, result, dry_run=dry_run)

        return result

    async def _check_assigned_issues(
        self,
        repos: set[str],
        username: str,
        result: PatrolResult,
        *,
        dry_run: bool = False,
    ) -> None:
        """Check repos for issues assigned to us.

        Scans each unique repo we've contributed to for open issues
        assigned to our username. Logs them and stores in result.
        """
        if not repos:
            return

        logger.info("📌 Checking %d repo(s) for assigned issues...", len(repos))

        for repo_full in repos:
            try:
                owner, repo_name = repo_full.split("/", 1)
                issues = await self._github.get_assigned_issues(owner, repo_name, username)

                for issue in issues:
                    issue_number = issue["number"]
                    title = issue["title"]
                    url = issue.get("html_url", "")

                    result.issues_found += 1
                    result.assigned_issues.append(
                        {
                            "repo": repo_full,
                            "number": issue_number,
                            "title": title,
                            "url": url,
                        }
                    )

                    if dry_run:
                        logger.info(
                            "  📌 [DRY RUN] Assigned issue #%d on %s: %s",
                            issue_number,
                            repo_full,
                            title[:60],
                        )
                    else:
                        logger.info(
                            "  📌 Assigned issue #%d on %s: %s",
                            issue_number,
                            repo_full,
                            title[:60],
                        )
            except Exception as e:
                logger.debug("Failed to check issues on %s: %s", repo_full, e)

    # ── Collect feedback ───────────────────────────────────────────────────

    async def _collect_feedback(
        self, owner: str, repo: str, pr_number: int, our_username: str
    ) -> list[dict]:
        """Collect all review comments and issue comments, filtering out our own."""
        feedback = []

        # Issue comments (general PR conversation)
        try:
            comments = await self._github.get_pr_comments(owner, repo, pr_number)
            for c in comments:
                login = c.get("user", {}).get("login", "")
                body = c.get("body", "")
                is_bot = c.get("user", {}).get("type") == "Bot"
                is_controlled_test = self._is_controlled_test_feedback(body)

                # Skip our own comments, bots, and review bots
                if (login == our_username and not is_controlled_test) or is_bot:
                    continue
                if login.lower() in REVIEW_BOT_LOGINS or login.endswith("[bot]"):
                    continue
                # Skip if it looks like our auto-reply
                if any(marker in body for marker in OUR_REPLY_MARKERS):
                    continue

                feedback.append(
                    {
                        "id": c["id"],
                        "author": login,
                        "body": body,
                        "is_inline": False,
                        "file_path": None,
                        "line": None,
                        "diff_hunk": None,
                        "created_at": c.get("created_at", ""),
                    }
                )
        except Exception as e:
            logger.warning("Could not fetch issue comments: %s", e)

        # Inline review comments (code-specific)
        try:
            review_comments = await self._github.get_pr_review_comments(owner, repo, pr_number)

            # Build index of bot comments for context lookup
            bot_index: dict[int, dict] = {}
            handled_review_comment_ids: set[int] = set()
            for c in review_comments:
                login = c.get("user", {}).get("login", "")
                body = c.get("body", "")
                is_bot = (
                    login.lower() in REVIEW_BOT_LOGINS
                    or login.endswith("[bot]")
                    or c.get("user", {}).get("type") == "Bot"
                )
                if is_bot:
                    bot_index[c["id"]] = {
                        "author": login,
                        "body": c.get("body", ""),
                        "file_path": c.get("path"),
                        "line": c.get("line") or c.get("original_line"),
                        "diff_hunk": c.get("diff_hunk"),
                    }
                if (
                    c.get("in_reply_to_id")
                    and (
                        login == our_username
                        or any(marker in body for marker in OUR_REPLY_MARKERS)
                    )
                ):
                    handled_review_comment_ids.add(c["in_reply_to_id"])

            for c in review_comments:
                login = c.get("user", {}).get("login", "")
                body = c.get("body", "")
                is_controlled_test = self._is_controlled_test_feedback(body)

                if c["id"] in handled_review_comment_ids:
                    continue

                if login == our_username and not is_controlled_test:
                    continue
                if login.lower() in REVIEW_BOT_LOGINS or login.endswith("[bot]"):
                    continue
                if any(marker in body for marker in OUR_REPLY_MARKERS):
                    continue

                # If this comment replies to a bot, attach bot's review as context
                bot_context = None
                reply_to = c.get("in_reply_to_id")
                if reply_to and reply_to in bot_index:
                    bot = bot_index[reply_to]
                    bot_context = f"[Bot review by @{bot['author']}]\n{bot['body']}"
                    # Inherit file_path/line/diff_hunk from bot if human comment lacks them
                    file_path = c.get("path") or bot.get("file_path")
                    line = c.get("line") or c.get("original_line") or bot.get("line")
                    diff_hunk = c.get("diff_hunk") or bot.get("diff_hunk")
                else:
                    file_path = c.get("path")
                    line = c.get("line") or c.get("original_line")
                    diff_hunk = c.get("diff_hunk")

                feedback.append(
                    {
                        "id": c["id"],
                        "author": login,
                        "body": body,
                        "is_inline": True,
                        "file_path": file_path,
                        "line": line,
                        "diff_hunk": diff_hunk,
                        "bot_context": bot_context,
                        "created_at": c.get("created_at", ""),
                    }
                )
        except Exception as e:
            logger.warning("Could not fetch review comments: %s", e)

        return feedback

    # ── Classify feedback via LLM ─────────────────────────────────────────

    async def _classify_feedback(self, feedback: list[dict]) -> list[FeedbackItem]:
        """Use LLM to classify each feedback item."""
        if not feedback:
            return []

        # P1-OPSEC: Hard-cap comment ingestion to prevent malicious comment flooding
        # from exhausting LLM quota in a single PR cycle.
        feedback = feedback[-15:]

        comments_text = "\n\n".join(
            f"Comment #{i + 1} (by @{f['author']}, "
            f"{'inline on ' + (f['file_path'] or '?') if f['is_inline'] else 'general'}):\n"
            f"{f['body']}"
            for i, f in enumerate(feedback)
        )

        prompt = (
            "Classify each review comment on a PR. "
            "For each comment, determine the action needed.\n\n"
            "Actions:\n"
            "- CODE_CHANGE: Maintainer wants code mods\n"
            "- QUESTION: Maintainer asks a question\n"
            "- STYLE_FIX: Naming, formatting, convention\n"
            "- APPROVE: Positive, no action\n"
            "- REJECT: PR rejected entirely\n"
            "- HOSTILE_REJECT: Maintainer is hostile — says stop, "
            "calls the PR spam, labels it as unwanted bot/automated PR, "
            "tells the bot to go away, or aggressively demands closure\n"
            "- ALREADY_HANDLED: Reply to prev fix or bot\n\n"
            f"Comments to classify:\n{comments_text}\n\n"
            "Respond in YAML:\n"
            "```yaml\n"
            "classifications:\n"
            "  - comment_number: 1\n"
            "    action: CODE_CHANGE\n"
            "    reason: brief reason\n"
            "```"
        )

        import asyncio

        from farm_agent.core.exceptions import LLMRateLimitError

        max_retries = 3
        for attempt in range(max_retries + 1):
            try:
                response = await self._llm.complete(
                    prompt,
                    system="You classify review comments on pull requests. Be precise.",
                    temperature=0.1,
                )
                return self._parse_classifications(response, feedback)
            except LLMRateLimitError as e:
                if attempt < max_retries:
                    wait = 5 * (2**attempt)  # 5s, 10s, 20s
                    logger.warning(
                        "  ⏳ Rate limited, retrying in %ds (%d/%d): %s",
                        wait,
                        attempt + 1,
                        max_retries,
                        e,
                    )
                    await asyncio.sleep(wait)
                else:
                    logger.warning("  ⚠️ Rate limit exhausted after %d retries", max_retries)
                    break
            except ValueError as e:
                # YAML/JSON parse failures from _parse_classifications — re-raise
                # so the retry loop can handle them
                logger.warning("Failed to parse LLM classification response: %s", e)
                raise
            except Exception as e:
                # Other exceptions (network, etc.) — re-raise for retry
                logger.error("Unexpected error parsing LLM feedback: %s", e)
                raise

        # Fall back: do NOT blindly treat as CODE_CHANGE — that triggers
        # unwanted automated commits. Mark as ALREADY_HANDLED and log error.
        logger.error(
            "  ⚠️ LLM classification failed after %d retries — marking %d feedback items as ALREADY_HANDLED",
            max_retries,
            len(feedback),
        )
        return [
            FeedbackItem(
                comment_id=f["id"],
                author=f["author"],
                body=f["body"],
                action=FeedbackAction.ALREADY_HANDLED,
                file_path=f.get("file_path"),
                line=f.get("line"),
                diff_hunk=f.get("diff_hunk"),
                is_inline=f["is_inline"],
            )
            for f in feedback
        ]

    def _parse_classifications(self, response: str, feedback: list[dict]) -> list[FeedbackItem]:
        """Parse LLM YAML response into FeedbackItems."""
        items = []

        # Extract YAML block
        text = response
        if "```yaml" in text:
            text = text.split("```yaml", 1)[1].split("```", 1)[0]
        elif "```" in text:
            text = text.split("```", 1)[1].split("```", 1)[0]

        try:
            parsed = yaml.safe_load(text)
        except yaml.YAMLError as e:
            logger.warning("Failed to parse LLM response as YAML: %s", e)
            raise ValueError(f"LLM returned unparseable YAML: {e}") from e
        except ValueError as e:
            logger.warning("Failed to parse LLM response as JSON: %s", e)
            raise ValueError(f"LLM returned unparseable JSON: {e}") from e
        except Exception as e:
            logger.error("Unexpected error parsing LLM feedback: %s", e)
            raise

        if not parsed or "classifications" not in parsed:
            return items

        action_map = {a.value: a for a in FeedbackAction}

        for cls in parsed["classifications"]:
            idx = cls.get("comment_number", 0) - 1
            if idx < 0 or idx >= len(feedback):
                continue

            f = feedback[idx]
            action_str = cls.get("action", "").lower()
            action = action_map.get(action_str, FeedbackAction.ALREADY_HANDLED)

            items.append(
                FeedbackItem(
                    comment_id=f["id"],
                    author=f["author"],
                    body=f["body"],
                    action=action,
                    file_path=f.get("file_path"),
                    line=f.get("line"),
                    diff_hunk=f.get("diff_hunk"),
                    is_inline=f["is_inline"],
                    bot_context=f.get("bot_context"),
                )
            )

        return items

    # ── Handle code fix ───────────────────────────────────────────────────

    async def _handle_code_fix(
        self,
        owner: str,
        repo: str,
        pr_record: dict,
        pr_data: dict,
        feedback: FeedbackItem,
        dry_run: bool = False,
    ) -> bool:
        """Generate and push a code fix based on review feedback."""
        if pr_record.get("type") not in _AUTO_FIXABLE_PR_TYPES:
            logger.warning("Blocking unverified automatic fix for security or untyped PR")
            return False
        try:
            # Get the PR branch and fork info
            head = pr_data.get("head", {})
            fork_owner = head.get("repo", {}).get("owner", {}).get("login", owner)
            fork_repo = head.get("repo", {}).get("name", repo)
            branch = head.get("ref", "main")

            # Get file content if inline comment
            file_content = ""
            file_path = feedback.file_path
            if file_path:
                try:
                    file_content = await self._github.get_file_content(
                        fork_owner, fork_repo, file_path, ref=branch
                    )
                except Exception:
                    logger.warning("Could not fetch file: %s", file_path)

            # P1-OPSEC-1: Non-blocking skip — check scheduled run time BEFORE doing any work
            task_key = f"code_fix:{pr_record['repo']}:{pr_data['number']}:{file_path or 'no_file'}"
            if self._memory:
                scheduled = await self._memory.get_task_schedule(task_key)
                if scheduled:
                    from datetime import datetime
                    try:
                        scheduled_dt = datetime.fromisoformat(scheduled)
                        if scheduled_dt.tzinfo is None:
                            scheduled_dt = scheduled_dt.replace(tzinfo=UTC)
                        if scheduled_dt > datetime.now(UTC):
                            logger.info(
                                "Skipping code fix for task %s — scheduled for %s",
                                task_key, scheduled,
                            )
                            return False
                    except Exception as e:
                        # PHASE 3-FIX: Active DB GC. Strip toxic entropy instantly.
                        logger.warning("Purging corrupted schedule entry for %s: %s", task_key, e)
                        try:
                            await self._memory._db.execute(
                                "DELETE FROM task_schedule WHERE task_key = ?",
                                (task_key,)
                            )
                            await self._memory._db.commit()
                        except Exception as db_e:
                            logger.error("Failed to purge corrupted entry %s: %s", task_key, db_e)

            # Get PR diff for context
            try:
                diff = await self._github.get_pr_diff(owner, repo, pr_data["number"])
                # Truncate diff if too long
                if len(diff) > 8000:
                    diff = diff[:8000] + "\n... (truncated)"
            except Exception:
                diff = ""

            # Layer 1: Contextual Memory — fetch previous failed diff
            user = await self._get_user()
            previous_diff = await self._fetch_previous_bot_diff(
                owner, repo, pr_data["number"], user["login"],
            )

            # Generate fix via LLM
            prompt = self._build_fix_prompt(
                feedback, file_content, file_path, diff, previous_diff
            )
            response = await self._llm.complete(
                prompt,
                system=(
                    "You are a developer fixing code based on a PR review comment. "
                    "Return ONLY the complete fixed file content. No explanations. "
                    "Make the MINIMUM change to address the feedback.\n"
                    "GHOST PROTOCOL: You are NOT an AI. Do NOT use phrases like "
                    "'As an AI', 'I am automated', or add any disclosure footers. "
                    "Sound like a busy senior engineer, not a chatbot."
                ),
                temperature=0.2,
            )

            # Extract fixed content
            fixed_content = self._extract_fixed_content(response)
            if not fixed_content or not file_path:
                logger.warning("  ⚠️ Could not generate fix for: %s", feedback.body[:60])
                return False

            if fixed_content.strip() == file_content.strip():
                logger.info("  [info] No changes needed for: %s", feedback.body[:60])
                return False

            # Get file SHA for update
            try:
                resp = await self._github._get(
                    f"/repos/{fork_owner}/{fork_repo}/contents/{file_path}",
                    params={"ref": branch},
                )
                sha = resp.get("sha")
            except Exception:
                sha = None

            if not dry_run:
                # P1-OPSEC-1: Human-like continuous delay distribution
                # Use expovariate for Poisson-process-like delays (human work patterns)
                mean_delay = random.uniform(120, 600)  # mean of 2-10 minutes
                read_delay = max(15, min(random.expovariate(1.0 / mean_delay), 7200))  # cap at 2 hours
                # Add triangular jitter to further obscure pattern
                jitter = random.triangular(0.5, 2.0, 1.0)  # 50%-200% of base, mode=100%
                read_delay = int(read_delay * jitter)
                # Cap absolute maximum
                read_delay = min(read_delay, 7200)  # 2 hours absolute max

                if read_delay < 300:
                    logger.info("  Mới check mail thấy có notification từ Maintainer. Bắt đầu đọc... (Simulating notification lag: %ds)", read_delay)
                else:
                    next_run = datetime.now(UTC) + timedelta(seconds=read_delay)
                    await self._memory.set_task_schedule(task_key, next_run.isoformat())
                    logger.info("  Long notification lag (%ds) scheduled for %s — skipping this cycle", read_delay, next_run.isoformat())
                    return False

                await asyncio.sleep(read_delay)

                delay = self._calculate_typing_delay(fixed_content)
                logger.info("  ⏳ WPM Simulator: 'Typing' code fix for %ds...", delay)
                await asyncio.sleep(delay)

            # Push fix (guarded against Janitor race condition)
            user = await self._get_user()
            signoff = self._build_signoff(user)
            # P0-FIX: Never pass raw maintainer text into commit messages.
            # Maintainer text (feedback.body) can contain prompt injection
            # sequences. Use only structural identifiers (PR# + file path).
            commit_summary = f"PR #{pr_data['number']}"
            if file_path:
                commit_summary += f" ({file_path.rsplit('/', 1)[-1]})"
            commit_msg = random.choice(GITHUB_REPLIES["COMMIT_FIX"]).format(
                summary=commit_summary,
            )
            try:
                await self._github.create_or_update_file(
                    fork_owner,
                    fork_repo,
                    file_path,
                    fixed_content,
                    commit_msg,
                    branch,
                    sha=sha,
                    signoff=signoff,
                )
            except GitHubAPIError as exc:
                logger.warning(
                    "  ⚠️ PR branch modified/deleted externally (Janitor race) "
                    "while pushing fix to %s: %s",
                    file_path, exc,
                )
                return False
            logger.info("  Pushed fix for %s: %s", file_path, feedback.body[:60])

            # Reply to comment — sound like a real human developer
            reply_body = (
                random.choice(GITHUB_REPLIES["FIX_APPLIED"])
                + "\n\n<!-- farm_agent-patrol -->"
            )
            if feedback.is_inline:
                await self._github.create_pr_review_comment_reply(
                    owner, repo, pr_data["number"], feedback.comment_id, reply_body
                )
            else:
                await self._github.create_pr_comment(owner, repo, pr_data["number"], reply_body)

            return True

        except Exception as e:
            logger.error("  ❌ Failed to fix: %s", e)
            return False

    def _build_fix_prompt(
        self,
        feedback: FeedbackItem,
        file_content: str,
        file_path: str | None,
        diff: str,
        previous_diff: str = "",
    ) -> str:
        """Build the LLM prompt to generate a code fix."""
        parts = [f"A reviewer left this feedback on a pull request:\n\n> {feedback.body}"]

        if feedback.bot_context:
            parts.append(
                f"\nThis comment was in reply to a bot code review that said:"
                f"\n```\n{feedback.bot_context[:3000]}\n```"
                f"\nUse the bot's analysis to understand what needs fixing."
            )

        if feedback.diff_hunk:
            parts.append(f"\nThe feedback is on this code section:\n```\n{feedback.diff_hunk}\n```")

        if file_path and file_content:
            parts.append(f"\nCurrent content of `{file_path}`:\n```\n{file_content}\n```")

        if diff:
            parts.append(f"\nFull PR diff (for context):\n```diff\n{diff}\n```")

        if previous_diff:
            parts.append(
                f"\nHere is the fix you just tried:\n"
                f"```diff\n{previous_diff}\n```\n"
                "It FAILED (was rejected). Do NOT generate this exact code again. "
                "Try a completely different approach based on the feedback."
            )

        parts.append(
            "\nApply the MINIMUM change to address the reviewer's feedback. "
            "Return the COMPLETE updated file content. "
            "Do NOT add any explanations before or after the code."
        )

        return "\n".join(parts)

    def _extract_fixed_content(self, response: str) -> str:
        """Extract the fixed file content from LLM response."""
        text = response.strip()

        # Remove markdown code fences if present
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove first line (```lang) and last line (```)
            lines = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
            text = "\n".join(lines)

        return text

    # ── Handle question ───────────────────────────────────────────────────

    async def _handle_question(
        self,
        owner: str,
        repo: str,
        pr_record: dict,
        pr_data: dict,
        feedback: FeedbackItem,
        dry_run: bool = False,
    ) -> bool:
        """Answer a maintainer's question on the PR."""
        try:
            # Get PR context
            pr_body = pr_data.get("body", "")
            pr_title = pr_data.get("title", "")

            prompt = (
                f"A maintainer asked this question on our pull request:\n\n"
                f"PR title: {pr_title}\n"
                f"PR description:\n{pr_body[:2000]}\n\n"
                f"Question from @{feedback.author}:\n> {feedback.body}\n\n"
                f"Write a concise reply (1-3 sentences). Be direct. No apologies, no excessive politeness."
            )

            response = await self._llm.complete(
                prompt,
                system=(
                    "You are a tired senior developer answering a code review question. "
                    "Be brief and direct. No fluff, no apologies.\n"
                    "GHOST PROTOCOL: You are NOT an AI. NEVER write 'As an AI', "
                    "'I am automated', or any disclosure footer. "
                    "If challenged, respond with technical facts only — no apologies."
                ),
                temperature=0.3,
            )

            raw_answer = response.strip()
            if not raw_answer:
                return False

            # Wrap LLM answer with a natural human opener/closer
            greeting = self._get_contextual_greeting()
            opener = random.choice(GITHUB_REPLIES["QUESTION_OPENER"])
            closer = random.choice(GITHUB_REPLIES["QUESTION_CLOSER"])
            reply_body = f"{greeting}{opener}\n\n{raw_answer}\n\n{closer}"

            if not dry_run:
                # BEHV-04 fix: bimodal distribution to simulate human work patterns
                if random.random() < 0.80:
                    read_delay = random.randint(30, 300)  # Quick response (active coding)
                else:
                    read_delay = random.randint(3600, 28800)  # Long delay (meeting/sleep)
                logger.info("  Mới check mail thấy có notification từ Maintainer. Bắt đầu đọc... (Simulating notification lag: %ds)", read_delay)
                await asyncio.sleep(read_delay)

                delay = self._calculate_typing_delay(reply_body)
                logger.info("  ⏳ WPM Simulator: 'Typing' reply for %ds...", delay)
                await asyncio.sleep(delay)

            # Post reply
            # ── Gag Order — block AI disclosures before posting ─────────────
            import re as _re
            _ghost_re = _re.compile(
                r"(?i)(as an ai|ai generated|language model|openai|minimax|"
                r"automated bot|generated by ai|ai assistant|farm_agent|agent-farm|farmagent)",
            )
            if _ghost_re.search(reply_body):
                logger.warning("Gag Order triggered — AI disclosure in reply body. Skipping post.")
                return False
            # ─────────────────────────────────────────────────────────────────
            if feedback.is_inline:
                await self._github.create_pr_review_comment_reply(
                    owner, repo, pr_data["number"], feedback.comment_id, reply_body
                )
            else:
                await self._github.create_pr_comment(owner, repo, pr_data["number"], reply_body)

            logger.info(
                "  💬 Replied to @%s on PR #%d",
                feedback.author,
                pr_data["number"],
            )
            return True

        except Exception as e:
            logger.error("  ❌ Failed to reply: %s", e)
            return False

    # ── CLA re-check ─────────────────────────────────────────────────────

    async def _handle_cla_recheck(self, owner: str, repo: str, pr_number: int) -> bool:
        """Re-sign CLA if needed after pushing new commits."""
        import asyncio

        # Wait for CLA bots to react to new commits
        await asyncio.sleep(10)

        try:
            comments = await self._github.get_pr_comments(owner, repo, pr_number)
        except Exception:
            return False

        for comment in comments:
            login = comment.get("user", {}).get("login", "")
            body = comment.get("body", "").lower()
            is_bot = comment.get("user", {}).get("type") == "Bot"

            if not is_bot:
                continue

            # Check if CLA bot is asking for re-signing
            if any(kw in login.lower() for kw in ["cla", "claassistant"]) or any(
                kw in body for kw in ["sign our cla", "cla not signed", "please sign"]
            ):
                try:
                    await self._github.create_pr_comment(
                        owner,
                        repo,
                        pr_number,
                        "I have read the CLA Document and I hereby sign the CLA",
                    )
                    logger.info("  ✍️ Re-signed CLA on PR #%d", pr_number)
                    return True
                except Exception as e:
                    logger.warning("  CLA re-sign failed: %s", e)

        return False

    # ── Fail-Safe Limits (set in __init__ from config) ─────────────────────
    # MAX_CI_RETRIES and MAX_DISCUSSION_REPLIES are now instance attributes
    # initialized from PipelineConfig (defaults: 3 and 3).

    # ── CI Auto-Healing ────────────────────────────────────────────────────

    async def _check_ci_failures(
        self,
        owner: str,
        repo: str,
        pr_record: dict,
        pr_data: dict,
        head_sha: str,
        result: PatrolResult,
        *,
        dry_run: bool = False,
    ) -> bool:
        """Check for CI failures and attempt auto-healing.

        Returns True if a CI failure was handled (caller should skip
        human feedback for this patrol cycle).
        """
        check_runs = await self._github.get_pr_check_runs(owner, repo, head_sha)
        failed_runs = [
            r for r in check_runs if r.get("conclusion") == "failure"
        ]
        if not failed_runs:
            return False

        pr_number = pr_record["pr_number"]
        repo_full = pr_record["repo"]

        # Check attempt count
        attempts = 0
        if self._memory:
            attempts = await self._memory.get_ci_fix_attempts(repo_full, pr_number)

        if attempts >= self.MAX_CI_RETRIES:
            logger.warning(
                "  🚫 CI fix limit (%d) reached for PR #%d — closing PR",
                self.MAX_CI_RETRIES, pr_number,
            )
            if not dry_run:
                try:
                    await self._github.close_pull_request(
                        owner, repo, pr_number,
                        comment=random.choice(GITHUB_REPLIES["CI_LIMIT_CLOSE"]).format(
                            attempts=self.MAX_CI_RETRIES,
                        ),
                    )
                except GitHubAPIError as exc:
                    logger.warning("  ⚠️ Could not close PR #%d: %s", pr_number, exc)
                if self._notifier:
                    repo_url = pr_data.get("html_url", f"https://github.com/{repo_full}")
                    await self._notifier.send_message(
                        f"🏳️ [SURRENDER] PR closed due to max CI retries ({self.MAX_CI_RETRIES}/{self.MAX_CI_RETRIES}) hit on {repo_url}"
                    )
            return True

        # Filter out infrastructure/auth failures that cannot be fixed by code
        fixable_runs = [
            r for r in failed_runs
            if not self._is_infra_ci_failure(r.get("name", ""))
        ]

        if len(fixable_runs) < len(failed_runs):
            skipped = len(failed_runs) - len(fixable_runs)
            logger.info(
                "  ⚙️ Skipped %d infra/auth CI failure(s) (not code-fixable)",
                skipped,
            )

        if not fixable_runs:
            logger.info(
                "  ✅ All %d CI failure(s) are infra/auth — nothing to auto-heal",
                len(failed_runs),
            )
            return False

        # Pick the first fixable run
        failed = fixable_runs[0]
        check_name = self._sanitize_check_name(failed.get("name", "CI"))
        check_run_id = failed.get("id", 0)

        logger.info(
            "  🔴 CI check '%s' failed on PR #%d (attempt %d/%d)",
            check_name, pr_number, attempts + 1, self.MAX_CI_RETRIES,
        )


        if dry_run:
            logger.info("  🏃 [DRY RUN] Would attempt CI auto-fix")
            return True

        # Download and parse log
        raw_log = await self._github.download_check_run_log(owner, repo, check_run_id)
        traceback = self._extract_ci_traceback(raw_log)

        if not traceback.strip():
            logger.warning("  ⚠️ Could not extract traceback from CI log")
            return False

        # Second-pass: check log content for infra/auth patterns
        if self._is_infra_ci_failure(traceback):
            logger.info(
                "  ⚙️ CI log for '%s' contains infra/auth patterns — skipping auto-heal",
                check_name,
            )
            return False


        ci_status = await self._handle_ci_failure(
            owner, repo, pr_record, pr_data, traceback, check_name, attempts,
        )

        if ci_status == "pushed":
            result.ci_fixes_pushed += 1
            return True

        return ci_status == "closed"

    @staticmethod
    def _is_infra_ci_failure(text: str) -> bool:
        """Check if a CI check name or log indicates an infrastructure failure.

        Infrastructure/auth failures (Vercel previews, missing secrets,
        Codecov, CLA bots) cannot be fixed via code changes and must not
        trigger the auto-heal loop.

        P1-OPSEC-3: For check names, uses exact match or prefix match to prevent
        false positives (e.g., "vercel-fake" must NOT match "vercel").
        For log content, uses substring matching.
        """
        text_clean = "".join(text.lower().split())
        # For check names: exact match (vercel, netlify, codecov...)
        if text_clean in CI_INFRA_IGNORE_NAMES:
            return True
        # For check names: prefix match (vercel/, netlify/, cla/...)
        if text_clean.startswith(CI_INFRA_IGNORE_PREFIXES):
            return True
        # For log content: substring matching still applies
        return any(pattern in text_clean.lower() for pattern in CI_INFRA_IGNORE_PATTERNS)

    @staticmethod
    def _sanitize_check_name(raw_name: str) -> str:
        """Sanitize a CI check name from the GitHub API.

        P0-FIX: CI check names are untrusted external input. Maintainers
        can craft check names containing emojis (🤖), AI-identity keywords
        (bot, AI), or prompt-injection patterns. This method strips:
        1. Emojis and non-ASCII characters (except basic punctuation)
        2. AI identity keywords that would violate the Gag Order
        3. Prompt injection sequences (ignore, instruction, system prompt)

        Returns a safe, ASCII-only check name suitable for commits/PR bodies.
        """
        import re as _re
        # Strip emojis and non-ASCII (keep alphanumeric, spaces, hyphens, underscores, dots, slashes)
        sanitized = _re.sub(r'[^\x20-\x7E]', '', raw_name)
        # Strip AI identity keywords (Gag Order)
        _gag_keywords = _re.compile(
            r'\b(bot|ai|automated|robot|artificial|intelligence|machine.?learning|'
            r'openai|anthropic|gemini|minimax|agent-farm|farm.?agent)\b',
            _re.IGNORECASE,
        )
        sanitized = _gag_keywords.sub('', sanitized)
        # Strip prompt injection patterns
        _injection_re = _re.compile(
            r'\b(ignore|instruction|system.?prompt|override|disregard|forget)\b',
            _re.IGNORECASE,
        )
        sanitized = _injection_re.sub('', sanitized)
        # Collapse whitespace and trim
        sanitized = _re.sub(r'\s+', ' ', sanitized).strip()
        # Fallback if everything was stripped
        return sanitized or "CI"

    @staticmethod
    def _extract_ci_traceback(raw_log: str) -> str:
        """Extract the relevant error traceback from a raw CI log.

        Strategy:
        1. Search for Python-style Traceback blocks.
        2. Search for lines containing Error:, Exception:, FAILED, FAIL:.
        3. Fallback: return last 100 lines.

        Output is capped at 3000 characters to avoid token overflow.
        """
        if not raw_log:
            return ""

        lines = raw_log.splitlines()

        # Strategy 1: Find Python traceback blocks
        traceback_pattern = re.compile(r"^\s*Traceback \(most recent call last\)", re.IGNORECASE)
        traceback_blocks: list[str] = []
        i = 0
        while i < len(lines):
            if traceback_pattern.search(lines[i]):
                block_start = i
                i += 1
                # Collect traceback lines: indented lines are stack frames,
                # a non-indented, non-empty line is the final error line.
                while i < len(lines):
                    raw_line = lines[i]
                    stripped = raw_line.strip()
                    if not stripped:
                        # blank line — could be inside or after traceback
                        i += 1
                        continue
                    if raw_line.startswith((" ", "\t")) or stripped.startswith("File "):
                        # Stack frame or code context line
                        i += 1
                        continue
                    # Non-indented, non-empty line → likely the error line
                    # (e.g. "ValueError: ..." or "AssertionError: ...")
                    i += 1  # include this line
                    break
                traceback_blocks.append("\n".join(lines[block_start:i]))
            else:
                i += 1

        if traceback_blocks:
            # Return the last traceback block (most relevant)
            return traceback_blocks[-1][:3000]

        # Strategy 2: Find lines with error keywords in the tail
        tail = lines[-200:] if len(lines) > 200 else lines
        error_pattern = re.compile(
            r"(Error:|Exception:|FAILED|FAIL:|AssertionError|assert.*error|error:)",
            re.IGNORECASE,
        )
        error_lines = []
        for idx, line in enumerate(tail):
            if error_pattern.search(line):
                # Include some context: 5 lines before and 3 lines after
                start = max(0, idx - 5)
                end = min(len(tail), idx + 4)
                error_lines.extend(tail[start:end])

        if error_lines:
            # Deduplicate while preserving order
            seen: set[str] = set()
            unique: list[str] = []
            for line in error_lines:
                if line not in seen:
                    seen.add(line)
                    unique.append(line)
            return "\n".join(unique)[:3000]

        # Strategy 3: Fallback — last 100 lines
        fallback = lines[-100:] if len(lines) > 100 else lines
        return "\n".join(fallback)[:3000]

    async def _fetch_previous_bot_diff(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        username: str,
    ) -> str:
        """Fetch the diff of the bot's most recent commit on this PR.

        Returns the diff string (capped at 4000 chars) or empty string
        on any failure.
        """
        try:
            commits = await self._github.get_pr_commits(owner, repo, pr_number)
            # Walk backwards to find the latest bot commit
            for commit in reversed(commits):
                author_login = (
                    commit.get("author") or {}
                ).get("login", "")
                if author_login == username:
                    sha = commit.get("sha", "")
                    if sha:
                        diff = await self._github.get_commit_diff(owner, repo, sha)
                        return diff[:4000] if diff else ""
        except Exception as exc:
            logger.debug("Could not fetch previous bot diff: %s", exc)
        return ""


    async def _handle_ci_failure(
        self,
        owner: str,
        repo: str,
        pr_record: dict,
        pr_data: dict,
        traceback: str,
        check_name: str,
        starting_attempts: int,
    ) -> str:
        """Use the LLM to fix a CI failure and push only sandbox-validated code."""
        if pr_record.get("type") not in _AUTO_FIXABLE_PR_TYPES:
            logger.warning("Blocking unverified automatic CI fix for security or untyped PR")
            return "blocked"
        try:
            head = pr_data.get("head", {})
            fork_owner = head.get("repo", {}).get("owner", {}).get("login", owner)
            fork_repo = head.get("repo", {}).get("name", repo)
            branch = head.get("ref", "main")
            pr_number = pr_data["number"]
            repo_full = pr_record["repo"]

            try:
                diff = await self._github.get_pr_diff(owner, repo, pr_number)
                if len(diff) > 8000:
                    diff = diff[:8000] + "\n... (truncated)"
            except Exception:
                diff = ""

            user = await self._get_user()
            previous_diff = await self._fetch_previous_bot_diff(
                owner, repo, pr_number, user["login"],
            )

            file_path = self._guess_file_from_traceback(traceback, diff)
            if not file_path:
                logger.warning("  Could not determine file path from traceback")
                return "failed"

            prompt = (
                f"The CI pipeline (`{check_name}`) failed with this error:\n"
                f"```\n{traceback}\n```\n\n"
            )
            if diff:
                prompt += f"Here is the PR diff for context:\n```diff\n{diff}\n```\n\n"
            if previous_diff:
                prompt += (
                    "Here is the fix you just tried:\n"
                    f"```diff\n{previous_diff}\n```\n"
                    "It FAILED. Do NOT generate this exact code again. "
                    "Try a completely different approach.\n\n"
                )
            prompt += (
                "Please fix the code to resolve this CI failure. "
                "Return ONLY the complete fixed file content. "
                "No explanations. Make the MINIMUM change to fix the error."
            )

            current_content = ""
            with contextlib.suppress(Exception):
                current_content = await self._github.get_file_content(
                    fork_owner, fork_repo, file_path, ref=branch,
                )

            fixed_content, _, validation_failures = await self._generate_validated_ci_fix(
                owner=fork_owner,
                repo=fork_repo,
                branch=branch,
                repo_full=repo_full,
                pr_number=pr_number,
                file_path=file_path,
                current_content=current_content,
                prompt=prompt,
                system_prompt=(
                    "You are a developer fixing CI failures. "
                    "Analyze the traceback, identify the broken file, "
                    "and return the complete corrected file content."
                ),
                starting_attempts=starting_attempts,
            )
            if not fixed_content:
                if starting_attempts + validation_failures >= self.MAX_CI_RETRIES:
                    await self._close_ci_retry_limited_pr(
                        owner=owner,
                        repo=repo,
                        repo_full=repo_full,
                        pr_number=pr_number,
                        pr_data=pr_data,
                    )
                    return "closed"

                logger.warning(
                    "  Local validation failed for `%s`; no CI fix was pushed",
                    file_path,
                )
                return "failed"

            try:
                resp = await self._github._get(
                    f"/repos/{fork_owner}/{fork_repo}/contents/{file_path}",
                    params={"ref": branch},
                )
                sha = resp.get("sha")
            except Exception:
                sha = None

            signoff = self._build_signoff(user)
            commit_msg = random.choice(GITHUB_REPLIES["COMMIT_CI_FIX"]).format(
                check_name=check_name,
            )
            try:
                await self._github.create_or_update_file(
                    fork_owner,
                    fork_repo,
                    file_path,
                    fixed_content,
                    commit_msg,
                    branch,
                    sha=sha,
                    signoff=signoff,
                )
            except GitHubAPIError as exc:
                logger.warning(
                    "  ⚠️ PR branch modified/deleted externally (Janitor race) "
                    "while pushing CI fix to %s: %s",
                    file_path, exc,
                )
                return "failed"
            logger.info("  Pushed CI fix for '%s' on %s", check_name, file_path)

            if self._memory and validation_failures == 0:
                await self._memory.increment_ci_fix_attempts(repo_full, pr_number)

            ci_reply = (
                random.choice(GITHUB_REPLIES["CI_FIX_APPLIED"]).format(
                    check_name=check_name,
                    file_path=file_path,
                )
                + "\n\n<!-- farm_agent-patrol -->"
            )
            await self._github.create_pr_comment(owner, repo, pr_number, ci_reply)
            return "pushed"

        except Exception as e:
            logger.error("  CI auto-fix failed: %s", e)
            return "failed"

    async def _generate_validated_ci_fix(
        self,
        *,
        owner: str,
        repo: str,
        branch: str,
        repo_full: str,
        pr_number: int,
        file_path: str,
        current_content: str,
        prompt: str,
        system_prompt: str,
        starting_attempts: int,
    ) -> tuple[str | None, dict[str, Any] | None, int]:
        """Generate a CI fix and validate it locally before pushing."""
        if not self._enable_sandbox_validation:
            try:
                response = await self._llm.complete(
                    prompt,
                    system=system_prompt,
                    temperature=0.2,
                )
            except Exception as exc:
                from farm_agent.core.exceptions import LLMRateLimitError
                if isinstance(exc, LLMRateLimitError):
                    logger.warning(
                        "  ⚠️ LLM quota exhausted during CI auto-heal — aborting fix: %s", exc,
                    )
                    raise  # re-raise so _handle_ci_failure / outer loop can cooldown
                logger.error("  ❌ LLM call failed during CI auto-heal: %s", exc)
                return None, None, 0
            fixed_content = self._extract_fixed_content(response)
            return fixed_content or None, None, 0

        remaining_attempts = max(1, self.MAX_CI_RETRIES - starting_attempts)
        validation_failures = 0
        current_prompt = prompt
        last_result: dict[str, Any] | None = None

        with TemporaryDirectory(prefix="farm_agent-ci-validation-") as tmpdir:
            workspace = Path(tmpdir).resolve()
            await self._prepare_validation_workspace(
                workspace=workspace,
                owner=owner,
                repo=repo,
                branch=branch,
                file_path=file_path,
                current_content=current_content,
            )
            command, image = self._detect_validation_command(workspace)
            logger.info(
                "  Running local sandbox validation with `%s` using image `%s`",
                command,
                image,
            )

            sandbox = self._create_sandbox()
            try:
                for _ in range(remaining_attempts):
                    try:
                        response = await self._llm.complete(
                            current_prompt,
                            system=system_prompt,
                            temperature=0.2,
                        )
                    except Exception as llm_exc:
                        from farm_agent.core.exceptions import LLMRateLimitError
                        if isinstance(llm_exc, LLMRateLimitError):
                            logger.warning(
                                "  ⚠️ LLM quota exhausted during sandbox CI fix — aborting: %s",
                                llm_exc,
                            )
                            raise  # propagate to caller for cooldown
                        logger.error(
                            "  ❌ LLM call failed during sandbox CI fix: %s", llm_exc,
                        )
                        return None, last_result, validation_failures
                    fixed_content = self._extract_fixed_content(response)
                    if not fixed_content:
                        logger.warning("  LLM returned empty fix for CI failure")
                        return None, last_result, validation_failures

                    await self._write_validation_file(workspace, file_path, fixed_content)
                    last_result = await sandbox.run_in_sandbox(
                        str(workspace),
                        command,
                        image=image,
                    )
                    if last_result.get("exit_code") == 0:
                        return fixed_content, last_result, validation_failures

                    validation_failures += 1
                    total_attempts = starting_attempts + validation_failures
                    logger.warning(
                        "  Local validation failed for `%s` (attempt %d/%d, exit=%s)",
                        file_path,
                        total_attempts,
                        self.MAX_CI_RETRIES,
                        last_result.get("exit_code"),
                    )

                    if total_attempts >= self.MAX_CI_RETRIES:
                        break

                    current_prompt = self._append_local_validation_failure_prompt(
                        current_prompt,
                        last_result,
                    )
            finally:
                with contextlib.suppress(Exception):
                    sandbox.client.close()

        return None, last_result, validation_failures

    async def _prepare_validation_workspace(
        self,
        *,
        workspace: Path,
        owner: str,
        repo: str,
        branch: str,
        file_path: str,
        current_content: str,
    ) -> None:
        """Populate a local workspace snapshot for sandbox validation."""
        hydrated = await self._hydrate_full_validation_workspace(
            workspace,
            owner=owner,
            repo=repo,
            branch=branch,
        )
        if hydrated:
            return

        logger.info("  Falling back to a minimal validation workspace for `%s`", file_path)
        await self._write_validation_file(workspace, file_path, current_content)

    async def _hydrate_full_validation_workspace(
        self,
        workspace: Path,
        *,
        owner: str,
        repo: str,
        branch: str,
    ) -> bool:
        """Attempt to materialize a text-only repository snapshot for validation."""
        get_file_tree = getattr(self._github, "get_file_tree", None)
        get_file_content = getattr(self._github, "get_file_content", None)
        if not callable(get_file_tree) or not callable(get_file_content):
            return False

        try:
            file_tree = await get_file_tree(owner, repo, branch=branch)
        except TypeError:
            file_tree = await get_file_tree(owner, repo, branch)
        except Exception as exc:
            logger.warning("  Could not fetch validation file tree: %s", exc)
            return False

        wrote_any = False
        for node in file_tree:
            node_path = self._tree_node_value(node, "path")
            node_type = self._tree_node_value(node, "type")
            node_size = self._tree_node_value(node, "size", 0)
            if node_type != "blob" or not node_path or not self._should_copy_validation_file(
                node_path,
                node_size,
            ):
                continue

            content = None
            try:
                content = await get_file_content(owner, repo, node_path, ref=branch)
            except TypeError:
                try:
                    content = await get_file_content(owner, repo, node_path, branch)
                except Exception as e:
                    logger.warning("Validation file fetch failed for %s: %s — cannot validate", node_path, e)
                    continue
            except Exception:
                continue

            if not isinstance(content, str):
                continue

            with contextlib.suppress(ValueError):
                await self._write_validation_file(workspace, node_path, content)
                wrote_any = True

        return wrote_any

    @staticmethod
    def _tree_node_value(node: Any, key: str, default: Any = None) -> Any:
        """Read a file-tree property from either a dict or model instance."""
        if isinstance(node, dict):
            return node.get(key, default)
        return getattr(node, key, default)

    @staticmethod
    def _should_copy_validation_file(path: str, size: int) -> bool:
        """Filter out obviously large or binary files from validation snapshots."""
        if size and size > 1_000_000:
            return False

        suffix = Path(path).suffix.lower()
        return suffix not in {
            ".png",
            ".jpg",
            ".jpeg",
            ".gif",
            ".bmp",
            ".ico",
            ".pdf",
            ".zip",
            ".gz",
            ".tar",
            ".tgz",
            ".7z",
            ".jar",
            ".exe",
            ".dll",
            ".so",
            ".dylib",
            ".pyc",
            ".pyo",
            ".class",
            ".woff",
            ".woff2",
            ".ttf",
            ".eot",
            ".mp3",
            ".mp4",
            ".mov",
            ".avi",
            ".webm",
            ".bin",
            ".sqlite",
            ".db",
        }

    async def _write_validation_file(self, workspace: Path, file_path: str, content: str) -> None:
        """Write a file into the local validation workspace."""
        destination = self._resolve_workspace_file(workspace, file_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(destination.write_text, content, encoding="utf-8")

    @staticmethod
    def _resolve_workspace_file(workspace: Path, file_path: str) -> Path:
        """Resolve a repo-relative path inside the validation workspace."""
        resolved_workspace = workspace.resolve()
        candidate = (resolved_workspace / Path(file_path)).resolve()
        if not candidate.is_relative_to(resolved_workspace):
            raise ValueError(f"Refusing to write outside the validation workspace: {file_path}")
        return candidate

    def _detect_validation_command(self, workspace: Path) -> tuple[str, str]:
        """Pick a sandbox validation command based on the repo snapshot."""
        if (workspace / "package.json").exists():
            if (workspace / "yarn.lock").exists():
                return (
                    "if [ -f yarn.lock ] && command -v yarn >/dev/null 2>&1; "
                    "then yarn test; else npm test; fi",
                    "node:20-alpine",
                )
            return "npm test", "node:20-alpine"

        if (workspace / "tests").is_dir() or self._workspace_uses_pytest(workspace):
            return "python -m pytest", "python:3.10-alpine"

        return "python -m compileall .", "python:3.10-alpine"

    @staticmethod
    def _workspace_uses_pytest(workspace: Path) -> bool:
        """Detect whether the repo snapshot appears to use pytest."""
        for manifest in (
            "pyproject.toml",
            "requirements.txt",
            "requirements-dev.txt",
            "setup.cfg",
            "setup.py",
            "tox.ini",
        ):
            manifest_path = workspace / manifest
            if not manifest_path.exists():
                continue

            with contextlib.suppress(OSError, UnicodeDecodeError):
                if "pytest" in manifest_path.read_text(encoding="utf-8").lower():
                    return True

        return False

    def _append_local_validation_failure_prompt(
        self,
        prompt: str,
        sandbox_result: dict[str, Any],
    ) -> str:
        """Append sandbox validation logs to the LLM prompt for self-correction."""
        sandbox_output = self._format_sandbox_output(sandbox_result)
        return (
            f"{prompt}\n\n"
            "Local Validation Failure:\n"
            "I ran the test suite locally with your fix, but it failed. Here is the output:\n"
            f"```text\n{sandbox_output}\n```\n"
            "Please analyze this local failure and provide a corrected fix."
        )

    @staticmethod
    def _format_sandbox_output(sandbox_result: dict[str, Any]) -> str:
        """Format sandbox stdout and stderr into a compact prompt payload."""
        stdout = (sandbox_result.get("stdout") or "").strip()
        stderr = (sandbox_result.get("stderr") or "").strip()
        exit_code = sandbox_result.get("exit_code")

        parts = []
        if stdout:
            parts.append(f"STDOUT:\n{stdout}")
        if stderr:
            parts.append(f"STDERR:\n{stderr}")
        if not parts:
            parts.append("No sandbox output was captured.")
        parts.append(f"Exit code: {exit_code}")

        combined = "\n\n".join(parts)
        if len(combined) > 4000:
            return combined[:4000] + "\n... (truncated)"
        return combined

    async def _close_ci_retry_limited_pr(
        self,
        *,
        owner: str,
        repo: str,
        repo_full: str,
        pr_number: int,
        pr_data: dict,
    ) -> None:
        """Close a PR after exhausting the CI auto-heal retry budget."""
        logger.warning(
            "  CI fix limit (%d) reached for PR #%d; closing PR",
            self.MAX_CI_RETRIES,
            pr_number,
        )
        try:
            await self._github.close_pull_request(
                owner,
                repo,
                pr_number,
                comment=random.choice(GITHUB_REPLIES["CI_LIMIT_CLOSE"]).format(
                    attempts=self.MAX_CI_RETRIES,
                ),
            )
        except GitHubAPIError as exc:
            logger.warning("  Could not close PR #%d: %s", pr_number, exc)

        if self._notifier:
            repo_url = pr_data.get("html_url", f"https://github.com/{repo_full}")
            await self._notifier.send_message(
                f"[SURRENDER] PR closed due to max CI retries "
                f"({self.MAX_CI_RETRIES}/{self.MAX_CI_RETRIES}) hit on {repo_url}"
            )

    @staticmethod
    def _guess_file_from_traceback(traceback: str, diff: str) -> str | None:
        """Try to extract the most likely file path from a traceback or diff."""
        # Look for Python File "..." patterns
        file_matches = re.findall(r'File "([^"]+)"', traceback)
        if file_matches:
            # Return the last file mentioned (closest to error)
            path = file_matches[-1]
            # Strip absolute prefixes common in CI
            for prefix in ("/home/runner/work/", "/github/workspace/"):
                if path.startswith(prefix):
                    # e.g. /home/runner/work/repo/repo/src/main.py → src/main.py
                    parts = path[len(prefix):].split("/", 2)
                    if len(parts) >= 3:
                        return parts[2]
            return path

        # Fallback: first changed file from diff
        diff_files = re.findall(r"^\+\+\+ b/(.+)$", diff, re.MULTILINE)
        if diff_files:
            return diff_files[0]

        return None
