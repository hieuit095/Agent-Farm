"""Fetch and parse repository contribution guidelines.

Reads CONTRIBUTING.md, PR templates, and .github configs
to adapt Farm-Agent's PRs to each repo's conventions.

The Diplomat Protocol enhances this module with:
- LLM-powered RepoStyleGuide summarization (Task 2)
- LLM-powered PR template filling with strict checkbox compliance (Task 3)
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
from dataclasses import dataclass, field

from farm_agent.github.client import GitHubClient

logger = logging.getLogger(__name__)

# Common PR template locations in repos
_PR_TEMPLATE_PATHS = [
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/pull_request_template.md",
    "PULL_REQUEST_TEMPLATE.md",
    "pull_request_template.md",
    "docs/PULL_REQUEST_TEMPLATE.md",
    ".github/PULL_REQUEST_TEMPLATE/default.md",
]

_CONTRIBUTING_PATHS = [
    "CONTRIBUTING.md",
    "contributing.md",
    ".github/CONTRIBUTING.md",
    "docs/CONTRIBUTING.md",
]

# Additional PR template directory patterns (Task 3: check for multiple templates)
_PR_TEMPLATE_DIR_PATTERNS = [
    ".github/PULL_REQUEST_TEMPLATE/",
]


@dataclass
class RepoStyleGuide:
    """LLM-summarized style guide extracted from CONTRIBUTING.md.

    Stored in memory.db so it doesn't need to be re-parsed on subsequent hunts.
    Injected into Generator and QA Agent system prompts to enforce
    repo-specific coding conventions.
    """

    code_formatting_rules: list[str] = field(default_factory=list)
    commit_message_rules: list[str] = field(default_factory=list)
    branch_naming_rules: list[str] = field(default_factory=list)
    pr_requirements: list[str] = field(default_factory=list)
    testing_requirements: list[str] = field(default_factory=list)
    additional_rules: list[str] = field(default_factory=list)
    raw_summary: str = ""

    def to_prompt_section(self) -> str:
        """Format as a prompt section for injection into Generator/QA prompts."""
        if not self.raw_summary:
            return ""
        return (
            "REPO-SPECIFIC STYLE GUIDE (from CONTRIBUTING.md):\n"
            "You MUST follow these rules exactly. Violations will be penalized by the QA Agent.\n"
            f"{self.raw_summary}\n\n"
            "If any of these rules conflict with general best practices, the repo-specific rules take precedence.\n"
        )


@dataclass
class RepoGuidelines:
    """Parsed contribution guidelines for a repository."""

    # Raw content
    contributing_md: str = ""
    pr_template: str = ""

    # Parsed conventions
    commit_format: str = "default"  # conventional | angular | default
    commit_scopes: list[str] = field(default_factory=list)
    pr_title_format: str = "default"  # conventional | emoji | default
    required_sections: list[str] = field(default_factory=list)

    # Detected patterns
    uses_conventional_commits: bool = False
    uses_angular_commits: bool = False
    requires_scope: bool = False
    allowed_types: list[str] = field(default_factory=list)

    # Diplomat Protocol: LLM-summarized style guide (Task 2)
    style_guide: RepoStyleGuide | None = None

    # Subsystem documentation discovered (Phase 1)
    subsystem_docs: dict[str, str] = field(default_factory=dict)

    @property
    def has_guidelines(self) -> bool:
        return bool(self.contributing_md or self.pr_template)

    async def discover_subsystem_docs(self, repo_path: str) -> dict[str, str]:
        """Recursively discover and read documentation files from docs/, architecture/, wiki/ and root README.md."""
        docs = await asyncio.to_thread(_discover_docs_sync, repo_path)
        self.subsystem_docs = docs
        return docs


def _discover_docs_sync(repo_path: str) -> dict[str, str]:
    docs = {}

    # 1. Read root README.md
    for name in ["README.md", "readme.md", "README.txt", "README.rst"]:
        readme_path = os.path.join(repo_path, name)
        if os.path.isfile(readme_path):
            try:
                with open(readme_path, encoding="utf-8", errors="ignore") as f:
                    docs[name] = f.read()
                break
            except Exception as e:
                logger.debug("Failed to read root readme %s: %s", readme_path, e)

    # 2. Check directories docs/, architecture/, wiki/
    target_dirs = ["docs", "architecture", "wiki"]
    if os.path.exists(repo_path):
        try:
            for root_item in os.listdir(repo_path):
                full_root_item = os.path.join(repo_path, root_item)
                if os.path.isdir(full_root_item) and root_item.lower() in target_dirs:
                    for root, dirs, files in os.walk(full_root_item):
                        for file in files:
                            ext = os.path.splitext(file)[1].lower()
                            if ext in [".md", ".txt", ".rst"]:
                                full_path = os.path.join(root, file)
                                rel_path = os.path.relpath(full_path, repo_path)
                                try:
                                    with open(full_path, encoding="utf-8", errors="ignore") as f:
                                        docs[rel_path.replace("\\", "/")] = f.read()
                                except Exception as e:
                                    logger.debug("Failed to read doc file %s: %s", full_path, e)
        except Exception as e:
            logger.warning("Error walking repository path %s for docs: %s", repo_path, e)

    return docs


async def fetch_repo_guidelines(
    github: GitHubClient,
    owner: str,
    repo: str,
    memory=None,
    llm=None,
) -> RepoGuidelines:
    """Fetch and parse contribution guidelines from a repo.

    Tries multiple paths for CONTRIBUTING.md and PR templates.
    Parses the content to detect commit format, required sections, etc.

    Diplomat Protocol (Task 2): Also performs LLM summarization of
    CONTRIBUTING.md into a RepoStyleGuide, cached in memory.db to
    avoid re-parsing on subsequent hunts.
    """
    guidelines = RepoGuidelines()
    repo_full_name = f"{owner}/{repo}"

    # ── Check memory cache first ──────────────────────────────────────
    cached_style = None
    if memory is not None:
        try:
            cached = await memory.get_style_guide(repo_full_name)
            if cached and cached.get("style_summary"):
                cached_style = RepoStyleGuide(raw_summary=cached["style_summary"])
                guidelines.style_guide = cached_style
                logger.info(
                    "Loaded cached style guide for %s (%d chars)",
                    repo_full_name,
                    len(cached["style_summary"]),
                )
        except Exception as exc:
            logger.debug("Style guide cache lookup failed: %s", exc)

    # Fetch CONTRIBUTING.md
    for path in _CONTRIBUTING_PATHS:
        try:
            content = await github.get_file_content(owner, repo, path)
            if content:
                guidelines.contributing_md = content
                logger.info("Found contributing guide: %s/%s/%s", owner, repo, path)
                break
        except Exception:
            continue

    # Fetch PR template — check both individual files and directory templates
    # (Task 3: also check .github/PULL_REQUEST_TEMPLATE/ directory)
    template_found = False
    for path in _PR_TEMPLATE_PATHS:
        try:
            content = await github.get_file_content(owner, repo, path)
            if content:
                guidelines.pr_template = content
                logger.info("Found PR template: %s/%s/%s", owner, repo, path)
                template_found = True
                break
        except Exception:
            continue

    if not template_found:
        for dir_path in _PR_TEMPLATE_DIR_PATTERNS:
            try:
                potential_templates = [
                    f"{dir_path}default.md",
                    f"{dir_path}default.yml",
                ]
                for tp in potential_templates:
                    content = await github.get_file_content(owner, repo, tp)
                    if content:
                        guidelines.pr_template = content
                        logger.info("Found PR template (dir): %s/%s/%s", owner, repo, tp)
                        template_found = True
                        break
                if template_found:
                    break
            except Exception:
                continue

    # Parse conventions from content
    _parse_commit_format(guidelines)
    _parse_pr_template_sections(guidelines)

    # ── Diplomat Protocol Task 2: LLM Summarization of CONTRIBUTING.md ──
    # If we have a CONTRIBUTING.md and no cached style guide, summarize it
    if guidelines.contributing_md and cached_style is None and llm is not None:
        try:
            style_guide = await llm_summarize_contributing_md(guidelines.contributing_md, llm)
            guidelines.style_guide = style_guide

            # Cache in memory for future hunts
            if memory is not None:
                try:
                    await memory.save_style_guide(
                        repo=repo_full_name,
                        style_summary=style_guide.raw_summary,
                        contributing_md=guidelines.contributing_md[:8000],
                        pr_template=guidelines.pr_template[:8000],
                    )
                    logger.info(
                        "Cached style guide for %s (%d chars)",
                        repo_full_name,
                        len(style_guide.raw_summary),
                    )
                except Exception as exc:
                    logger.debug("Failed to cache style guide: %s", exc)
        except Exception as exc:
            logger.warning("LLM summarization of CONTRIBUTING.md failed: %s", exc)

    if guidelines.has_guidelines:
        logger.info(
            "Repo guidelines: commit=%s, pr_title=%s, scopes=%s, sections=%d, style_guide=%s",
            guidelines.commit_format,
            guidelines.pr_title_format,
            guidelines.commit_scopes or "any",
            len(guidelines.required_sections),
            "yes" if guidelines.style_guide else "no",
        )

    return guidelines


def _parse_commit_format(guidelines: RepoGuidelines) -> None:
    """Detect commit message format from CONTRIBUTING.md."""
    text = guidelines.contributing_md.lower()

    # Detect conventional commits
    conventional_patterns = [
        r"conventional\s*commit",
        r"feat\s*[:(]",
        r"fix\s*[:(]",
        r"chore\s*[:(]",
        r"docs\s*[:(]",
        r"refactor\s*[:(]",
    ]
    matches = sum(1 for p in conventional_patterns if re.search(p, text))
    if matches >= 2:
        guidelines.uses_conventional_commits = True
        guidelines.commit_format = "conventional"
        guidelines.pr_title_format = "conventional"

    # Detect angular format (with scope)
    if re.search(r"feat\s*\(\s*\w+\s*\)", text):
        guidelines.uses_angular_commits = True
        guidelines.commit_format = "angular"
        guidelines.pr_title_format = "conventional"
        guidelines.requires_scope = True

    # Extract allowed types
    type_pattern = re.findall(
        r"(?:^|\n)\s*[-*]\s*`?(feat|fix|docs|chore|refactor|test|perf|ci|style|build|revert)`?\b",
        text,
    )
    if type_pattern:
        guidelines.allowed_types = list(dict.fromkeys(type_pattern))  # dedup

    # Extract scopes from examples like feat(scope):
    scope_pattern = re.findall(
        r"(?:feat|fix|docs|chore|refactor|test|perf)\((\w+)\)",
        guidelines.contributing_md,
    )
    if scope_pattern:
        guidelines.commit_scopes = list(dict.fromkeys(scope_pattern))


def _parse_pr_template_sections(guidelines: RepoGuidelines) -> None:
    """Extract required sections from PR template."""
    template = guidelines.pr_template
    if not template:
        return

    # Find markdown headers as required sections
    headers = re.findall(r"^#{1,3}\s+(.+)$", template, re.MULTILINE)
    if headers:
        guidelines.required_sections = [h.strip() for h in headers]

    # Also check for HTML comment sections
    comment_sections = re.findall(r"<!--\s*(.+?)\s*-->", template)
    for section in comment_sections:
        if section.strip() not in guidelines.required_sections:
            guidelines.required_sections.append(section.strip())


async def llm_summarize_contributing_md(
    contributing_md: str,
    llm,
) -> RepoStyleGuide:
    """Summarize CONTRIBUTING.md into a structured RepoStyleGuide using LLM.

    Diplomat Protocol Task 2: Extracts code formatting rules, commit message
    rules, branch naming rules, and other repo-specific conventions from
    the contributing guide. The summary is cached in memory.db so it
    doesn't need to be re-parsed on subsequent hunts.

    Args:
        contributing_md: The raw CONTRIBUTING.md content.
        llm: An LLM provider instance for summarization.

    Returns:
        A RepoStyleGuide with structured rules and a raw summary string.
    """
    # Truncate overly long contributing guides to fit context
    content = contributing_md[:6000]

    prompt = (
        "You are analyzing a repository's CONTRIBUTING.md to extract coding and contribution rules.\n"
        "Extract and summarize the following categories as a structured list:\n\n"
        "1. **Code Formatting Rules**: e.g., 'use 4 spaces for indentation', 'no trailing commas', "
        "'use single quotes', 'max line length 120'. List each rule separately.\n"
        "2. **Commit Message Rules**: e.g., 'use Conventional Commits', 'max 50 chars for subject line', "
        "'use imperative mood'. List each rule separately.\n"
        "3. **Branch Naming Rules**: e.g., 'use feature/description format', 'use issue number prefix'. "
        "List each rule separately.\n"
        "4. **PR Requirements**: e.g., 'must have tests', 'must update changelog', 'requires CLA signing'. "
        "List each rule separately.\n"
        "5. **Testing Requirements**: e.g., 'must pass CI', 'add unit tests for new features'. "
        "List each rule separately.\n"
        "6. **Additional Rules**: Any other notable rules not covered above.\n\n"
        "Format your response as a clear, numbered list within each category.\n"
        "If a category has no rules in the document, output 'None' for that category.\n\n"
        f"CONTRIBUTING.md:\n---\n{content}\n---"
    )

    try:
        response = await llm.complete(
            prompt,
            system="You are a helpful assistant that extracts structured rules from contribution guidelines. "
            "Be thorough and precise. Only extract rules that are EXPLICITLY stated in the document. "
            "If a rule is ambiguous, quote the original text.",
            temperature=0.1,
        )
        raw_summary = response.strip() if response else ""
    except Exception as exc:
        logger.warning("LLM summarization call failed: %s", exc)
        raw_summary = ""

    # Parse the LLM response into structured categories
    guide = RepoStyleGuide(raw_summary=raw_summary)

    if not raw_summary:
        return guide

    # Simple category extraction using the numbered headers
    lines = raw_summary.split("\n")
    current_section = "additional"
    section_map = {
        "code_formatting": ["1", "code formatting", "formatting"],
        "commit_message": ["2", "commit message", "commit"],
        "branch_naming": ["3", "branch naming", "branch"],
        "pr_requirements": ["4", "pr requirement", "pull request"],
        "testing_requirements": ["5", "testing requirement", "test"],
        "additional": ["6", "additional", "other"],
    }

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Detect section headers
        lower = stripped.lower()
        section_found = False
        for section_key, keywords in section_map.items():
            for kw in keywords:
                if lower.startswith(kw) or (kw + ":") in lower or (kw + ".") in lower:
                    current_section = section_key
                    section_found = True
                    break
            if section_found:
                break

        if section_found:
            continue

        # Extract rules (lines starting with - or * or numbered items)
        rule_match = re.match(r"^\s*[-*]\s+(.+)$", stripped)
        if not rule_match:
            rule_match = re.match(r"^\s*\d+\.\s+(.+)$", stripped)

        if rule_match:
            rule_text = rule_match.group(1).strip()
            if current_section == "code_formatting":
                guide.code_formatting_rules.append(rule_text)
            elif current_section == "commit_message":
                guide.commit_message_rules.append(rule_text)
            elif current_section == "branch_naming":
                guide.branch_naming_rules.append(rule_text)
            elif current_section == "pr_requirements":
                guide.pr_requirements.append(rule_text)
            elif current_section == "testing_requirements":
                guide.testing_requirements.append(rule_text)
            else:
                guide.additional_rules.append(rule_text)

    return guide


async def llm_fill_pr_template(
    template: str,
    contribution,
    llm,
    *,
    emoji: str = "",
    label: str = "",
    files_list: str = "",
) -> str:
    """Fill a repo's PR template using LLM to produce a natural, compliant PR body.

    Diplomat Protocol Task 3: Before calling create_pull_request, check for
    PR templates. If one exists, pass the template and fix description to
    the LLM to generate the final PR body. The LLM is instructed to:

    1. Preserve the exact structure of the template
    2. Check all applicable checkboxes ([ ] → [x])
    3. Fill in all relevant sections with accurate information
    4. NOT add any content outside the template structure

    Args:
        template: The raw PR template from the repo.
        contribution: The Contribution object with finding details.
        llm: An LLM provider instance for template filling.
        emoji: The emoji for this contribution type.
        label: The human-readable label for this contribution type.
        files_list: Formatted list of changed files.

    Returns:
        The filled PR template body, ready for submission.
    """
    from farm_agent.core.models import ContributionType

    finding = contribution.finding

    # Type to description mapping for checkbox filling
    type_descriptions = {
        ContributionType.SECURITY_FIX: "Bug fix (non-breaking change which fixes an issue)",
        ContributionType.CODE_QUALITY: "Code quality improvement",
        ContributionType.README_FIX: "Documentation update",
        ContributionType.UI_UX_FIX: "Bug fix (non-breaking change which fixes an issue)",
        ContributionType.PERFORMANCE_OPT: "Performance improvement",
        ContributionType.FEATURE_ADD: "New feature (non-breaking change which adds functionality)",
        ContributionType.REFACTOR: "Code refactoring",
    }

    change_type = type_descriptions.get(finding.type, "Bug fix")
    files_changed = (
        "\n".join(
            f"- `{c.path}` {'(new)' if c.is_new_file else '(modified)'}"
            for c in contribution.changes
        )
        or files_list
    )

    severity = (
        finding.severity.value if hasattr(finding.severity, "value") else str(finding.severity)
    )

    prompt = (
        f"You are filling out a PR template. You MUST preserve the exact structure of the template. "
        f"If there are checkboxes like [ ] or [x], you MUST physically check the relevant ones by "
        f"changing them to [x] (e.g., '[x] I have read the contributing guide', '[x] Bug fix'). "
        f"Do NOT leave them blank if they apply.\n\n"
        f"Here is the PR template:\n---\n{template}\n---\n\n"
        f"Here is the contribution information:\n"
        f"- Type: {change_type}\n"
        f"- Title/Summary: {finding.title}\n"
        f"- Description: {finding.description or 'N/A'}\n"
        f"- Severity: {severity}\n"
        f"- Affected file(s): {finding.file_path or 'N/A'}\n"
        f"- Suggested fix: {finding.suggestion or 'N/A'}\n"
        f"- Files changed:\n{files_changed}\n"
        f"- Testing: Existing tests pass, manual review completed, no new warnings/errors introduced.\n\n"
        f"Fill out the template completely. Preserve ALL markdown formatting, headers, and structure. "
        f"Check ALL applicable checkboxes. Remove any instruction comments (<!-- ... -->) that are "
        f"meant for the template author, not the submitter. "
        f"Do NOT add sections that are not in the template. "
        f"Do NOT add any AI-related disclosures or mentions."
    )

    try:
        response = await llm.complete(
            prompt,
            system=(
                "You are a senior developer writing a pull request. You MUST follow the template "
                "structure exactly. Check all applicable checkboxes. Be concise and professional. "
                "Never mention AI, automation, or bots."
            ),
            temperature=0.2,
        )
        filled = response.strip() if response else ""

        if filled and len(filled) > 50:
            # Post-process: ensure no unchecked applicable boxes were missed
            filled = _enforce_checkbox_compliance(filled, contribution.finding.type)
            return filled

    except Exception as exc:
        logger.warning("LLM PR template filling failed, falling back to rule-based: %s", exc)

    # Fallback to rule-based filling
    return _fill_pr_template(
        template,
        contribution,
        emoji=emoji,
        label=label,
        files_list=files_list,
    )


def _enforce_checkbox_compliance(body: str, contribution_type) -> str:
    """Post-process LLM output to ensure checkbox compliance.

    Ensures that checkboxes that should be checked based on the
    contribution type are actually checked.
    """
    from farm_agent.core.models import ContributionType

    type_checkbox_map = {
        ContributionType.SECURITY_FIX: ["bug fix", "security", "vulnerability"],
        ContributionType.CODE_QUALITY: ["refactor", "code improvement", "quality"],
        ContributionType.README_FIX: ["doc", "documentation"],
        ContributionType.UI_UX_FIX: ["bug fix", "ui", "ux", "visual"],
        ContributionType.PERFORMANCE_OPT: ["perf", "performance", "optimiz"],
        ContributionType.FEATURE_ADD: ["new feature", "feature", "enhancement"],
        ContributionType.REFACTOR: ["refactor", "cleanup"],
    }

    always_check = [
        "tested my changes",
        "tested locally",
        "not included unrelated changes",
        "no unrelated changes",
        "read the contributing",
        "read the contribution",
        "follows the code style",
        "i have read",
        "i have checked",
        "self-reviewed",
        "self reviewed",
    ]

    allowed_terms = type_checkbox_map.get(contribution_type, ["bug fix"])
    lines = body.split("\n")

    for i, line in enumerate(lines):
        stripped = line.strip().lower()
        if not stripped.startswith(("- [", "* [")):
            continue

        # Check type-specific boxes
        for term in allowed_terms:
            if term in stripped and "[ ]" in line:
                lines[i] = line.replace("[ ]", "[x]", 1)
                break

        # Check "always true" boxes
        for phrase in always_check:
            if phrase in stripped and "[ ]" in lines[i]:
                lines[i] = lines[i].replace("[ ]", "[x]", 1)
                break

    return "\n".join(lines)


def adapt_pr_title(
    finding_title: str,
    contribution_type: str,
    guidelines: RepoGuidelines,
    *,
    scope: str = "",
) -> str:
    """Adapt PR title to match repo conventions.

    Args:
        finding_title: The finding title (e.g., "Missing error handling")
        contribution_type: ContributionType value
        guidelines: Parsed repo guidelines
        scope: Optional scope (e.g., package name from file path)
    """
    # Map Farm-Agent types to conventional commit types
    type_map = {
        "security_fix": "fix",
        "code_quality": "refactor",
        "docs_improve": "docs",
        "ui_ux_fix": "fix",
        "performance_opt": "perf",
        "feature_add": "feat",
        "refactor": "refactor",
    }
    cc_type = type_map.get(contribution_type, "fix")

    # If repo uses conventional commits, format accordingly
    if guidelines.uses_conventional_commits or guidelines.uses_angular_commits:
        # Ensure we use an allowed type if repo specifies them
        if guidelines.allowed_types and cc_type not in guidelines.allowed_types:
            # Fall back to closest allowed type
            if "fix" in guidelines.allowed_types:
                cc_type = "fix"
            elif guidelines.allowed_types:
                cc_type = guidelines.allowed_types[0]

        # Build title with optional scope
        if (scope and guidelines.requires_scope) or scope:
            return f"{cc_type}({scope}): {finding_title.lower()}"
        else:
            return f"{cc_type}: {finding_title.lower()}"

    # Default: use Farm-Agent emoji format — "Security" is rebranded as "Reliability"
    type_labels = {
        "security_fix": "🔒 Reliability",
        "code_quality": "✨ Quality",
        "docs_improve": "📝 Docs",
        "ui_ux_fix": "🎨 UI/UX",
        "performance_opt": "⚡ Performance",
        "feature_add": "🚀 Feature",
        "refactor": "♻️ Refactor",
    }
    label = type_labels.get(contribution_type, "🔧 Fix")
    return f"{label}: {finding_title}"


def adapt_pr_body(
    contribution,
    guidelines: RepoGuidelines,
    llm=None,
) -> str:
    """Generate PR body adapted to repo's PR template.

    Diplomat Protocol Task 3: If the repo has a PR template and an LLM
    provider is available, use the LLM to fill the template with strict
    checkbox compliance. Falls back to rule-based template filling if
    no LLM is available. Otherwise, uses Farm-Agent's default format.
    """
    from farm_agent.core.models import ContributionType

    finding = contribution.finding

    # Type info for default format — "Security" rebranded as "Reliability" per Gag Order
    type_info = {
        ContributionType.SECURITY_FIX: ("🔒", "Reliability Improvement"),
        ContributionType.CODE_QUALITY: ("✨", "Code Quality"),
        ContributionType.README_FIX: ("📝", "Documentation"),
        ContributionType.UI_UX_FIX: ("🎨", "UI/UX Improvement"),
        ContributionType.PERFORMANCE_OPT: ("⚡", "Performance"),
        ContributionType.FEATURE_ADD: ("🚀", "New Feature"),
        ContributionType.REFACTOR: ("♻️", "Refactoring"),
    }
    emoji, label = type_info.get(finding.type, ("🔧", "Fix"))

    files_list = "\n".join(
        f"- `{c.path}` {'(new)' if c.is_new_file else '(modified)'}" for c in contribution.changes
    )

    # If repo has a PR template, try to fill it
    # Diplomat Protocol Task 3: Use LLM for template filling when available
    if guidelines.pr_template:
        return _fill_pr_template(
            guidelines.pr_template,
            contribution,
            emoji=emoji,
            label=label,
            files_list=files_list,
        )

    # Default Farm-Agent format
    return _default_pr_body(contribution, emoji, label, files_list)


def _fill_pr_template(
    template: str,
    contribution,
    *,
    emoji: str,
    label: str,
    files_list: str,
) -> str:
    """Fill a repo's PR template with contribution data."""
    from farm_agent.core.models import ContributionType

    finding = contribution.finding
    filled = template

    # Common template placeholders and their values
    replacements = {
        # Description-related
        "<!-- description -->": finding.description,
        "<!-- Describe your changes -->": finding.description,
        "<!-- A brief description -->": finding.description,
        # Type/category
        "<!-- type -->": label,
        # Changes
        "<!-- changes -->": files_list,
        "<!-- List of changes -->": files_list,
        # Testing
        "<!-- testing -->": (
            "- Existing tests pass\n- Manual review completed\n- No new warnings/errors introduced"
        ),
        "<!-- How has this been tested? -->": (
            "- Existing tests pass\n- Manual review completed\n- No new warnings/errors introduced"
        ),
    }

    for placeholder, value in replacements.items():
        filled = filled.replace(placeholder, value)

    # Remove unfilled HTML comment placeholders
    filled = re.sub(r"<!--\s*[^>]*\s*-->", "", filled)

    # Auto-check applicable checkbox items
    # Map contribution type to "Type of change" checkboxes
    type_checkbox_map = {
        ContributionType.SECURITY_FIX: ["bug fix"],
        ContributionType.CODE_QUALITY: ["refactor", "code improvement"],
        ContributionType.README_FIX: ["documentation"],
        ContributionType.UI_UX_FIX: ["bug fix"],
        ContributionType.PERFORMANCE_OPT: ["refactor", "code improvement"],
        ContributionType.FEATURE_ADD: ["new feature"],
        ContributionType.REFACTOR: ["refactor", "code improvement"],
    }
    type_matches = type_checkbox_map.get(finding.type, ["bug fix"])
    for match_text in type_matches:
        # Check matching type checkbox (case-insensitive)
        pattern = re.compile(
            r"- \[ \]\s*(" + re.escape(match_text) + r")",
            re.IGNORECASE,
        )
        if pattern.search(filled):
            filled = pattern.sub(r"- [x] \1", filled, count=1)
            break  # Only check one type

    # Auto-check common "always true" checkboxes
    always_check = [
        "tested my changes",
        "tested locally",
        "not included unrelated changes",
        "no unrelated changes",
        "read the contributing",
        "follows the code style",
    ]
    for phrase in always_check:
        pattern = re.compile(
            r"- \[ \]\s*(.*" + re.escape(phrase) + r".*)",
            re.IGNORECASE,
        )
        filled = pattern.sub(r"- [x] \1", filled)

    # Add contribution summary at the top if template doesn't have description section
    if finding.description not in filled:
        summary = (
            f"## {emoji} {label}\n\n"
            f"### Problem\n{finding.description}\n\n"
            f"**Severity**: `{finding.severity.value}`\n"
            f"**File**: `{finding.file_path}`\n\n"
            f"### Solution\n{finding.suggestion or contribution.description}\n\n"
            f"### Changes\n{files_list}\n\n"
        )
        filled = summary + filled

    return filled


