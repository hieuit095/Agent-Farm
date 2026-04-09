"""Contribution quality scorer.

Evaluates generated contributions before submission
to prevent low-quality PRs from being created.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from farm_agent.core.models import Contribution, ContributionType

logger = logging.getLogger(__name__)


@dataclass
class QualityReport:
    """Quality assessment of a contribution."""

    score: float  # 0.0 - 1.0
    passed: bool
    checks: dict[str, CheckResult]

    @property
    def summary(self) -> str:
        passed = sum(1 for c in self.checks.values() if c.passed)
        total = len(self.checks)
        return f"{passed}/{total} checks passed (score: {self.score:.0%})"


@dataclass
class CheckResult:
    """Result of a single quality check."""

    name: str
    passed: bool
    score: float  # 0.0 - 1.0
    reason: str


class QualityScorer:
    """Evaluates contribution quality before PR submission.

    Runs a series of heuristic checks to catch low-quality
    contributions that would likely be rejected by maintainers.
    """

    def __init__(self, min_score: float = 0.6):
        self._min_score = min_score

    def evaluate(self, contribution: Contribution) -> QualityReport:
        """Run all quality checks on a contribution.

        Args:
            contribution: The generated contribution to evaluate.

        Returns:
            QualityReport with individual check results and overall score.
        """
        checks = {}

        checks["has_changes"] = self._check_has_changes(contribution)
        checks["change_size"] = self._check_change_size(contribution)
        checks["commit_message"] = self._check_commit_message(contribution)
        checks["description"] = self._check_description(contribution)
        checks["no_debug_code"] = self._check_no_debug_code(contribution)
        checks["no_placeholders"] = self._check_no_placeholders(contribution)
        checks["file_coherence"] = self._check_file_coherence(contribution)

        total_score = sum(c.score for c in checks.values()) / len(checks)
        passed = total_score >= self._min_score

        report = QualityReport(score=total_score, passed=passed, checks=checks)
        logger.info("Quality check: %s", report.summary)
        return report

    def _check_has_changes(self, c: Contribution) -> CheckResult:
        """At least one meaningful file change."""
        has = len(c.changes) > 0 and any(len(ch.new_content.strip()) > 0 for ch in c.changes)
        return CheckResult(
            name="has_changes",
            passed=has,
            score=1.0 if has else 0.0,
            reason="Has file changes" if has else "No file changes",
        )

    def _check_change_size(self, c: Contribution) -> CheckResult:
        """Changes should be focused (not too big, not trivial)."""
        total_lines = sum(len(ch.new_content.splitlines()) for ch in c.changes)

        if total_lines == 0:
            return CheckResult("change_size", False, 0.0, "Empty changes")
        elif total_lines < 3:
            return CheckResult(
                "change_size",
                False,
                0.3,
                f"Very small change ({total_lines} lines)",
            )
        elif total_lines > 500:
            return CheckResult(
                "change_size",
                False,
                0.4,
                f"Very large change ({total_lines} lines)",
            )
        elif total_lines > 200:
            return CheckResult("change_size", True, 0.7, f"Large change ({total_lines} lines)")
        else:
            return CheckResult("change_size", True, 1.0, f"Good change size ({total_lines} lines)")

    def _check_commit_message(self, c: Contribution) -> CheckResult:
        """Commit message follows conventional format."""
        msg = c.commit_message
        if not msg:
            return CheckResult("commit_message", False, 0.0, "Empty commit message")

        # Check conventional commit format: type: description
        conventional = re.match(r"^(feat|fix|docs|refactor|perf|test|chore)\(?.*\)?: .+", msg)
        if conventional:
            return CheckResult("commit_message", True, 1.0, "Follows conventional commits")

        if len(msg) > 10:
            return CheckResult("commit_message", True, 0.7, "Descriptive but not conventional")

        return CheckResult("commit_message", False, 0.3, "Poor commit message")

    def _check_description(self, c: Contribution) -> CheckResult:
        """PR description is meaningful."""
        desc = c.description
        if not desc:
            return CheckResult("description", False, 0.0, "Empty description")
        if len(desc) < 20:
            return CheckResult("description", False, 0.3, "Description too short")
        return CheckResult("description", True, 1.0, "Good description")

    def _check_no_debug_code(self, c: Contribution) -> CheckResult:
        """No debug statements in generated code."""
        debug_patterns = [
            r"\bprint\s*\(",
            r"\bconsole\.log\s*\(",
            r"\bdebugger\b",
            r"\bpdb\.set_trace\(",
            r"\bbreakpoint\(\)",
            r"#\s*TODO\b",
            r"#\s*FIXME\b",
            r"#\s*HACK\b",
        ]

        issues = []
        for change in c.changes:
            for pattern in debug_patterns:
                if re.search(pattern, change.new_content):
                    issues.append(f"{change.path}: {pattern}")

        if not issues:
            return CheckResult("no_debug_code", True, 1.0, "No debug code found")

        # Allow some patterns (TODO can be intentional)
        severity = 0.8 if len(issues) <= 2 else 0.4
        return CheckResult(
            "no_debug_code",
            severity >= 0.6,
            severity,
            f"Found {len(issues)} debug patterns",
        )

    def _check_no_placeholders(self, c: Contribution) -> CheckResult:
        """No placeholder text in generated code."""
        placeholder_patterns = [
            r"YOUR_.*_HERE",
            r"REPLACE_THIS",
            r"PLACEHOLDER",
            r"XXX",
            r"lorem ipsum",
            r"example\.com",
            r"foo\s*bar",
        ]

        for change in c.changes:
            content_lower = change.new_content.lower()
            for pattern in placeholder_patterns:
                if re.search(pattern, content_lower, re.IGNORECASE):
                    return CheckResult(
                        "no_placeholders",
                        False,
                        0.2,
                        f"Found placeholder: {pattern} in {change.path}",
                    )

        return CheckResult("no_placeholders", True, 1.0, "No placeholders found")

    def _check_file_coherence(self, c: Contribution) -> CheckResult:
        """Changes are related to the finding."""
        if not c.changes:
            return CheckResult("file_coherence", False, 0.0, "No changes")

        # Check that the finding's file is actually changed
        finding_file = c.finding.file_path
        changed_files = {ch.path for ch in c.changes}

        if finding_file in changed_files:
            return CheckResult("file_coherence", True, 1.0, "Finding file is changed")

        # Some contributions legitimately change different files
        if c.contribution_type in (ContributionType.README_FIX, ContributionType.FEATURE_ADD):
            return CheckResult("file_coherence", True, 0.8, "Different file but type allows it")

        return CheckResult(
            "file_coherence",
            False,
            0.4,
            f"Finding in {finding_file} but changes in {changed_files}",
        )


class QAHardcoreScorer:
    """Ruthless LLM-powered QA scorer for the Bounty Loop.

    Evaluates a generated patch against the originating VulnerabilityDossier.
    Only patches scoring >= 9.0 / 10.0 are approved. Failed patches generate
    strict critiques that are recorded in the Knowledge Base for the next
    DEV cycle.
    """

    MIN_APPROVAL_SCORE = 9.0

    def __init__(self, llm):
        self._llm = llm

    async def evaluate(
        self,
        dossier: "VulnerabilityDossier",
        contribution: "Contribution",
    ) -> "QAResult":
        """Score a patch against its originating vulnerability dossier.

        Returns a QAResult with score (0.0-10.0), critiques, and approval status.
        """
        import json as _json

        from farm_agent.core.models import QAResult

        # ── Build diff string from contribution ──────────────────────────
        diff_parts = []
        for change in contribution.changes:
            if change.original_content:
                import difflib

                diff = "".join(difflib.unified_diff(
                    change.original_content.splitlines(keepends=True),
                    change.new_content.splitlines(keepends=True),
                    fromfile=f"a/{change.path}",
                    tofile=f"b/{change.path}",
                    n=3,
                ))
                diff_parts.append(diff[:4000])
            else:
                diff_parts.append(
                    f"[NEW FILE] {change.path}\n{change.new_content[:4000]}"
                )
        diff_str = "\n\n".join(diff_parts) if diff_parts else "No diff available."

        # ── Build vulnerability context ──────────────────────────────────
        vuln_parts = []
        for v in dossier.vulnerabilities:
            vuln_parts.append(
                f"File: {v.file}\n"
                f"Line: {v.line}\n"
                f"Snippet: {v.snippet}\n"
                f"PoC: {v.poc}\n"
                f"Fix: {v.fix}\n"
                f"Impact: {v.impact}"
            )
        vuln_str = "\n---\n".join(vuln_parts)

        # ── System prompt: strict JSON enforcement ──────────────────────
        system_prompt = (
            "You are an elite, ruthless QA Security Engineer grading a patch "
            "against a vulnerability report. You grade strictly from 0.0 to 10.0.\n\n"
            "Weighted grading criteria:\n"
            "- Logic (30%): Does the fix correctly address the vulnerability?\n"
            "- Architecture (25%): Does the fix fit the codebase architecture?\n"
            "- Idioms (20%): Does the fix follow language/framework conventions?\n"
            "- Security (15%): Does the fix not introduce new security issues?\n"
            "- Scope/Tests (10%): Is the change minimal and focused?\n\n"
            "Return ONLY a JSON object with this exact schema:\n"
            '{"score": 8.5, "critiques": ["critique 1", "critique 2"], "approved": false}\n\n'
            "The 'approved' boolean MUST be true ONLY if the score is >= 9.0.\n"
            "Be ruthless. A score of 9.0+ means the patch is production-ready "
            "with zero issues. Most patches should score 5-8.\n\n"
            "DO NOT include any text before or after the JSON object. "
            "DO NOT wrap it in markdown fences. "
            "Return ONLY the raw JSON."
        )

        user_prompt = (
            f"## Repository: {dossier.repo_url}\n\n"
            f"## Vulnerability Report\n{vuln_str}\n\n"
            f"## Proposed Patch (Diff)\n{diff_str}\n\n"
            f"## Commit Message\n{contribution.commit_message}\n\n"
            f"Grade this patch. Return ONLY the JSON object."
        )

        try:
            response = await self._llm.complete(
                user_prompt, system=system_prompt, temperature=0.1,
            )
        except Exception as exc:
            logger.error("QA Hardcore LLM call failed: %s", exc)
            return QAResult(
                score=0.0,
                critiques=[f"System Error: QA Agent LLM call failed: {exc}"],
                approved=False,
            )

        # ── Parse JSON response ──────────────────────────────────────────
        text = response.strip()

        # Strip markdown fences if present
        import re as _re
        fence_match = _re.search(
            r"```(?:json)?\s*(.*?)```", text, _re.DOTALL | _re.IGNORECASE
        )
        if fence_match:
            text = fence_match.group(1).strip()

        # Find JSON object boundaries
        brace_start = text.find("{")
        brace_end = text.rfind("}")
        if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
            text = text[brace_start:brace_end + 1]

        try:
            parsed = _json.loads(text)
        except _json.JSONDecodeError:
            logger.warning("QA Hardcore: failed to parse LLM response as JSON")
            return QAResult(
                score=0.0,
                critiques=["System Error: QA Agent failed to return valid JSON."],
                approved=False,
            )

        if not isinstance(parsed, dict):
            logger.warning("QA Hardcore: LLM response is not a JSON object")
            return QAResult(
                score=0.0,
                critiques=["System Error: QA Agent failed to return valid JSON."],
                approved=False,
            )

        score = float(parsed.get("score", 0.0))
        critiques = parsed.get("critiques", [])
        if not isinstance(critiques, list):
            critiques = [str(critiques)]

        # Always compute approved from score — never trust LLM's boolean
        approved = score >= self.MIN_APPROVAL_SCORE

        logger.info("QA Hardcore Score: %.1f/10.0 — Approved: %s", score, approved)
        if not approved:
            for c in critiques[:5]:
                logger.info("  Critique: %s", c[:200])

        return QAResult(
            score=score,
            critiques=[str(c) for c in critiques],
            approved=approved,
        )
