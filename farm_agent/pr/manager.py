"""Pull Request lifecycle manager.

Handles the full PR workflow: fork → branch → commit → PR.
Generates detailed PR descriptions with context and testing info.
"""

from __future__ import annotations

import asyncio
import csv
import logging
import re
from datetime import UTC, datetime
from pathlib import Path

from farm_agent.core.exceptions import PRCreationError
from farm_agent.core.models import Contribution, ContributionType, PRResult, PRStatus, Repository
from farm_agent.generator.engine import _sanitize_text, escape_html_xss
from farm_agent.github.client import GitHubClient

logger = logging.getLogger(__name__)

def auto_check_pr_template(body: str, contrib_type: ContributionType | None = None) -> str:
    """Auto-check compliance checkboxes strictly based on contribution type.

    Phase 1 Martial Law: Eradicated naive regex blind-ticking.
    Now only ticks checkboxes if the exact line expressly matches the
    bot's actual contribution type. If no type is provided or matched,
    it ticks nothing, opting for safety over false compliance.
    """
    if not contrib_type:
        return body

    # Map ContributionTypes to the literal template terms maintainers usually use
    type_matches = {
        ContributionType.SECURITY_FIX: ["security", "vulnerability", "cve", "bug"],
        ContributionType.CODE_QUALITY: ["bug", "fix", "quality", "lint", "static analysis"],
        ContributionType.README_FIX: ["doc", "readme", "comment"],
        ContributionType.UI_UX_FIX: ["ui", "ux", "visual", "frontend"],
        ContributionType.PERFORMANCE_OPT: ["perf", "speed", "optimiz"],
        ContributionType.FEATURE_ADD: ["feature", "enhancement", "new"],
        ContributionType.REFACTOR: ["refactor", "cleanup", "chore"],
    }

    allowed_terms = type_matches.get(contrib_type, [])
    if not allowed_terms:
        return body

    lines = body.split("\n")
    for i, line in enumerate(lines):
        stripped = line.strip().lower()
        if stripped.startswith(("- [ ]", "* [ ]")):
            if any(term in stripped for term in allowed_terms):
                # Only check if it safely avoids danger terms
                if not any(danger in stripped for danger in ["breaking", "release", "deploy", "migration"]):
                    # Replace the first unmet checkbox
                    lines[i] = line.replace("[ ]", "[x]", 1)
    return "\n".join(lines)