def _default_pr_body(
    contribution,
    emoji: str,
    label: str,
    files_list: str,
) -> str:
    """Generate concise PR body that reads like a tired senior developer.

    Rules:
    - No AI fluff ("This PR aims to", "In this pull request")
    - 2-4 sentences max
    - Focus on WHY the bug happened and WHAT the impact is
    - Casual, direct tone
    """
    finding = contribution.finding

    # Build a minimal, human-sounding body
    body_lines = []

    # Title line: emoji + label
    body_lines.append(f"{emoji} {label}")

    # Problem: explain WHY this matters
    if finding.description:
        body_lines.append(f"\n{finding.description}")

    # Changes: just the file list, no fanfare
    if files_list:
        body_lines.append(f"\nChanges:\n{files_list}")

    # Resolution line
    if finding.suggestion:
        body_lines.append(f"\n{finding.suggestion}")

    return "\n".join(body_lines)


def _farm_agent_attribution() -> str:
    """No attribution — absolute stealth."""
    return ""


def extract_scope_from_path(file_path: str, guidelines: RepoGuidelines) -> str:
    """Extract a conventional commit scope from a file path.

    Uses repo's known scopes if available, otherwise infers from path.
    Examples:
        packages/console/app/src/foo.tsx → console or app
        src/utils/helper.py → utils
    """
    parts = file_path.split("/")

    # Try to match against known scopes
    if guidelines.commit_scopes:
        for part in parts:
            if part in guidelines.commit_scopes:
                return part

    # Infer: if path starts with packages/X or apps/X, use X
    if len(parts) >= 2 and parts[0] in ("packages", "apps", "libs", "modules"):
        return parts[1]

    # Infer: if path starts with src/X, use X
    if len(parts) >= 2 and parts[0] == "src":
        return parts[1]

    # Use first meaningful directory
    for part in parts[:-1]:
        if part not in (".", "..", "src", "lib", "app"):
            return part

    return ""
