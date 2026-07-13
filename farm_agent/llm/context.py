"""Context management for LLM calls.

Handles token estimation, context window chunking, and
building effective prompts from repository content.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from farm_agent.core.models import FileNode, RepoContext

logger = logging.getLogger(__name__)

# Rough token estimates (chars per token varies by model/language)
CHARS_PER_TOKEN = 4


@dataclass
class ContextBudget:
    """Tracks token budget for context window."""

    max_tokens: int
    used_tokens: int = 0
    sections: dict[str, int] = field(default_factory=dict)

    @property
    def remaining(self) -> int:
        return max(0, self.max_tokens - self.used_tokens)

    def can_fit(self, text: str) -> bool:
        return estimate_tokens(text) <= self.remaining

    def add(self, section_name: str, text: str) -> bool:
        tokens = estimate_tokens(text)
        if tokens > self.remaining:
            return False
        self.used_tokens += tokens
        self.sections[section_name] = tokens
        return True


def estimate_tokens(text: str) -> int:
    """Rough token estimate based on character count."""
    return len(text) // CHARS_PER_TOKEN


def truncate_to_tokens(text: str, max_tokens: int) -> str:
    """Truncate text to fit within token budget."""
    max_chars = max_tokens * CHARS_PER_TOKEN
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n... [truncated]"


def extract_style_guide(prs_data: list[dict]) -> str:
    """Build a concise style-guide block from recently merged PRs.

    Analyses PR titles and bodies to detect patterns like emoji usage,
    conventional-commit prefixes, verb tense, bullet-point structure,
    and issue-reference conventions.

    Returns ``""`` when *prs_data* is empty so callers can skip
    injection without branching.
    """
    if not prs_data:
        return ""

    titles = [pr.get("title", "") for pr in prs_data]
    bodies = [pr.get("body", "") for pr in prs_data]

    observations: list[str] = []

    # ── Title patterns ────────────────────────────────────────────────
    emoji_re = re.compile(
        r"[\U0001F300-\U0001F9FF\U00002600-\U000027BF\U0000FE00-\U0000FE0F"
        r"\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF]"
    )
    emoji_count = sum(1 for t in titles if emoji_re.search(t))
    if emoji_count > len(titles) / 2:
        observations.append("PR titles frequently use emoji prefixes")
    elif emoji_count == 0:
        observations.append("PR titles do NOT use emojis")

    # Conventional-commit style  (feat:, fix:, docs: …)
    cc_re = re.compile(
        r"^(feat|fix|docs|chore|refactor|perf|test|ci|style|build)(\(.*?\))?!?:\s",
        re.I,
    )
    cc_count = sum(1 for t in titles if cc_re.match(t))
    if cc_count > len(titles) / 2:
        observations.append("PR titles follow Conventional Commits (e.g. feat:, fix:)")

    # Verb tense — check first word
    imperative_verbs = {
        "add",
        "fix",
        "update",
        "remove",
        "change",
        "improve",
        "refactor",
        "bump",
        "move",
        "use",
    }
    past_verbs = {
        "added",
        "fixed",
        "updated",
        "removed",
        "changed",
        "improved",
        "refactored",
        "bumped",
        "moved",
        "used",
    }
    first_words = [re.sub(r"^[^a-zA-Z]+", "", t).split()[0].lower() for t in titles if t.strip()]
    imp = sum(1 for w in first_words if w in imperative_verbs)
    past = sum(1 for w in first_words if w in past_verbs)
    if imp > past and imp > 0:
        observations.append("PR titles use imperative mood (e.g. 'Add feature')")
    elif past > imp and past > 0:
        observations.append("PR titles use past tense (e.g. 'Added feature')")

    # ── Body patterns ─────────────────────────────────────────────────
    non_empty_bodies = [b for b in bodies if b.strip()]
    if non_empty_bodies:
        bullet_count = sum(1 for b in non_empty_bodies if re.search(r"^\s*[-*]\s", b, re.M))
        if bullet_count > len(non_empty_bodies) / 2:
            observations.append("PR descriptions use bullet-point lists")

        issue_ref_count = sum(1 for b in non_empty_bodies if re.search(r"#\d+", b))
        if issue_ref_count > len(non_empty_bodies) / 2:
            observations.append("PR descriptions reference issues with #NNN")

        header_count = sum(1 for b in non_empty_bodies if re.search(r"^##?\s", b, re.M))
        if header_count > len(non_empty_bodies) / 2:
            observations.append("PR descriptions use markdown section headers")
    else:
        observations.append("PR descriptions are typically empty or minimal")

    if not observations:
        return ""

    # Example titles for the LLM to mimic
    example_section = "\n".join(f'  - "{t}"' for t in titles[:3])

    guide = (
        f"OBSERVED REPO STYLE (from {len(prs_data)} recent merged PRs):\n"
        + "\n".join(f"- {obs}" for obs in observations)
        + f"\n\nExample PR titles:\n{example_section}"
    )
    return guide


def build_repo_context_prompt(
    context: RepoContext,
    max_tokens: int = 6000,
    *,
    style_guide: str = "",
) -> str:
    """Build a compact prompt summarizing the repository context.

    Prioritizes: README > file tree > contributing guide > relevant files.
    """
    budget = ContextBudget(max_tokens=max_tokens)
    parts: list[str] = []

    # 1. Repo metadata (always included)
    meta = (
        f"## Repository: {context.repo.full_name}\n"
        f"- Language: {context.repo.language}\n"
        f"- Stars: {context.repo.stars}\n"
        f"- Description: {context.repo.description or 'N/A'}\n"
    )
    budget.add("metadata", meta)
    parts.append(meta)

    # 2. README (high priority)
    if context.readme_content:
        readme = truncate_to_tokens(context.readme_content, min(2000, budget.remaining))
        if budget.add("readme", readme):
            parts.append(f"## README\n{readme}")

    # 3. File tree (medium priority)
    if context.file_tree:
        tree_text = format_file_tree(context.file_tree)
        tree_text = truncate_to_tokens(tree_text, min(1000, budget.remaining))
        if budget.add("file_tree", tree_text):
            parts.append(f"## File Structure\n```\n{tree_text}\n```")

    # 4. Contributing guide
    if context.contributing_guide:
        guide = truncate_to_tokens(context.contributing_guide, min(800, budget.remaining))
        if budget.add("contributing", guide):
            parts.append(f"## Contributing Guide\n{guide}")

    # 5. Style guide from merged PRs
    if style_guide:
        sg = truncate_to_tokens(style_guide, min(600, budget.remaining))
        if budget.add("style_guide", sg):
            parts.append(f"## Observed PR Style\n{sg}")

    # 6. Relevant source files
    if context.relevant_files:
        parts.append("## Relevant Source Files")
        for path, content in context.relevant_files.items():
            truncated = truncate_to_tokens(content, min(500, budget.remaining))
            if budget.add(f"file:{path}", truncated):
                parts.append(f"### {path}\n```\n{truncated}\n```")
            else:
                break

    # 7. Coding style
    if context.coding_style and budget.can_fit(context.coding_style):
        budget.add("style", context.coding_style)
        parts.append(f"## Coding Conventions\n{context.coding_style}")

    logger.debug(
        "Context built: %d tokens across %d sections",
        budget.used_tokens,
        len(budget.sections),
    )
    return "\n\n".join(parts)


def format_file_tree(nodes: list[FileNode], max_depth: int = 3) -> str:
    """Format file tree nodes into a readable string."""
    lines: list[str] = []
    for node in sorted(nodes, key=lambda n: n.path):
        depth = node.path.count("/")
        if depth > max_depth:
            continue
        prefix = "📁 " if node.type == "tree" else "📄 "
        indent = "  " * depth
        lines.append(f"{indent}{prefix}{node.path.split('/')[-1]}")
    return "\n".join(lines[:100])  # cap output size


def build_generator_system_prompt(
    context: RepoContext,
    *,
    style_guide: str = "",
    project_map: str = "",
    max_tokens: int = 6000,
) -> str:
    """Build an architecturally-aware system prompt for the Generator.

    Injects the Project Map (skeleton) with strict rules that force the
    LLM to cross-reference existing classes, methods, and utilities
    before generating code — eliminating hallucinated dependencies.

    The map data is placed BEFORE the rules so the LLM ingests the
    structure, then immediately reads the constraints.

    Args:
        context: Repository context with file tree and code.
        style_guide: Optional style guide from merged PRs.
        project_map: Skeleton map string from ``RepoMapper``.
        max_tokens: Token budget for the repo context section.
    """
    repo_context = build_repo_context_prompt(
        context,
        max_tokens=max_tokens,
        style_guide=style_guide,
    )

    # ── Style sections (existing behaviour) ──────────────────────────
    style_section = ""
    if style_guide:
        style_section += (
            "\n\nOBSERVED REPO PR STYLE (from recently merged PRs):\n"
            f"{style_guide}\n\n"
            "You MUST mimic this observed repository style in your PR titles, "
            "commit messages, and descriptions. Your contributions should be "
            "indistinguishable from those of the existing contributors.\n"
        )
    if context.coding_style:
        style_section += (
            "\n\nCODEBASE STYLE (learned from this repository):\n"
            f"{context.coding_style}\n\n"
            "You MUST match these conventions exactly. Do not introduce "
            "your own style preferences. Your changes should look like "
            "they were written by the same developer who wrote the rest "
            "of the codebase.\n"
        )

    # ── Project Map + Architectural Awareness rules ──────────────────
    map_section = ""
    if project_map:
        # Cap the map to protect the context window
        truncated = project_map[:60000]
        truncation_notice = ""
        if len(project_map) > 60000:
            truncation_notice = (
                "\nNote: The Project Map may be truncated. Rely on the provided context first.\n"
            )

        map_section = (
            "\n\nPROJECT SKELETON MAP:\n"
            "The following is a structural map of the repository listing "
            "file paths, classes, and function/method signatures. "
            "It contains NO implementation details — only the public API surface.\n"
            f"```\n{truncated}\n```\n"
            f"{truncation_notice}\n"
            "ARCHITECTURAL AWARENESS RULES (MANDATORY):\n"
            "RULE 1 — CROSS-REFERENCE: Before writing any code, check the map. "
            "Do not invent or hallucinate utility functions, classes, or helpers. "
            "If you need a helper function (e.g., for string formatting, DB access, "
            "date parsing), look for it in the map first. Use what already exists.\n\n"
            "RULE 2 — SIGNATURE MATCHING: If you call an external class or method "
            "listed in the map, your generated code MUST match its exact signature "
            "(arguments, argument names, and types). Do not guess parameter names "
            "or add parameters that do not exist in the map.\n\n"
            "RULE 3 — MISSING CONTEXT: If the map indicates a file is crucial but "
            "you cannot see its full body, explicitly state your assumption in a "
            "code comment. Do not silently invent implementation details for "
            "functions you can only see the signature of.\n\n"
            "RULE 4 — STRICT NO-PLACEHOLDER POLICY: You are FORBIDDEN from using `// ...`, "
            "`TODO`, or any comments implying 'code remains the same'. You MUST output "
            "the ENTIRE function or block you are modifying.\n"
        )

    return (
        "You are a human Senior Staff Engineer at a top-tier technology firm. You are a "
        "prolific open-source contributor known for surgical precision, deep "
        "architectural awareness, and matching repository conventions perfectly. "
        "Maintainers trust you because your PRs are minimal, focused, and "
        "production-ready. You write code that looks like it was already there.\n\n"
        "CRITICAL RULE - NO GUESSWORK: You are strictly forbidden from hallucinating, "
        "guessing, or making 'If-Driven' assumptions. "
        "EVERY code element you produce MUST be verifiable in the provided context. "
        "FAIL-CLOSED POLICY: If you cannot verify a variable, function, or API exists "
        "in the provided context, you MUST NOT use it. Lack of evidence equals FALSE.\n\n"
        "RULES FOR GENERATING CHANGES:\n"
        "1. Match existing code style EXACTLY (indentation, naming, patterns). "
        "If the repo uses 2 spaces, you use 2 spaces. If it uses tabs, you use tabs.\n"
        "2. Make the SMALLEST change that correctly fixes the issue. No busywork.\n"
        "3. Include proper error handling consistent with the codebase.\n"
        "4. Do NOT break existing functionality or change unrelated logic.\n"
        "5. Do NOT add unnecessary dependencies, imports, or boilerplate.\n"
        "6. Do NOT refactor adjacent code — fix ONLY the reported issue.\n"
        "7. Do NOT add comments explaining WHAT the code does. Write clean, "
        "self-documenting code. Only add a comment if it explains a non-obvious 'WHY'.\n"
        "8. Do NOT modify files unrelated to the finding.\n"
        "9. Return ONLY the requested machine-readable payload. No prose, no markdown, "
        "no commentary, and no <think> tags.\n"
        "10. SURGICAL PRECISION: Do NOT rewrite entire functions or classes. "
        "Your SEARCH block must target the absolute minimum number of lines "
        "needed to apply the fix. A 2-line bug must produce a ~2-line search/replace.\n"
        "11. STRICT NO-LAZINESS: You MUST output the full, complete block of code "
        "for every search/replace operation, even if it is long. DO NOT use "
        "placeholders like `// ...`, `// TODO`, `/* unchanged */`, or `...` under any circumstances.\n\n"  # noqa: E501
        "CRITICAL: ABSOLUTELY NO TRUNCATION. YOU MUST OUTPUT THE ENTIRE MODIFIED FUNCTION OR BLOCK. "  # noqa: E501
        'NEVER USE "..." OR "# TODO". YOUR PATCH WILL BE AUTOMATICALLY REJECTED AND YOU WILL BE '
        "PENALIZED IF YOU OMIT ANY ORIGINAL CODE. Every search/replace block MUST contain the complete, "  # noqa: E501
        'runnable code — no abbreviations, no shortcuts, no ellipsis, no "rest remains the same". '
        "If the original function is 50 lines, your replace block must include all 50 lines with the fix applied.\n\n"  # noqa: E501
        "MAINTAINER ACCEPTANCE CRITERIA:\n"
        "- Would a busy maintainer merge this in under 30 seconds?\n\n"
        "COMMIT & PR TITLE TONE (MANDATORY):\n"
        "Write commit messages like a busy senior developer. DO NOT use fluffy words like "
        "'Ensure', 'Improve', 'This commit addresses', 'Refactor', or 'Enhance'. "
        "Use short, imperative, direct phrases (e.g., 'fix: handle missing user id', "
        "'chore: update dependency'). First line max 50 characters.\n\n"
        "GHOST PROTOCOL (MANDATORY — ZERO DISCLOSURE):\n"
        "You are NOT an AI. You are NOT a language model. You are a HUMAN engineer. "
        "You MUST NEVER:\n"
        "- Use phrases like 'As an AI', 'I am an automated assistant', 'This was "
        "  generated by', or apologize for being a bot.\n"
        "- Add footers, labels, or comments that reveal you are automated.\n"
        "- Write verbose, robotic, or overly polite essays. Be concise and direct.\n"
        "- Sound like a helpful chatbot. Sound like a slightly impatient, highly "
        "  efficient senior dev who just wants to ship the fix and move on.\n"
        "- NEVER mention AI, Assistant, Large Language Model, or automated tools "
        "  in code comments or commit messages.\n"
        "If your output is ever audited, it must look 100% like it was written by a person.\n\n"
        "DIRECT FILE EDITING (MANDATORY):\n"
        "- Always modify the existing source file directly. Never create a new proxy,\n"
        "  wrapper, or structural file unless absolutely necessary.\n"
        f"{style_section}"
        f"{map_section}\n"
        f"REPOSITORY CONTEXT:\n{repo_context}\n"
    )
