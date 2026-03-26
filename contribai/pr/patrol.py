"""PR Patrol — monitor and respond to review feedback on open PRs.

Scans ContribAI PRs for maintainer review comments, uses LLM to
classify feedback, generates code fixes, and pushes updates.
"""

from __future__ import annotations

import contextlib
import logging
import random
import re

import yaml

from contribai.core.exceptions import GitHubAPIError
from contribai.core.models import (
    FeedbackAction,
    FeedbackItem,
    PatrolResult,
)
from contribai.github.client import GitHubClient
from contribai.llm.provider import LLMProvider

logger = logging.getLogger(__name__)

# Comments we already posted — skip these
OUR_REPLY_MARKERS = [
    "I have read the CLA Document",
    "contribai",
    "<!-- contribai-patrol -->",
]

# ── Human Developer Persona ────────────────────────────────────────────────
# Randomized natural English phrases for all GitHub interactions.
# This is the soul of "Super Human Mode" — no bot should ever
# sound like a bot.  Every reply picks a variant via random.choice().

GITHUB_REPLIES: dict[str, list[str]] = {
    # After pushing a code fix in response to review feedback
    "FIX_APPLIED": [
        "Good catch! I just pushed a commit to address this. Let me know if it looks better now.",
        "Updated in the latest commit. Thanks for pointing it out!",
        "Done — I've adjusted the logic as you suggested.",
        "Makes sense, I've fixed this in the newest push.",
        "Great feedback, just pushed the update. Happy to iterate further if needed.",
        "Agreed, that's cleaner. Pushed the change just now.",
    ],
    # Commit messages for code fixes
    "COMMIT_FIX": [
        "fix: {summary}",
        "fix: update based on review — {summary}",
        "fix: apply reviewer suggestion — {summary}",
        "fix: adjust logic per feedback — {summary}",
    ],
    # Prepended to LLM-generated question answers
    "QUESTION_OPENER": [
        "Great question!",
        "Good question, happy to clarify.",
        "Sure thing, let me explain.",
        "Thanks for asking!",
        "Yeah, fair point — here's the reasoning:",
    ],
    # Appended to LLM-generated question answers
    "QUESTION_CLOSER": [
        "Let me know if that clears things up!",
        "Happy to discuss further if anything's unclear.",
        "Hope that helps — feel free to follow up.",
    ],
    # When closing a PR due to hostile rejection
    "HOSTILE_CLOSE": [
        "Understood, closing this PR. Apologies for the noise — this repo won't be targeted again.",
        "Fair enough, I'll close this out. Sorry for the trouble, and this repo is noted.",
        "Got it, closing now. Apologies for any inconvenience.",
    ],
    # Comment after pushing a CI fix
    "CI_FIX_APPLIED": [
        "Looks like `{check_name}` was failing — I pushed a fix for `{file_path}`. Hopefully that resolves it.",  # noqa: E501
        "Spotted the `{check_name}` failure and pushed a fix in `{file_path}`. Let me know if CI goes green now.",  # noqa: E501
        "Just pushed a fix for the `{check_name}` failure (updated `{file_path}`). Fingers crossed!",  # noqa: E501
        "CI was unhappy with `{check_name}` — I've patched `{file_path}` in the latest commit.",
    ],
    # When closing PR after exhausting CI fix attempts
    "CI_LIMIT_CLOSE": [
        "CI keeps failing after {attempts} fix attempts on my end. Closing this to avoid further noise — sorry about that!",  # noqa: E501
        "I've tried to fix CI {attempts} times but it's still failing. Going to close this PR to keep things clean. Apologies!",  # noqa: E501
        "After {attempts} attempts I haven't been able to get CI green. Closing this out — sorry for the churn.",  # noqa: E501
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
        self._notifier = kwargs.get("notifier", None)
        self._user: dict | None = None

    async def _get_user(self) -> dict:
        if not self._user:
            self._user = await self._github.get_authenticated_user()
        return self._user

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
                        fixed = await self._handle_code_fix(owner, repo_name, pr, pr_data, item)
                        if fixed:
                            result.fixes_pushed += 1
                            result.replies_sent += 1
                            if self._notifier and not dry_run:
                                await self._notifier.send_message(
                                    f"🛡️ <b>[PATROL]</b> Action Taken!\nRepo: <code>{pr['repo']}</code>\nAction: Pushed Code Fix\nURL: {pr_data.get('html_url', pr.get('pr_url', ''))}"
                                )
                    elif item.action == FeedbackAction.QUESTION:
                        answered = await self._handle_question(owner, repo_name, pr, pr_data, item)
                        if answered:
                            result.replies_sent += 1
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

        from contribai.core.exceptions import LLMRateLimitError

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
            except Exception as e:
                logger.warning("Failed to classify feedback: %s", e)
                break

        # Fall back: treat all as potential code changes
        return [
            FeedbackItem(
                comment_id=f["id"],
                author=f["author"],
                body=f["body"],
                action=FeedbackAction.CODE_CHANGE,
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
        except Exception:
            logger.warning("Could not parse classification YAML")
            return items

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
    ) -> bool:
        """Generate and push a code fix based on review feedback."""
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

            # Get PR diff for context
            try:
                diff = await self._github.get_pr_diff(owner, repo, pr_data["number"])
                # Truncate diff if too long
                if len(diff) > 8000:
                    diff = diff[:8000] + "\n... (truncated)"
            except Exception:
                diff = ""

            # Generate fix via LLM
            prompt = self._build_fix_prompt(feedback, file_content, file_path, diff)
            response = await self._llm.complete(
                prompt,
                system=(
                    "You are a developer fixing code based on a PR review comment. "
                    "Return ONLY the complete fixed file content. No explanations. "
                    "Make the MINIMUM change to address the feedback."
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

            # Push fix
            user = await self._get_user()
            signoff = self._build_signoff(user)
            commit_msg = random.choice(GITHUB_REPLIES["COMMIT_FIX"]).format(
                summary=feedback.body[:60],
            )
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
            logger.info("  Pushed fix for %s: %s", file_path, feedback.body[:60])

            # Reply to comment — sound like a real human developer
            reply_body = (
                random.choice(GITHUB_REPLIES["FIX_APPLIED"])
                + "\n\n<!-- contribai-patrol -->"
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
                f"Write a concise, helpful reply (2-4 sentences). "
                f"Be polite and professional. Explain the reasoning behind our change."
            )

            response = await self._llm.complete(
                prompt,
                system=(
                    "You are a developer responding to a code review question. "
                    "Be concise, professional, and helpful."
                ),
                temperature=0.3,
            )

            raw_answer = response.strip()
            if not raw_answer:
                return False

            # Wrap LLM answer with a natural human opener/closer
            opener = random.choice(GITHUB_REPLIES["QUESTION_OPENER"])
            closer = random.choice(GITHUB_REPLIES["QUESTION_CLOSER"])
            reply_body = f"{opener}\n\n{raw_answer}\n\n{closer}\n\n<!-- contribai-patrol -->"

            # Post reply
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

    # ── CI Auto-Healing ────────────────────────────────────────────────────

    MAX_CI_FIX_ATTEMPTS = 2

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

        if attempts >= self.MAX_CI_FIX_ATTEMPTS:
            logger.warning(
                "  🚫 CI fix limit (%d) reached for PR #%d — closing PR",
                self.MAX_CI_FIX_ATTEMPTS, pr_number,
            )
            if not dry_run:
                try:
                    await self._github.close_pull_request(
                        owner, repo, pr_number,
                        comment=random.choice(GITHUB_REPLIES["CI_LIMIT_CLOSE"]).format(
                            attempts=self.MAX_CI_FIX_ATTEMPTS,
                        ),
                    )
                except GitHubAPIError as exc:
                    logger.warning("  ⚠️ Could not close PR #%d: %s", pr_number, exc)
            return True

        # Pick the first failed run to fix
        failed = failed_runs[0]
        check_name = failed.get("name", "CI")
        check_run_id = failed.get("id", 0)

        logger.info(
            "  🔴 CI check '%s' failed on PR #%d (attempt %d/%d)",
            check_name, pr_number, attempts + 1, self.MAX_CI_FIX_ATTEMPTS,
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

        fixed = await self._handle_ci_failure(
            owner, repo, pr_record, pr_data, traceback, check_name,
        )

        if fixed:
            result.ci_fixes_pushed += 1
            if self._memory:
                await self._memory.increment_ci_fix_attempts(repo_full, pr_number)

        return fixed

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

    async def _handle_ci_failure(
        self,
        owner: str,
        repo: str,
        pr_record: dict,
        pr_data: dict,
        traceback: str,
        check_name: str,
    ) -> bool:
        """Use LLM to fix a CI failure and push the fix."""
        try:
            head = pr_data.get("head", {})
            fork_owner = head.get("repo", {}).get("owner", {}).get("login", owner)
            fork_repo = head.get("repo", {}).get("name", repo)
            branch = head.get("ref", "main")

            # Get PR diff for context
            try:
                diff = await self._github.get_pr_diff(owner, repo, pr_data["number"])
                if len(diff) > 8000:
                    diff = diff[:8000] + "\n... (truncated)"
            except Exception:
                diff = ""

            prompt = (
                f"The CI pipeline (`{check_name}`) failed with this error:\n"
                f"```\n{traceback}\n```\n\n"
            )
            if diff:
                prompt += f"Here is the PR diff for context:\n```diff\n{diff}\n```\n\n"
            prompt += (
                "Please fix the code to resolve this CI failure. "
                "Return ONLY the complete fixed file content. "
                "No explanations. Make the MINIMUM change to fix the error."
            )

            response = await self._llm.complete(
                prompt,
                system=(
                    "You are a developer fixing CI failures. "
                    "Analyze the traceback, identify the broken file, "
                    "and return the complete corrected file content."
                ),
                temperature=0.2,
            )

            fixed_content = self._extract_fixed_content(response)
            if not fixed_content:
                logger.warning("  ⚠️ LLM returned empty fix for CI failure")
                return False

            # Try to determine file path from traceback
            file_path = self._guess_file_from_traceback(traceback, diff)
            if not file_path:
                logger.warning("  ⚠️ Could not determine file path from traceback")
                return False

            # Get file SHA
            try:
                resp = await self._github._get(
                    f"/repos/{fork_owner}/{fork_repo}/contents/{file_path}",
                    params={"ref": branch},
                )
                sha = resp.get("sha")
            except Exception:
                sha = None

            # Push fix
            user = await self._get_user()
            signoff = self._build_signoff(user)
            commit_msg = random.choice(GITHUB_REPLIES["COMMIT_CI_FIX"]).format(
                check_name=check_name,
            )
            await self._github.create_or_update_file(
                fork_owner, fork_repo, file_path, fixed_content,
                commit_msg, branch, sha=sha, signoff=signoff,
            )
            logger.info("  Pushed CI fix for '%s' on %s", check_name, file_path)

            # Post comment on PR — sound human
            ci_reply = (
                random.choice(GITHUB_REPLIES["CI_FIX_APPLIED"]).format(
                    check_name=check_name,
                    file_path=file_path,
                )
                + "\n\n<!-- contribai-patrol -->"
            )
            await self._github.create_pr_comment(
                owner, repo, pr_data["number"], ci_reply,
            )
            return True

        except Exception as e:
            logger.error("  ❌ CI auto-fix failed: %s", e)
            return False

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
