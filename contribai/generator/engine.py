"""LLM-powered contribution generator.

Takes findings from the analysis engine and generates
actual code changes, tests, and commit messages that
follow the target repository's coding conventions.
"""

from __future__ import annotations

import difflib
import json
import logging
import re
from datetime import UTC, datetime

from contribai.analysis.mapper import RepoMapper
from contribai.core.config import ContributionConfig
from contribai.core.models import (
    Contribution,
    ContributionType,
    FileChange,
    Finding,
    RepoContext,
)
from contribai.llm.context import build_generator_system_prompt
from contribai.llm.provider import LLMProvider
from contribai.tools.protocol import READ_FILE_TOOL_SCHEMA, GitHubTool

logger = logging.getLogger(__name__)

# Maximum tool calls per generation session to prevent infinite loops
MAX_TOOL_CALLS = 3


class ContributionGenerator:
    """Generate code contributions from analysis findings."""

    def __init__(self, llm: LLMProvider, config: ContributionConfig, *, memory=None, pipeline_config=None):
        self._llm = llm
        self._config = config
        self._memory = memory  # Optional Memory for repo_preferences
        # Configurable patch retry limit (from PipelineConfig or default)
        self._max_patch_retries = getattr(pipeline_config, "max_patch_retries", 2) if pipeline_config else 2

    async def generate(
        self,
        finding: Finding,
        context: RepoContext,
        *,
        guidelines=None,
        github_client=None,
    ) -> Contribution | None:
        """Generate a contribution for a single finding.

        Steps:
        1. Build context-aware prompt
        2. Get LLM to generate the fix
        3. Parse structured output into FileChanges
        4. Generate commit message
        5. Self-review the generated code
        """
        import asyncio
        try:
            # 0: Fetch repo style from merged PRs (optional)
            async def _fetch_style() -> str:
                if github_client is None:
                    return ""
                try:
                    prs_data = await github_client.get_recent_merged_prs(
                        context.repo.owner, context.repo.name,
                    )
                    from contribai.llm.context import extract_style_guide
                    return extract_style_guide(prs_data)
                except Exception as exc:
                    logger.debug("Style mimicry skipped: %s", exc)
                    return ""

            # 0.5: Generate project skeleton map for architectural awareness
            async def _fetch_map() -> str:
                if github_client is None:
                    return ""
                try:
                    mapper = RepoMapper()
                    async def _fetch(path: str) -> str:
                        content = await github_client.get_file_content(
                            context.repo.owner, context.repo.name, path,
                        )
                        context.relevant_files[path] = content
                        return content
                    return await mapper.generate_map(context.file_tree, _fetch)
                except Exception as exc:
                    logger.debug("Project map generation skipped: %s", exc)
                    return ""

            # Concurrent fetching to overclock system pipeline
            style_task = asyncio.create_task(_fetch_style())
            map_task = asyncio.create_task(_fetch_map())
            prefs_task = asyncio.create_task(self._get_repo_preferences(context))

            style_guide, project_map, repo_prefs = await asyncio.gather(
                style_task, map_task, prefs_task
            )

            # 1 & 2: Generate the fix via agentic loop
            prompt = self._build_generation_prompt(finding, context, repo_prefs=repo_prefs)
            system = self._build_system_prompt(
                context, style_guide=style_guide, project_map=project_map,
            )

            response = await self._agentic_generate(
                prompt,
                system=system,
                github_client=github_client,
                context=context,
            )

            # 3: Parse output → apply search/replace to original content
            # Patch-Correction Retry Loop: if the patcher fails to apply
            # any edits (LLM hallucinated the SEARCH block), re-prompt the
            # LLM with the file content and ask for a corrected patch.
            MAX_PATCH_RETRIES = self._max_patch_retries
            changes = self._parse_changes(response, context)
            patch_attempt = 0
            while not changes and patch_attempt < MAX_PATCH_RETRIES:
                patch_attempt += 1
                logger.warning(
                    "Patch attempt %d/%d failed for %s — re-prompting LLM",
                    patch_attempt, MAX_PATCH_RETRIES, finding.title,
                )
                # Build a correction prompt with the actual file content
                file_content = context.relevant_files.get(finding.file_path, "")
                retry_prompt = (
                    "Your previous SEARCH block was NOT FOUND in the file. "
                    "This usually happens because of hallucinated lines, "
                    "incorrect indentation, or using `...` to skip lines.\n\n"
                    "Here is the ACTUAL file content you must match against:\n"
                    f"```\n{file_content[:6000]}\n```\n\n"
                    "Please review and provide the EXACT, VERBATIM block of code "
                    "you want to replace. Copy it character-for-character from the "
                    "file above. Do not use `...` to skip lines. Do not modify "
                    "indentation or whitespace.\n\n"
                    + prompt  # Re-include the original task prompt
                )
                response = await self._agentic_generate(
                    retry_prompt,
                    system=system,
                    github_client=github_client,
                    context=context,
                )
                changes = self._parse_changes(response, context)

            if not changes:
                logger.warning("No valid changes parsed for finding: %s", finding.title)
                return None


            # 4: Generate commit message
            commit_msg = await self._generate_commit_message(finding, changes, context)

            # 5: Generate branch name
            branch_name = self._generate_branch_name(finding)

            # Build the contribution
            contribution = Contribution(
                finding=finding,
                contribution_type=finding.type,
                title=self._generate_pr_title(finding, guidelines=guidelines),
                description=finding.description,
                changes=changes,
                commit_message=commit_msg,
                branch_name=branch_name,
                generated_at=datetime.now(UTC),
            )

            # 6: Self-review
            review_passed = await self._self_review(contribution, context)
            if not review_passed:
                logger.warning("Self-review failed for: %s", finding.title)
                return None

            logger.info(
                "Generated contribution: %s (%d files changed)",
                contribution.title,
                contribution.total_files_changed,
            )
            return contribution

        except Exception as e:
            logger.error("Failed to generate contribution for %s: %s", finding.title, e)
            return None

    async def _get_repo_preferences(self, context: RepoContext) -> dict | None:
        """Query memory for learned repo preferences.

        Returns dict with preferred_types, rejected_types, merge_rate
        or None if no memory or no data for this repo.
        """
        if not self._memory:
            return None
        try:
            return await self._memory.get_repo_preferences(context.repo.full_name)
        except Exception as e:
            logger.debug("Could not fetch repo preferences: %s", e)
            return None

    def _build_system_prompt(
        self,
        context: RepoContext,
        *,
        style_guide: str = "",
        project_map: str = "",
    ) -> str:
        """Build system prompt with repository context, style, and project map."""
        return build_generator_system_prompt(
            context,
            style_guide=style_guide,
            project_map=project_map,
            max_tokens=4000,
        )

    async def _agentic_generate(
        self,
        prompt: str,
        *,
        system: str,
        github_client=None,
        context: RepoContext | None = None,
    ) -> str:
        """Run the agentic generation loop with tool-calling support.

        If ``github_client`` is provided, the LLM can request file
        reads via the ``read_file`` tool.  The loop runs at most
        ``MAX_TOOL_CALLS`` tool invocations before forcing the LLM
        to generate the final code with whatever context it has.

        Falls back to a single ``self._llm.complete()`` call when
        no github_client is available (no tools).
        """
        if github_client is None:
            return await self._llm.complete(
                prompt, system=system, temperature=0.2,
            )

        # Build tool executor
        owner = context.repo.owner if context else ""
        repo_name = context.repo.name if context else ""
        tool = GitHubTool(github_client, owner=owner, repo=repo_name)

        # Prepare message history for the agentic loop
        messages: list[dict] = [
            {"role": "user", "content": prompt},
        ]
        tools = [READ_FILE_TOOL_SCHEMA]

        tool_calls_made = 0

        for _iteration in range(MAX_TOOL_CALLS + 1):
            response = await self._llm.complete_with_tools(
                messages,
                tools=tools if tool_calls_made < MAX_TOOL_CALLS else None,
                system=system,
                temperature=0.2,
            )

            # ── Text response → done ────────────────────────────────
            if not response.has_tool_calls:
                return response.text or ""

            # ── Tool call(s) → execute and loop ─────────────────────
            for tc in response.tool_calls:
                if tc.tool_name != "read_file":
                    logger.warning(
                        "Ignoring unknown tool call: %s", tc.tool_name,
                    )
                    continue

                filepath = tc.arguments.get("filepath", "")
                logger.info(
                    "🔧 Tool call: read_file('%s') [%d/%d]",
                    filepath, tool_calls_made + 1, MAX_TOOL_CALLS,
                )

                result = await tool.read_file(filepath)
                tool_calls_made += 1
                if result.success and filepath:
                    context.relevant_files[filepath] = str(result.data)

                # Append assistant's tool-call decision
                messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": f"call_{tool_calls_made}",
                        "type": "function",
                        "function": {
                            "name": "read_file",
                            "arguments": json.dumps(tc.arguments),
                        },
                    }],
                })

                # Append tool result
                content = result.data if result.success else result.error
                messages.append({
                    "role": "tool",
                    "tool_call_id": f"call_{tool_calls_made}",
                    "content": str(content),
                })

            # If we've hit the tool call limit, stop offering tools
            if tool_calls_made >= MAX_TOOL_CALLS:
                logger.info(
                    "Tool call limit reached (%d). Forcing final generation.",
                    MAX_TOOL_CALLS,
                )

        # Shouldn't reach here, but safety fallback
        return await self._llm.complete(
            prompt, system=system, temperature=0.2,
        )

    def _build_generation_prompt(
        self, finding: Finding, context: RepoContext, *, repo_prefs: dict | None = None
    ) -> str:
        """Build the generation prompt based on finding type."""
        # Get the current file content if available
        current_content = context.relevant_files.get(finding.file_path, "")

        type_instructions = {
            ContributionType.SECURITY_FIX: (
                "Fix this SECURITY vulnerability. Ensure the fix is complete "
                "and doesn't introduce new vulnerabilities."
            ),
            ContributionType.CODE_QUALITY: (
                "Improve the CODE QUALITY. Make the code cleaner, more maintainable, "
                "and more robust. Keep changes minimal and focused."
            ),
            ContributionType.DOCS_IMPROVE: (
                "Improve the DOCUMENTATION. Add missing docstrings, improve README sections, "
                "or fix documentation issues. Be thorough but concise."
            ),
            ContributionType.UI_UX_FIX: (
                "Fix this UI/UX issue. Improve accessibility, user experience, or visual design. "
                "Follow WCAG guidelines where applicable."
            ),
            ContributionType.PERFORMANCE_OPT: (
                "Optimize PERFORMANCE. Reduce time/space complexity, "
                "eliminate wasteful operations, or improve resource usage."
            ),
            ContributionType.FEATURE_ADD: (
                "Add this FEATURE. Keep the implementation clean, well-structured, and consistent "
                "with the existing codebase patterns."
            ),
            ContributionType.REFACTOR: (
                "REFACTOR this code. Improve structure and readability without changing behavior."
            ),
        }

        instruction = type_instructions.get(finding.type, "Fix this issue.")

        prompt = (
            f"## Task\n{instruction}\n\n"
            f"## Finding\n"
            f"- **Title**: {finding.title}\n"
            f"- **Severity**: {finding.severity.value}\n"
            f"- **File**: {finding.file_path}\n"
            f"- **Description**: {finding.description}\n"
        )

        # Inject repo preferences from outcome learning
        if repo_prefs:
            prefs_section = "\n## Repo Preferences (learned from past PRs)\n"
            if repo_prefs.get("rejected_types"):
                prefs_section += (
                    f"- **Avoid these PR types** (historically rejected): "
                    f"{', '.join(repo_prefs['rejected_types'])}\n"
                )
            if repo_prefs.get("preferred_types"):
                prefs_section += (
                    f"- **Preferred PR types** (historically merged): "
                    f"{', '.join(repo_prefs['preferred_types'])}\n"
                )
            if repo_prefs.get("merge_rate") is not None:
                rate = repo_prefs["merge_rate"]
                prefs_section += f"- **Merge rate**: {rate:.0%}\n"
            prompt += prefs_section

        if finding.suggestion:
            prompt += f"- **Suggestion**: {finding.suggestion}\n"

        if current_content:
            prompt += (
                f"\n## Current File Content ({finding.file_path})\n"
                f"```\n{current_content[:6000]}\n```\n"
            )

        # Cross-file: find other files with the same pattern
        other_affected_files = self._find_cross_file_instances(finding, context)
        if other_affected_files:
            prompt += (
                f"\n## ⚠️ IMPORTANT: Same issue in "
                f"{len(other_affected_files)} OTHER file(s)\n"
                "Fix ALL instances across ALL files in a single contribution.\n"
                "This produces a higher-quality PR that addresses the issue comprehensively.\n\n"
            )
            for fpath, fcontent in other_affected_files.items():
                prompt += f"### {fpath}\n```\n{fcontent[:3000]}\n```\n\n"

        prompt += (
            "\n## Output Format\n"
            "Return ONLY a JSON object matching the requested schema.\n"
            "Do NOT include explanations, markdown fences, or <think> tags.\n\n"
        )

        if current_content:
            # For EXISTING files: use search/replace blocks to preserve content
            prompt += (
                "Since this is an EXISTING file, use SEARCH/REPLACE blocks "
                "to make targeted edits. DO NOT rewrite the entire file.\n\n"
                "```json\n"
                "{\n"
                '  "changes": [\n'
                "    {\n"
                '      "path": "path/to/file",\n'
                '      "is_new_file": false,\n'
                '      "edits": [\n'
                "        {\n"
                '          "search": "exact text to find in the file",\n'
                '          "replace": "replacement text"\n'
                "        }\n"
                "      ]\n"
                "    }\n"
                "  ]\n"
                "}\n"
                "```\n\n"
                "RULES for search/replace:\n"
                "- `search` must be an EXACT substring from the current file\n"
                "- `replace` is what replaces it (can be longer/shorter)\n"
                "- To ADD new content, search for the text BEFORE the insertion "
                "point and include it + the new content in `replace`\n"
                "- To DELETE content, set `replace` to empty string\n"
                "- Keep each edit small and focused\n"
                "- DO NOT include the entire file in search or replace\n\n"
                "⚠️ CRITICAL RULES — FAILURE TO FOLLOW THESE WILL BREAK THE PATCH ENGINE:\n"
                "1. The `search` value MUST be an EXACT, VERBATIM, copy-paste of a "
                "CONTINUOUS block of lines from the file above. Character-for-character.\n"
                "2. NEVER use `...` or `# ...` or any placeholder to skip lines. "
                "If your edit spans a large block, you MUST include EVERY SINGLE LINE "
                "between the first and last line of the search block.\n"
                "3. DO NOT modify indentation, whitespace, quotes, or any character "
                "in the `search` string. It must match the source file byte-for-byte.\n"
                "4. Each `search` block must contain enough surrounding context "
                "(at least 3-5 lines) to be UNIQUE within the file. Do not use "
                "a 1-line search that could match multiple locations.\n"
                "5. NEVER paraphrase, reformat, or re-indent code in the `search` block. "
                "Copy it EXACTLY as it appears in the file content provided above.\n"
            )
        else:
            # For NEW files: provide full content
            prompt += (
                "Since this is a NEW file, provide the full content:\n\n"
                "```json\n"
                "{\n"
                '  "changes": [\n'
                "    {\n"
                '      "path": "path/to/file",\n'
                '      "content": "full content of the new file",\n'
                '      "is_new_file": true\n'
                "    }\n"
                "  ]\n"
                "}\n"
                "```\n"
            )

        return prompt

    def _find_cross_file_instances(self, finding: Finding, context: RepoContext) -> dict[str, str]:
        """Find other files in the repo with the same issue pattern.

        Searches relevant_files for code patterns similar to the primary
        finding's issue (e.g., same non-null assertion, same unsafe pattern).
        Returns {path: content} for files that likely have the same issue.
        """
        if not finding.file_path or not context.relevant_files:
            return {}

        # Extract key terms from the finding to search for
        keywords = self._extract_search_patterns(finding)
        if not keywords:
            return {}

        other_files: dict[str, str] = {}
        for fpath, content in context.relevant_files.items():
            if fpath == finding.file_path:
                continue
            # Check if any keyword pattern appears in this file
            content_lower = content.lower()
            matches = sum(1 for kw in keywords if kw.lower() in content_lower)
            if matches >= 2:  # At least 2 pattern matches = likely same issue
                other_files[fpath] = content
                if len(other_files) >= 3:  # Cap at 3 extra files to limit prompt size
                    break

        if other_files:
            logger.info(
                "🔗 Found same pattern in %d other file(s): %s",
                len(other_files),
                ", ".join(other_files.keys()),
            )
        return other_files

    @staticmethod
    def _extract_search_patterns(finding: Finding) -> list[str]:
        """Extract code patterns from finding description to search across files.

        Looks for code-like tokens in the finding's description and suggestion.
        """
        patterns = []
        text = f"{finding.description} {finding.suggestion or ''}"
        # Extract backtick-quoted code snippets
        import re

        for match in re.findall(r"`([^`]+)`", text):
            if len(match) > 3:  # Skip very short matches
                patterns.append(match)
        # Extract common code patterns mentioned
        for pattern in re.findall(r"(\w+\.\w+[!?]?(?:\(\))?)", text):
            if len(pattern) > 5:
                patterns.append(pattern)
        return patterns[:10]  # Cap at 10 patterns

    def _parse_changes(self, response: str, context: RepoContext) -> list[FileChange]:
        """Parse LLM response into FileChange objects.

        Supports two formats:
        1. Search/replace blocks (for existing files) — applies edits to original
        2. Full content (for new files) — uses content as-is
        """
        import yaml

        changes: list[FileChange] = []

        try:
            cleaned_response = re.sub(
                r"<think>[\s\S]*?</think>",
                "",
                response,
                flags=re.IGNORECASE,
            ).strip()

            payload_text = None

            json_match = re.search(
                r"```json\s*\n(.*?)\n\s*```",
                cleaned_response,
                re.DOTALL | re.IGNORECASE,
            )
            if json_match:
                payload_text = json_match.group(1)
            else:
                json_match = re.search(
                    r"\{[\s\S]*?(?:\"changes\"|'changes')[\s\S]*\}",
                    cleaned_response,
                )
                if json_match:
                    payload_text = json_match.group(0)
                else:
                    yaml_match = re.search(
                        r"changes:\s*[\s\S]*",
                        cleaned_response,
                        re.IGNORECASE,
                    )
                    if yaml_match:
                        payload_text = yaml_match.group(0)

            if not payload_text:
                return []

            try:
                data = json.loads(payload_text)
            except json.JSONDecodeError:
                data = yaml.safe_load(payload_text)

            if isinstance(data, dict):
                raw_changes = data.get("changes", [])
            elif isinstance(data, list):
                raw_changes = data
            else:
                return []

            for item in raw_changes:
                if not isinstance(item, dict) or "path" not in item:
                    continue

                path = str(item["path"]).strip().strip("`\"'")
                is_new = item.get("is_new_file", False)

                if "edits" in item and not is_new:
                    # Search/replace mode — apply edits to original content
                    original = context.relevant_files.get(path, "")
                    if not original:
                        logger.warning(
                            "No original content for %s (finding file not fetched), skipping edits",
                            path,
                        )
                        continue

                    new_content = original
                    edits_applied = 0
                    edits_total = len(item["edits"])
                    for edit in item["edits"]:
                        search = edit.get("search", "")
                        replace = edit.get("replace", "")
                        if not search:
                            continue

                        matched = False

                        # Try 1: Exact match
                        if search in new_content:
                            new_content = new_content.replace(search, replace, 1)
                            matched = True

                        # Try 2: Normalize trailing whitespace per line
                        if not matched:
                            norm_search = "\n".join(line.rstrip() for line in search.split("\n"))
                            norm_content = "\n".join(
                                line.rstrip() for line in new_content.split("\n")
                            )
                            if norm_search in norm_content:
                                idx = norm_content.index(norm_search)
                                start_line = norm_content[:idx].count("\n")
                                end_line = start_line + norm_search.count("\n")
                                lines = new_content.split("\n")
                                lines[start_line : end_line + 1] = replace.split("\n")
                                new_content = "\n".join(lines)
                                matched = True
                                logger.debug(
                                    "Fuzzy match (whitespace normalized) for %s",
                                    path,
                                )

                        # Try 3: Strip all leading/trailing whitespace
                        if not matched:
                            stripped_search = search.strip()
                            if len(stripped_search) > 20 and stripped_search in new_content:
                                new_content = new_content.replace(
                                    stripped_search, replace.strip(), 1
                                )
                                matched = True
                                logger.debug(
                                    "Fuzzy match (stripped) for %s",
                                    path,
                                )

                        # Try 4: Indentation-agnostic line-by-line matching
                        # Strips leading whitespace from each line for
                        # comparison, then re-applies the original file's
                        # indentation to the replacement block.
                        if not matched:
                            search_lines = search.split("\n")
                            content_lines = new_content.split("\n")
                            stripped_search_lines = [l.lstrip() for l in search_lines]

                            # Slide a window of len(search_lines) over content
                            window = len(search_lines)
                            if window >= 2:  # Require at least 2 lines for safety
                                for start_idx in range(len(content_lines) - window + 1):
                                    candidate = content_lines[start_idx : start_idx + window]
                                    candidate_stripped = [l.lstrip() for l in candidate]
                                    if candidate_stripped == stripped_search_lines:
                                        # Match found — re-indent replacement
                                        # using the original file's leading whitespace
                                        replace_lines = replace.split("\n")
                                        reindented: list[str] = []
                                        for j, rline in enumerate(replace_lines):
                                            if j < len(candidate):
                                                # Borrow indent from the corresponding original line
                                                orig_indent = candidate[j][: len(candidate[j]) - len(candidate[j].lstrip())]
                                            elif candidate:
                                                # Extra lines: use indent of the last matched line
                                                last = candidate[-1]
                                                orig_indent = last[: len(last) - len(last.lstrip())]
                                            else:
                                                orig_indent = ""
                                            # Strip the LLM's indent and apply the file's indent
                                            reindented.append(orig_indent + rline.lstrip())

                                        content_lines[start_idx : start_idx + window] = reindented
                                        new_content = "\n".join(content_lines)
                                        matched = True
                                        logger.debug(
                                            "Indent-agnostic match for %s (lines %d-%d)",
                                            path, start_idx + 1, start_idx + window,
                                        )
                                        break

                        if matched:
                            edits_applied += 1
                        else:
                            logger.warning(
                                "Search text not found in %s (tried exact + fuzzy + indent-agnostic). "
                                "Search[:%d]: %.80s...",
                                path,
                                len(search),
                                search.replace("\n", "\\n"),
                            )


                    logger.info(
                        "Edits for %s: %d/%d applied",
                        path,
                        edits_applied,
                        edits_total,
                    )

                    if edits_applied == 0:
                        logger.warning("No edits applied to %s, skipping file", path)
                        continue

                    changes.append(
                        FileChange(
                            path=path,
                            original_content=original,
                            new_content=new_content,
                            is_new_file=False,
                        )
                    )

                elif "content" in item:
                    # Full content mode (new files or fallback)
                    changes.append(
                        FileChange(
                            path=path,
                            new_content=item["content"],
                            is_new_file=is_new,
                        )
                    )

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning("Failed to parse changes JSON: %s", e)

        # Enforce max files limit
        if len(changes) > self._config.max_files_per_pr:
            logger.warning(
                "Too many files changed (%d > %d), truncating",
                len(changes),
                self._config.max_files_per_pr,
            )
            changes = changes[: self._config.max_files_per_pr]

        return changes

    async def _generate_commit_message(
        self, finding: Finding, changes: list[FileChange], context: RepoContext
    ) -> str:
        """Generate a conventional commit message."""
        type_prefixes = {
            ContributionType.SECURITY_FIX: "fix(security)",
            ContributionType.CODE_QUALITY: "refactor",
            ContributionType.DOCS_IMPROVE: "docs",
            ContributionType.UI_UX_FIX: "fix(ui)",
            ContributionType.PERFORMANCE_OPT: "perf",
            ContributionType.FEATURE_ADD: "feat",
            ContributionType.REFACTOR: "refactor",
        }

        prefix = type_prefixes.get(finding.type, "fix")
        files = ", ".join(c.path.split("/")[-1] for c in changes[:3])

        if self._config.commit_convention == "conventional":
            # Try to extract scope from file path
            scope = ""
            if changes:
                parts = changes[0].path.split("/")
                if (len(parts) >= 2 and parts[0] in ("packages", "apps", "libs")) or (
                    len(parts) >= 2 and parts[0] == "src"
                ):
                    scope = parts[1]
            if scope:
                return (
                    f"{prefix}({scope}): {finding.title.lower()}\n\n"
                    f"{finding.description}\n\n"
                    f"Affected files: {files}"
                )
            return (
                f"{prefix}: {finding.title.lower()}\n\n"
                f"{finding.description}\n\n"
                f"Affected files: {files}"
            )
        elif self._config.commit_convention == "angular":
            scope = changes[0].path.split("/")[0] if changes else ""
            return f"{prefix}({scope}): {finding.title.lower()}"
        else:
            return finding.title

    def _generate_branch_name(self, finding: Finding) -> str:
        """Generate a clean branch name from finding."""
        prefix_map = {
            ContributionType.SECURITY_FIX: "fix/security",
            ContributionType.CODE_QUALITY: "improve/quality",
            ContributionType.DOCS_IMPROVE: "docs",
            ContributionType.UI_UX_FIX: "fix/ui",
            ContributionType.PERFORMANCE_OPT: "perf",
            ContributionType.FEATURE_ADD: "feat",
            ContributionType.REFACTOR: "refactor",
        }
        prefix = prefix_map.get(finding.type, "fix")
        # Clean title for branch name
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", finding.title.lower()).strip("-")[:40]
        return f"contribai/{prefix}/{slug}"

    def _generate_pr_title(self, finding: Finding, *, guidelines=None) -> str:
        """Generate a PR title adapted to repo conventions."""
        # Use adaptive title if guidelines available
        if guidelines and guidelines.has_guidelines:
            from contribai.github.guidelines import (
                adapt_pr_title,
                extract_scope_from_path,
            )

            scope = extract_scope_from_path(finding.file_path or "", guidelines)
            return adapt_pr_title(
                finding.title,
                finding.type.value,
                guidelines,
                scope=scope,
            )

        # Default: emoji format
        type_labels = {
            ContributionType.SECURITY_FIX: "🔒 Security",
            ContributionType.CODE_QUALITY: "✨ Quality",
            ContributionType.DOCS_IMPROVE: "📝 Docs",
            ContributionType.UI_UX_FIX: "🎨 UI/UX",
            ContributionType.PERFORMANCE_OPT: "⚡ Performance",
            ContributionType.FEATURE_ADD: "🚀 Feature",
            ContributionType.REFACTOR: "♻️ Refactor",
        }
        label = type_labels.get(finding.type, "🔧 Fix")
        return f"{label}: {finding.title}"

    async def _self_review(self, contribution: Contribution, context: RepoContext) -> bool:
        """Have the LLM self-review the generated contribution."""
        changes_summary = "\n".join(
            f"- {c.path} ({'new' if c.is_new_file else 'modified'})" for c in contribution.changes
        )

        prompt = (
            "Review the following code contribution for quality:\n\n"
            f"**Title**: {contribution.title}\n"
            f"**Type**: {contribution.contribution_type.value}\n"
            f"**Finding**: {contribution.finding.description}\n"
            f"**Changes**:\n{changes_summary}\n\n"
            "For each changed file:\n"
        )
        for change in contribution.changes[:5]:
            review_snippet = self._build_review_snippet(change)
            prompt += f"\n### {change.path}\n```diff\n{review_snippet}\n```\n"

        prompt += (
            "\nAnswer these questions:\n"
            "1. Does the change correctly fix the described issue?\n"
            "2. Does it introduce any new bugs or security issues?\n"
            "3. Does it follow good coding practices?\n"
            "4. Is the change minimal and focused?\n\n"
            "Reply with APPROVE or REJECT followed by brief reasoning."
        )

        try:
            response = await self._llm.complete(prompt, temperature=0.1)
            response_upper = response.upper()
            if "REJECT" in response_upper:
                logger.info("Self-review rejected: %s", response[:200])
                return False
            if "APPROVE" in response_upper:
                return True
            logger.warning(
                "Self-review returned unrecognized verdict, approving by default: %s",
                response[:200],
            )
            return True
        except Exception as e:
            logger.warning("Self-review failed, approving by default: %s", e)
            return True  # Don't block on review failures

    @staticmethod
    def _build_review_snippet(change: FileChange, max_chars: int = 2000) -> str:
        """Build a compact diff-oriented review snippet for self-review."""
        if change.original_content is not None:
            diff = "".join(
                difflib.unified_diff(
                    change.original_content.splitlines(keepends=True),
                    change.new_content.splitlines(keepends=True),
                    fromfile=f"a/{change.path}",
                    tofile=f"b/{change.path}",
                    n=3,
                )
            ).strip()
            if diff:
                return diff[:max_chars]

        return change.new_content[:max_chars]