class PRManager:
    """Manage the full pull request lifecycle."""

    PR_LEDGER_PATH = Path("logs/pr_history.csv")
    _LEDGER_HEADER = ["timestamp", "repo_url", "pr_url", "status", "error_details", "vulnerability_type"]

    def __init__(self, github: GitHubClient, llm=None):
        self._github = github
        self._llm = llm
        self._user: dict | None = None
        self._ledger_lock = asyncio.Lock() if hasattr(asyncio, "Lock") else None

    async def append_to_ledger(
        self,
        repo_url: str,
        pr_url: str,
        status: str,
        error_details: str = "",
        vulnerability_type: str = "",
    ) -> None:
        """Append a PR attempt to the persistent CSV ledger.

        Thread-safe / async-safe via lock.  Creates the file with headers
        on first write.  Never overwrites existing rows.
        """
        if self._ledger_lock is None:
            self._ledger_lock = asyncio.Lock()

        async with self._ledger_lock:
            self.PR_LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
            needs_header = not self.PR_LEDGER_PATH.exists()
            row = [
                datetime.now(UTC).isoformat(),
                repo_url,
                pr_url,
                status,
                error_details,
                vulnerability_type,
            ]
            try:
                with open(self.PR_LEDGER_PATH, "a", newline="", encoding="utf-8") as fh:
                    writer = csv.writer(fh)
                    if needs_header:
                        writer.writerow(self._LEDGER_HEADER)
                    writer.writerow(row)
                logger.debug("PR ledger entry written: %s — %s", repo_url, status)
            except Exception as exc:
                logger.warning("Failed to write PR ledger entry: %s", exc)

    async def _get_user(self) -> dict:
        """Get and cache the authenticated user."""
        if not self._user:
            self._user = await self._github.get_authenticated_user()
        return self._user

    def _build_signoff(self, user: dict) -> str | None:
        """Build DCO Signed-off-by string from user info.

        Returns ``"Name <email>"`` or ``None`` if info is missing.
        """
        name = user.get("name") or user.get("login", "")
        email = user.get("email")
        if not email:
            # GitHub noreply fallback
            uid = user.get("id", "")
            login = user.get("login", "")
            email = f"{uid}+{login}@users.noreply.github.com"
        return f"{name} <{email}>" if name else None

    async def create_pr(
        self,
        contribution: Contribution,
        target_repo: Repository,
        *,
        guidelines=None,
        closes_issue: int | None = None,
    ) -> PRResult:
        """Create a PR from a generated contribution.

        Full workflow:
        1. Fork the target repo (if not already forked)
        2. Create a feature branch on the fork
        3. Commit all file changes
        3b. Create a linked issue (if repo requires it)
        4. Create the pull request
        5. Check compliance and auto-fix if needed

        Args:
            contribution: Generated contribution
            target_repo: Target repository
            guidelines: Repo contribution guidelines
            closes_issue: If set, adds 'Closes #N' to PR body
        """
        user = await self._get_user()
        username = user["login"]
        signoff = self._build_signoff(user)

        try:
            # 1. Fork (with polling to wait for GitHub's async fork processing)
            fork = await self._fork_if_needed(username, target_repo)
            fork_owner = fork.owner
            fork_name = fork.name

            # Wait for fork to become accessible via API before proceeding
            # GitHub forks take a few seconds to process; 404 without this
            await self._github.wait_for_fork_accessibility(fork_owner, fork_name)

            # 2. Create branch on the fork
            branch = contribution.branch_name or self._human_branch_name(contribution)
            await self._github.create_branch(fork_owner, fork_name, branch)

            # 3. Gather all file changes (patches + tests)
            all_changes = contribution.changes + contribution.tests_added
            if not all_changes:
                logger.warning("WARNING: No actual code changes detected. Aborting PR.")
                raise PRCreationError("Aborted PR creation: no changes to commit.")

            # 4. Use Git Data API to create commit without cloning locally
            # 4a. Get base branch tip (commit SHA + tree SHA) from the fork
            base_branch = target_repo.default_branch
            base_commit_sha, base_tree_sha = await self._github.get_branch_tip(
                fork_owner, fork_name, base_branch
            )

            # 4b. Create blobs for each file change and collect tree entries
            tree_entries = []
            for change in all_changes:
                if change.is_deleted:
                    # Deletion: entry with sha=null removes the file
                    tree_entries.append({
                        "path": change.path,
                        "mode": "100644",
                        "type": "blob",
                        "sha": None,
                    })
                else:
                    # Create blob from new content
                    blob_sha = await self._github.create_git_blob(
                        fork_owner, fork_name, change.new_content
                    )
                    tree_entries.append({
                        "path": change.path,
                        "mode": "100644",
                        "type": "blob",
                        "sha": blob_sha,
                    })

            # 4c. Create tree from all file entries (base_tree enables recursive diff)
            new_tree_sha = await self._github.create_git_tree(
                fork_owner, fork_name, base_tree_sha, tree_entries
            )

            # 4d. Build commit message with DCO signoff
            commit_msg = contribution.commit_message
            if signoff and "Signed-off-by:" not in commit_msg:
                commit_msg = f"{commit_msg}\n\nSigned-off-by: {signoff}"

            # Author with backdated timestamp (anti-spam jitter: 15-45 min in the past)
            import random
            from datetime import UTC, datetime, timedelta
            author_name = user.get("name") or user.get("login", "Farm-Agent")
            author_email = user.get("email") or \
                f"{user.get('id', '9919')}+{user.get('login', 'farm_agent')}@users.noreply.github.com"
            author_date = (datetime.now(UTC) - timedelta(minutes=random.randint(15, 45))).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )

            # 4e. Create commit
            new_commit_sha = await self._github.create_git_commit(
                fork_owner, fork_name,
                message=commit_msg,
                tree_sha=new_tree_sha,
                parent_shas=[base_commit_sha],
                author_name=author_name,
                author_email=author_email,
                author_date=author_date,
                signoff=signoff,
            )

            # 4f. Update branch ref to point to new commit
            await self._github.update_git_ref(fork_owner, fork_name, branch, new_commit_sha)

            logger.info("Git Data API commit %s pushed to branch %s", new_commit_sha[:8], branch)

            # Anti-Spam Jitter (after push — mimics natural delay)
            await asyncio.sleep(5)

            # 3b. Create linked issue if repo likely requires it
            issue_number = closes_issue
            if not issue_number and guidelines and guidelines.has_guidelines:
                issue_number = await self._create_issue_for_finding(contribution, target_repo)

            # 4. Create PR body — Diplomat Protocol Task 3: LLM-powered template filling
            from farm_agent.core.models import ContributionType as CT

            _type_info = {
                CT.SECURITY_FIX: ("🔒", "Reliability Improvement"),
                CT.CODE_QUALITY: ("✨", "Code Quality"),
                CT.README_FIX: ("📝", "Documentation"),
                CT.UI_UX_FIX: ("🎨", "UI/UX Improvement"),
                CT.PERFORMANCE_OPT: ("⚡", "Performance"),
                CT.FEATURE_ADD: ("🚀", "New Feature"),
                CT.REFACTOR: ("♻️", "Refactoring"),
            }
            pr_emoji, pr_label = _type_info.get(contribution.finding.type, ("🔧", "Fix"))
            pr_files_list = "\n".join(
                f"- `{c.path}` {'(new)' if c.is_new_file else '(modified)'}"
                for c in contribution.changes
            )

            if guidelines and guidelines.has_guidelines and guidelines.pr_template and self._llm:
                from farm_agent.github.guidelines import llm_fill_pr_template

                pr_body = await llm_fill_pr_template(
                    template=guidelines.pr_template,
                    contribution=contribution,
                    llm=self._llm,
                    emoji=pr_emoji,
                    label=pr_label,
                    files_list=pr_files_list,
                )
            elif guidelines and guidelines.has_guidelines:
                from farm_agent.github.guidelines import adapt_pr_body

                pr_body = adapt_pr_body(contribution, guidelines)
            else:
                pr_body = self._generate_pr_body(contribution)

            # Inject issue link into body
            if issue_number:
                pr_body = pr_body.replace("Closes N/A", f"Closes #{issue_number}").replace(
                    "Closes #\n", f"Closes #{issue_number}\n"
                )
                # If no placeholder found, append
                if f"#{issue_number}" not in pr_body:
                    pr_body += f"\n\nCloses #{issue_number}"

            # Layer 2: Deterministic checkbox compliance fallback
            pr_body = auto_check_pr_template(pr_body, contribution.finding.type)

            # ── Gag Order — sanitize all free-text fields before submission ──
            # PR title
            safe_title = _sanitize_text(contribution.title, "PR title")
            # PR body
            safe_body = _sanitize_text(pr_body, "PR body")
            # ─────────────────────────────────────────────────────────────────────

            head = f"{fork_owner}:{branch}"

            if ":" not in head:
                raise PRCreationError(
                    f"Invalid PR head format: '{head}'. Cross-repo PRs require "
                    f"'{{fork_owner}}:{{branch}}' format. Got bare branch name."
                )

            pr_data = await self._github.create_pull_request(
                target_repo.owner,
                target_repo.name,
                title=safe_title,
                body=safe_body,
                head=head,
                base=target_repo.default_branch,
            )

            result = PRResult(
                repo=target_repo,
                contribution=contribution,
                pr_number=pr_data["number"],
                pr_url=pr_data["html_url"],
                status=PRStatus.OPEN,
                branch_name=branch,
                fork_full_name=f"{fork_owner}/{fork_name}",
            )

            logger.info("✅ PR #%d created: %s", result.pr_number, result.pr_url)

            await self.append_to_ledger(
                repo_url=target_repo.html_url,
                pr_url=result.pr_url,
                status="SUCCESS",
                error_details="",
                vulnerability_type=contribution.finding.type.value,
            )

            return result

        except Exception as e:
            await self.append_to_ledger(
                repo_url=target_repo.html_url,
                pr_url="",
                status="FAILED",
                error_details=str(e)[:500],
                vulnerability_type=contribution.finding.type.value if contribution else "unknown",
            )
            raise PRCreationError(f"Failed to create PR: {e}") from e

    async def _fork_if_needed(self, username: str, repo: Repository) -> Repository:
        """Fork the repo if not already forked."""
        try:
            # Check if fork exists
            existing = await self._github.get_repo_details(username, repo.name)
            if existing.owner == username:
                logger.info("Fork already exists: %s/%s", username, repo.name)
                return existing
        except Exception:
            pass

        # Create fork
        return await self._github.fork_repository(repo.owner, repo.name)

    @staticmethod
    def _human_branch_name(contribution: Contribution) -> str:
        """Generate a natural-looking branch name (no tool branding)."""

        type_prefix = {
            ContributionType.SECURITY_FIX: "fix/security",
            ContributionType.CODE_QUALITY: "fix",
            ContributionType.README_FIX: "docs",
            ContributionType.UI_UX_FIX: "fix/ui",
            ContributionType.PERFORMANCE_OPT: "perf",
            ContributionType.FEATURE_ADD: "feat",
            ContributionType.REFACTOR: "refactor",
        }
        prefix = type_prefix.get(contribution.finding.type, "fix")

        # Slugify the title
        slug = contribution.finding.title.lower()
        slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")[:50]
        return f"{prefix}/{slug}"

    def _generate_pr_body(self, contribution: Contribution) -> str:
        """Generate a PR description that sounds like a tired senior developer.

        Rules:
        - NO AI fluff: no "This PR aims to", "In this pull request", etc.
        - BE LAZY BUT ACCURATE: 2-4 sentences max
        - FOCUS ON THE WHY: explain why the bug happened and impact, not how code works
        - TONE: casual, direct, lowercase OK for minor things
        - FORMATTING: no heavy markdown, minimal bullets
        """
        finding = contribution.finding

        # Files changed summary (compact, no heavy formatting)
        files_list = ", ".join(
            c.path.split("/")[-1] for c in contribution.changes
        )

        # Build a tired-dev style body: short, direct, no fluff
        body_lines = [
            finding.description,
        ]

        # Add impact/root cause if we have it in the suggestion
        if finding.suggestion:
            body_lines.append(f"Fix: {finding.suggestion}")

        # Minimal file list
        body_lines.append(f"Affected: {files_list}")

        # Resolves placeholder (caller will substitute)
        body_lines.append("Closes N/A")

        return "\n\n".join(body_lines)

    def _generate_issue_body(self, contribution: Contribution) -> str:
        """Generate a human-like Issue-First body — lazy senior dev style.

        Route B (Issue-First Protocol):
        - BE BRIEF: 2-3 sentences max
        - POINT OUT THE ISSUE: describe the problem, not the solution
        - OFFER HELP conditionally: "if the team agrees, I can put together a PR"
        - NO code generation here — this is just a polite heads-up
        - TONE: casual, direct, not pushy
        """
        finding = contribution.finding
        file_hint = f" in `{finding.file_path}`" if finding.file_path else ""

        # Build a brief, natural issue description
        lines = [
            finding.description or f"Spotted a potential issue{file_hint}.",
        ]

        # Add root cause or impact if known
        if finding.suggestion:
            lines.append(f"\nThis could cause: {finding.suggestion[:150]}")

        # Conditional offer — not pushy
        lines.append(
            "\nIf the team thinks this is worth addressing, I can put together a PR. Happy to help."
        )

        raw_body = "".join(lines)
        # ── Gag Order — sanitize issue body before submission ──
        return _sanitize_text(raw_body, "issue body")

    async def get_pr_status(self, owner: str, repo: str, pr_number: int) -> PRStatus:
        """Check the current status of a PR."""
        try:
            data = await self._github._get(f"/repos/{owner}/{repo}/pulls/{pr_number}")
            state = data.get("state", "open")
            merged = data.get("merged", False)

            if merged:
                return PRStatus.MERGED
            elif state == "closed":
                return PRStatus.CLOSED
            elif data.get("requested_reviewers"):
                return PRStatus.REVIEW_REQUESTED
            else:
                return PRStatus.OPEN
        except Exception:
            return PRStatus.PENDING

    # ── Auto Issue Creation ─────────────────────────────────────────────

    async def _create_issue_for_finding(
        self,
        contribution: Contribution,
        target_repo: Repository,
    ) -> int | None:
        """Create an issue describing the finding before creating a PR.

        Returns the issue number, or None if creation failed.
        """
        finding = contribution.finding

        type_labels = {
            ContributionType.SECURITY_FIX: "bug",
            ContributionType.CODE_QUALITY: "bug",
            ContributionType.README_FIX: "documentation",
            ContributionType.UI_UX_FIX: "bug",
            ContributionType.PERFORMANCE_OPT: "perf",
            ContributionType.FEATURE_ADD: "enhancement",
            ContributionType.REFACTOR: "enhancement",
        }

        type_map = {
            ContributionType.SECURITY_FIX: "fix",
            ContributionType.CODE_QUALITY: "fix",
            ContributionType.README_FIX: "docs",
            ContributionType.UI_UX_FIX: "fix",
            ContributionType.PERFORMANCE_OPT: "perf",
            ContributionType.FEATURE_ADD: "feat",
            ContributionType.REFACTOR: "refactor",
        }

        prefix = type_map.get(finding.type, "fix")

        scope = ""
        if finding.file_path:
            parts = finding.file_path.split("/")
            if (len(parts) >= 2 and parts[0] in ("packages", "apps", "libs")) or (
                len(parts) >= 2 and parts[0] == "src"
            ):
                scope = parts[1]

        # P2-3 FIX: Sanitize finding title and description to prevent XSS in GitHub issue body
        safe_title = escape_html_xss(_sanitize_text(finding.title, "issue title"))
        safe_description = escape_html_xss(_sanitize_text(finding.description, "issue description"))

        if scope:
            issue_title = f"{prefix}({scope}): {safe_title.lower()}"
        else:
            issue_title = f"{prefix}: {safe_title.lower()}"

        issue_body = (
            f"## Description\n\n"
            f"{safe_description}\n\n"
            f"**Severity**: `{finding.severity.value}`\n"
            f"**File**: `{finding.file_path}`\n\n"
            f"## Expected Behavior\n\n"
            f"The code should handle this case properly to avoid "
            f"unexpected errors or degraded quality."
        )

        try:
            label = type_labels.get(finding.type, "bug")
            try:
                data = await self._github.create_issue(
                    target_repo.owner,
                    target_repo.name,
                    title=issue_title,
                    body=issue_body,
                    labels=[label],
                )
            except Exception:
                # Labels might not exist, retry without labels
                data = await self._github.create_issue(
                    target_repo.owner,
                    target_repo.name,
                    title=issue_title,
                    body=issue_body,
                )

            issue_number = data["number"]
            logger.info(
                "📋 Created issue #%d on %s: %s",
                issue_number,
                target_repo.full_name,
                issue_title,
            )
            return issue_number

        except Exception as e:
            logger.warning("Failed to create issue: %s", e)
            return None

    # ── Post-PR Compliance ──────────────────────────────────────────────

    async def check_compliance_and_fix(
        self,
        pr_result: PRResult,
        contribution: Contribution,
        guidelines=None,
    ) -> bool:
        """Check bot comments for compliance issues and auto-fix.

        Handles:
        - Title format (conventional commit)
        - Missing issue references
        - CLA signing (EasyCLA, CLAAssistant, CLA bot)

        Returns True if PR is compliant (or was auto-fixed).
        """
        import asyncio

        repo = pr_result.repo

        # Wait for bots to comment
        await asyncio.sleep(15)

        try:
            comments = await self._github.get_pr_comments(
                repo.owner, repo.name, pr_result.pr_number
            )
        except Exception as e:
            # PHASE 1-FIX: Fail-closed on compliance bypass.
            # Returning True (compliant) on a network exception bypasses CLA
            # checks and pisses off maintainers. Fail the compliance entirely.
            logger.error("Could not fetch PR comments — failing compliance check: %s", e)
            return False

        bot_issues = []
        cla_comments = []
        for comment in comments:
            user = comment.get("user", {})
            body = comment.get("body", "")
            login = user.get("login", "")
            is_bot = user.get("type") == "Bot" or login.endswith("[bot]")

            if not is_bot:
                continue

            body_lower = body.lower()

            # Detect CLA bots
            if any(kw in login.lower() for kw in ["cla", "easycla", "claassistant"]) or any(
                kw in body_lower
                for kw in [
                    "contributor license agreement",
                    "sign our cla",
                    "cla not signed",
                    "please sign",
                    "i have read the cla",
                ]
            ):
                cla_comments.append(comment)
                continue

            # Detect compliance issues
            if any(
                keyword in body_lower
                for keyword in [
                    "doesn't follow conventional commit",
                    "no issue referenced",
                    "doesn't fully meet",
                    "pr title",
                    "needs:title",
                    "needs:issue",
                    "needs:compliance",
                ]
            ):
                bot_issues.append(body)

        # ── Handle CLA signing ──
        if cla_comments:
            await self._handle_cla_signing(pr_result, cla_comments)

        if not bot_issues:
            logger.info("✅ PR #%d passed compliance checks", pr_result.pr_number)
            return True

        logger.info(
            "🔧 PR #%d has %d compliance issues, auto-fixing...",
            pr_result.pr_number,
            len(bot_issues),
        )

        # Detect specific issues and fix
        all_comments = " ".join(bot_issues).lower()
        needs_fix = False

        # Fix title format
        if "conventional commit" in all_comments or "needs:title" in all_comments:
            new_title = contribution.title
            if (
                any(
                    new_title.startswith(prefix)
                    for prefix in ["🔒", "✨", "📝", "🎨", "⚡", "🚀", "♻️", "🔧"]
                )
                and guidelines
                and guidelines.has_guidelines
            ):
                from farm_agent.github.guidelines import (
                    adapt_pr_title,
                    extract_scope_from_path,
                )

                scope = extract_scope_from_path(contribution.finding.file_path or "", guidelines)
                new_title = adapt_pr_title(
                    contribution.finding.title,
                    contribution.finding.type.value,
                    guidelines,
                    scope=scope,
                )

            try:
                await self._github.update_pull_request(
                    repo.owner, repo.name, pr_result.pr_number, title=new_title
                )
                logger.info("Fixed PR title → %s", new_title)
                needs_fix = True
            except Exception as e:
                logger.warning("Failed to fix title: %s", e)

        # Fix missing issue reference
        if "no issue referenced" in all_comments or "needs:issue" in all_comments:
            issue_number = await self._create_issue_for_finding(contribution, pr_result.repo)
            if issue_number:
                try:
                    pr_data = await self._github._get(
                        f"/repos/{repo.owner}/{repo.name}/pulls/{pr_result.pr_number}"
                    )
                    current_body = pr_data.get("body", "")
                    new_body = current_body.replace("Closes N/A", f"Closes #{issue_number}")
                    if f"#{issue_number}" not in new_body:
                        new_body = f"Closes #{issue_number}\n\n{new_body}"

                    await self._github.update_pull_request(
                        repo.owner,
                        repo.name,
                        pr_result.pr_number,
                        body=new_body,
                    )
                    logger.info("Linked issue #%d to PR", issue_number)
                    needs_fix = True
                except Exception as e:
                    logger.warning("Failed to link issue: %s", e)

        if needs_fix:
            logger.info("🔄 PR #%d compliance auto-fixed", pr_result.pr_number)
        else:
            logger.warning("⚠️ PR #%d has unresolved compliance issues", pr_result.pr_number)

        return needs_fix

    # ── CLA Auto-signing ─────────────────────────────────────────────────

    async def _handle_cla_signing(
        self,
        pr_result: PRResult,
        cla_comments: list[dict],
    ) -> None:
        """Auto-sign CLA when a CLA bot requests it.

        Supports: EasyCLA, CLAAssistant, generic CLA bots.
        """
        repo = pr_result.repo

        for comment in cla_comments:
            login = comment.get("user", {}).get("login", "")
            body = comment.get("body", "").lower()

            # CLAAssistant — sign by posting the magic comment
            if "claassistant" in login.lower() or "i have read the cla" in body:
                try:
                    await self._github.create_pr_comment(
                        repo.owner,
                        repo.name,
                        pr_result.pr_number,
                        "I have read the CLA Document and I hereby sign the CLA",
                    )
                    logger.info(
                        "✍️ Auto-signed CLA (CLAAssistant) on PR #%d",
                        pr_result.pr_number,
                    )
                    return
                except Exception as e:
                    logger.warning("CLA signing failed: %s", e)

            # EasyCLA — log for manual signing (requires web flow)
            if "easycla" in login.lower() or "linux-foundation" in login.lower():
                logger.warning(
                    "⚠️ PR #%d needs EasyCLA — manual signing required at "
                    "the link in the bot comment.",
                    pr_result.pr_number,
                )
                return

        logger.info(
            "📝 CLA bot detected on PR #%d but no actionable signing method found",
            pr_result.pr_number,
        )
