"""Main code analysis orchestrator.

Runs multiple analyzers (security, code quality, docs, UI/UX) in parallel
using LLM-powered analysis. Each analyzer examines the repo through
a different lens and returns findings.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import re
import time
import uuid
from fnmatch import fnmatch

import json
from pathlib import Path

from farm_agent.core.config import AnalysisConfig
from farm_agent.core.exceptions import AnalysisError
from farm_agent.core.models import (
    AnalysisResult,
    ContributionType,
    FileNode,
    Finding,
    ImpactLevel,
    RepoContext,
    Repository,
    Severity,
    Vulnerability,
    VulnerabilityDossier,
)
from farm_agent.github.client import GitHubClient
from farm_agent.llm.provider import LLMProvider

logger = logging.getLogger(__name__)

# File extensions we can meaningfully analyze
ANALYZABLE_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".jsx",
    ".tsx",
    ".java",
    ".go",
    ".rs",
    ".rb",
    ".php",
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".cs",
    ".swift",
    ".kt",
    ".html",
    ".css",
    ".scss",
    ".vue",
    ".svelte",
    ".md",
    ".rst",
    ".txt",
    ".yaml",
    ".yml",
    ".json",
    ".toml",
}


class CodeAnalyzer:
    """Orchestrates multiple code analyzers using LLM."""

    def __init__(
        self,
        llm: LLMProvider,
        github: GitHubClient,
        config: AnalysisConfig,
    ):
        self._llm = llm
        self._github = github
        self._config = config

    async def analyze(self, repo: Repository) -> AnalysisResult:
        """Run full analysis on a repository.

        1. Fetch file tree
        2. Select files to analyze
        3. Run enabled analyzers in parallel
        4. Aggregate and deduplicate findings
        """
        start = time.monotonic()

        # Fetch file tree
        file_tree = await self._github.get_file_tree(repo.owner, repo.name)
        analyzable = self._select_files(file_tree)

        logger.info(
            "Analyzing %s: %d/%d files selected",
            repo.full_name,
            len(analyzable),
            len(file_tree),
        )

        # Build repo context
        context = await self._build_context(repo, file_tree, analyzable)

        # Run enabled analyzers
        all_findings: list[Finding] = []
        analyzer_tasks = []

        for analyzer_name in self._config.enabled_analyzers:
            analyzer_tasks.append(self._run_analyzer(analyzer_name, context))

        results = await asyncio.gather(*analyzer_tasks, return_exceptions=True)
        failed_analyzers: list[str] = []
        successful_analyzers = 0

        for analyzer_name, result in zip(self._config.enabled_analyzers, results, strict=False):
            if isinstance(result, Exception):
                failed_analyzers.append(f"{analyzer_name}: {result}")
                logger.error("Analyzer %s failed: %s", analyzer_name, result)
            elif isinstance(result, list):
                successful_analyzers += 1
                all_findings.extend(result)

        if failed_analyzers and successful_analyzers == 0:
            raise AnalysisError(
                f"All analyzers failed for {repo.full_name}",
                details={
                    "repo": repo.full_name,
                    "analyzers": failed_analyzers,
                },
            )

        if failed_analyzers:
            logger.warning(
                "Analysis of %s completed with %d/%d analyzer failures",
                repo.full_name,
                len(failed_analyzers),
                len(self._config.enabled_analyzers),
            )

        # Deduplicate
        findings = self._deduplicate(all_findings)

        # Filter by severity threshold
        findings = self._filter_severity(findings)

        # Build context summary for downstream consumers
        context_summary = self.summarize_findings(findings)
        logger.info(
            "Analysis of %s complete — %d findings. Summary: %s",
            repo.full_name,
            len(findings),
            context_summary[:100],
        )

        duration = time.monotonic() - start
        return AnalysisResult(
            repo=repo,
            findings=findings,
            analyzed_files=len(analyzable),
            skipped_files=len(file_tree) - len(analyzable),
            analysis_duration_sec=round(duration, 2),
        )

    @staticmethod
    def summarize_findings(findings: list[Finding]) -> str:
        """Compress findings into a concise summary.

        Inspired by DeerFlow's context engineering: summarize completed
        sub-tasks to preserve context window for subsequent processing.

        Returns a compact string suitable for injection into LLM prompts.
        """
        if not findings:
            return "No issues found."

        # Group by type
        by_type: dict[str, list[str]] = {}
        for f in findings:
            key = f.type.value if hasattr(f.type, "value") else str(f.type)
            by_type.setdefault(key, []).append(f.title)

        parts = []
        for ftype, titles in by_type.items():
            if len(titles) <= 2:
                parts.append(f"- {ftype}: {'; '.join(titles)}")
            else:
                parts.append(f"- {ftype}: {titles[0]}; {titles[1]}; +{len(titles) - 2} more")

        severity_counts = {}
        for f in findings:
            sev = f.severity.value if hasattr(f.severity, "value") else str(f.severity)
            severity_counts[sev] = severity_counts.get(sev, 0) + 1

        sev_str = ", ".join(f"{s}: {c}" for s, c in sorted(severity_counts.items()))
        return f"{len(findings)} findings ({sev_str}):\n" + "\n".join(parts)

    def _select_files(self, tree: list[FileNode]) -> list[FileNode]:
        """Select files suitable for analysis."""
        selected: list[FileNode] = []
        for node in tree:
            if node.type != "blob":
                continue

            # Check extension
            ext = "." + node.path.rsplit(".", 1)[-1] if "." in node.path else ""
            if ext.lower() not in ANALYZABLE_EXTENSIONS:
                continue

            # Check skip patterns
            if any(fnmatch(node.path, pat) for pat in self._config.skip_patterns):
                continue

            # Check file size
            if node.size > self._config.max_file_size_kb * 1024:
                continue

            selected.append(node)

        return selected

    async def _build_context(
        self,
        repo: Repository,
        tree: list[FileNode],
        analyzable: list[FileNode],
    ) -> RepoContext:
        """Build repository context for LLM analysis."""
        relevant_files: dict[str, str] = {}

        async def fetch_special(path: str, is_contrib: bool = False):
            with contextlib.suppress(Exception):
                if is_contrib:
                    return await self._github.get_contributing_guide(repo.owner, repo.name)
                return await self._github.get_file_content(repo.owner, repo.name, path)
            return None

        readme_task = asyncio.create_task(fetch_special("README.md"))
        contrib_task = asyncio.create_task(fetch_special("", is_contrib=True))

        # Fetch a sample of source files (up to 50 most important since we are overclocked)
        priority_files = self._prioritize_files(analyzable, tree)[:50]

        sem = asyncio.Semaphore(50)
        async def fetch_file(node: FileNode) -> tuple[str, str | None]:
            async with sem:
                try:
                    content = await self._github.get_file_content(repo.owner, repo.name, node.path)
                    return node.path, content
                except Exception as e:
                    logger.debug("Failed to fetch %s: %s", node.path, e)
                    return node.path, None

        file_tasks = [fetch_file(n) for n in priority_files]

        # Await all concurrently
        readme = await readme_task
        contributing = await contrib_task
        results = await asyncio.gather(*file_tasks)

        for path, content in results:
            if content:
                relevant_files[path] = content

        # Detect project profile and style
        profile = self._detect_project_profile(repo, tree, readme)
        style_guide = self._build_style_guide(relevant_files)
        coding_style = f"PROJECT PROFILE:\n{profile}\n\nSTYLE GUIDE:\n{style_guide}"

        return RepoContext(
            repo=repo,
            file_tree=tree,
            readme_content=readme,
            contributing_guide=contributing,
            relevant_files=relevant_files,
            coding_style=coding_style,
        )

    def _detect_project_profile(
        self,
        repo: Repository,
        tree: list[FileNode],
        readme: str | None,
    ) -> str:
        """Detect project type, tech stack, and conventions from file tree.

        Returns a concise profile string that helps LLM understand the codebase.
        """
        paths = {n.path.lower() for n in tree}
        names = {n.path.rsplit("/", 1)[-1].lower() for n in tree}

        # Detect project type
        project_type = "library"
        if any(f in names for f in ("manage.py", "wsgi.py", "asgi.py")):
            project_type = "web_app"
        elif any(f in names for f in ("server.py", "api.py", "routes.py", "app.py")):
            project_type = "api_server"
        elif any(f in names for f in ("main.py", "__main__.py", "cli.py")):
            if any("click" in p or "argparse" in p or "typer" in p for p in paths):
                project_type = "cli_tool"
        elif any(f in names for f in ("pipeline.py", "dag.py", "etl.py")):
            project_type = "data_pipeline"

        # Detect tech stack
        stack: list[str] = []
        stack_markers = {
            "django": ["manage.py", "settings.py", "urls.py"],
            "flask": ["flask"],
            "fastapi": ["fastapi"],
            "sqlalchemy": ["models.py", "alembic"],
            "react": ["package.json", "jsx", "tsx"],
            "pytest": ["conftest.py", "pytest.ini"],
            "celery": ["celery.py", "tasks.py"],
            "docker": ["dockerfile", "docker-compose.yml"],
        }
        for tech, markers in stack_markers.items():
            if any(m in p for p in paths for m in markers):
                stack.append(tech)

        # Detect conventions
        has_tests = any("test" in p for p in paths)
        has_ci = any(
            f in p for p in paths for f in (".github/workflows", ".gitlab-ci", "Jenkinsfile")
        )
        has_types = any("py.typed" in p or "types" in p for p in paths)
        has_docs = any(f in p for p in paths for f in ("docs/", "doc/", "sphinx"))

        return (
            f"Type: {project_type}\n"
            f"Language: {repo.language or 'unknown'}\n"
            f"Stack: {', '.join(stack) if stack else 'minimal'}\n"
            f"Tests: {'yes' if has_tests else 'no'}\n"
            f"CI: {'yes' if has_ci else 'no'}\n"
            f"Type hints: {'yes' if has_types else 'unknown'}\n"
            f"Docs: {'yes' if has_docs else 'minimal'}"
        )

    def _build_style_guide(self, files: dict[str, str]) -> str:
        """Extract coding conventions from sample files.

        Examines actual code to detect naming, error handling, and import patterns.
        Returns a concise style guide string.
        """
        if not files:
            return "No source files available for style detection."

        # Sample up to 3 Python files for style detection
        py_files = [(p, c) for p, c in files.items() if p.endswith(".py") and len(c) > 100][:3]
        if not py_files:
            # Try other languages
            code_files = [
                (p, c)
                for p, c in files.items()
                if any(p.endswith(e) for e in (".js", ".ts", ".go", ".rs")) and len(c) > 100
            ][:3]
            if not code_files:
                return "Could not detect style — no substantial source files."
            py_files = code_files

        # Analyze patterns
        conventions: list[str] = []
        all_code = "\n".join(c for _, c in py_files)

        # Naming convention
        if "snake_case" not in all_code and "camelCase" not in all_code:
            import re

            func_names = re.findall(r"def (\w+)", all_code)
            if func_names:
                snake = sum(1 for n in func_names if "_" in n)
                camel = sum(1 for n in func_names if n != n.lower() and "_" not in n)
                conventions.append(f"Naming: {'snake_case' if snake > camel else 'camelCase'}")

        # Error handling style
        if "raise" in all_code and "except" in all_code:
            conventions.append("Errors: try/except with raise")
        elif "Result" in all_code or "Ok(" in all_code:
            conventions.append("Errors: Result type pattern")

        # Docstring format
        if '"""' in all_code:
            if "Args:" in all_code:
                conventions.append("Docstrings: Google style")
            elif "Parameters" in all_code and "---" in all_code:
                conventions.append("Docstrings: NumPy style")
            elif ":param" in all_code:
                conventions.append("Docstrings: Sphinx style")
            else:
                conventions.append("Docstrings: simple/minimal")
        else:
            conventions.append("Docstrings: rare/none")

        # Import style
        import re

        abs_imports = len(re.findall(r"^from \w+\.\w+", all_code, re.MULTILINE))
        rel_imports = len(re.findall(r"^from \.", all_code, re.MULTILINE))
        if abs_imports + rel_imports > 0:
            conventions.append(
                f"Imports: {'absolute' if abs_imports > rel_imports else 'relative'}"
            )

        # Logging
        if "logger" in all_code or "logging" in all_code:
            conventions.append("Logging: stdlib logging")
        elif "print(" in all_code:
            conventions.append("Logging: print statements")

        return "\n".join(conventions) if conventions else "Standard conventions"

    def _prioritize_files(
        self,
        files: list[FileNode],
        tree: list[FileNode] | None = None,
    ) -> list[FileNode]:
        """Prioritize files for analysis by contribution value.

        Scores files based on:
        - Core logic (not tests, vendored, generated, or configs)
        - Size (medium-sized files are most useful)
        - Location (shallow = more important)
        """
        # Dirs/patterns that indicate low-value files
        skip_prefixes = (
            "test",
            "tests",
            "spec",
            "__pycache__",
            "node_modules",
            "vendor",
            "dist",
            "build",
            ".git",
            "migrations",
            "generated",
            "proto",
            "stubs",
        )

        def file_score(node: FileNode) -> float:
            path = node.path.lower()
            name = path.rsplit("/", 1)[-1]
            score = 50.0  # base score

            # Boost entry points and core files
            if name in ("main.py", "app.py", "server.py", "cli.py", "__main__.py"):
                score += 40
            elif name in ("api.py", "routes.py", "views.py", "handlers.py"):
                score += 35
            elif any(k in name for k in ("auth", "security", "middleware", "utils")):
                score += 30
            elif name in ("models.py", "schema.py", "types.py"):
                score += 25
            elif any(k in name for k in ("config", "settings")):
                score += 20

            # Penalize low-value files
            parts = path.split("/")
            if any(p.startswith(s) for p in parts for s in skip_prefixes):
                score -= 60
            if name.startswith("test_") or name.endswith("_test.py"):
                score -= 50
            if name in ("__init__.py", "conftest.py", "setup.py"):
                score -= 20

            # Prefer medium-sized files (200-2000 bytes = sweet spot)
            if 200 <= node.size <= 2000:
                score += 10
            elif node.size > 10000:
                score -= 5  # very large files are harder to analyze

            # Prefer shallow paths (core modules, not deeply nested)
            depth = len(parts)
            if depth <= 2:
                score += 15
            elif depth >= 5:
                score -= 10

            return score

        return sorted(files, key=file_score, reverse=True)

    async def _run_analyzer(self, name: str, context: RepoContext) -> list[Finding]:
        """Run a single LLM-powered analyzer."""
        prompts = {
            "security": self._security_prompt,
            "code_quality": self._code_quality_prompt,
            "docs": self._docs_prompt,
            "ui_ux": self._ui_ux_prompt,
            "performance": self._performance_prompt,
            "refactor": self._refactor_prompt,
            "testing": self._testing_prompt,
        }

        prompt_fn = prompts.get(name)
        if not prompt_fn:
            logger.warning("Unknown analyzer: %s", name)
            return []

        prompt = prompt_fn(context)

        # Build context-aware system prompt with project profile
        profile_ctx = ""
        if context.coding_style:
            profile_ctx = (
                f"\n\nCODEBASE CONTEXT (use this to calibrate your analysis):\n"
                f"{context.coding_style}\n\n"
                f"IMPORTANT: Only report issues relevant to this type of project. "
                f"Skip issues that don't apply to the detected stack/type.\n"
            )

        system = (
            "You are a senior software engineer performing a focused code review. "
            "You have deep expertise in real-world codebases and know which issues "
            "actually matter vs which are noise.\n\n"
            "For each finding, provide:\n"
            "- title: short descriptive title (be specific, not generic)\n"
            "- severity: low|medium|high|critical\n"
            "- impact_level: CRITICAL|HIGH|MEDIUM|LOW|TRIVIAL\n"
            "- file_path: path to the affected file\n"
            "- line_start: approximate line number (or 0 if unknown)\n"
            "- description: explain WHY this is a problem with concrete impact\n"
            "- suggestion: exact code-level fix (not vague advice)\n\n"
            "Return ONLY valid YAML. Do not include commentary before or after it.\n"
            "If no issues found, return exactly 'findings: []'.\n\n"
            f"{profile_ctx}"
            '═══════════════════════════════════════════════════════════════\n'
            '⛔ ZERO-TOLERANCE "ANTI-FARMING" CONSTRAINT — FOLLOW OR BE IGNORED:\n'
            'You are a senior engineer. Do NOT act like a spammy AI bot.\n\n'
            'STRICTLY FORBIDDEN from reporting:\n'
            '1. ANYTHING related to documentation, README, docstrings, or comments.\n'
            '2. Typos, grammar, spelling, or formatting issues (PEP8, Prettier, etc.).\n'
            '3. Naming conventions, import ordering, or whitespace issues.\n'
            '4. Missing type hints, unused imports, or "missing docstring" warnings.\n'
            '5. Exploratory or curiosity-driven tasks: '
            '"understand how X works", "read this file", "investigate Y".\n'
            '6. Adding or removing comments, TODOs, or FIXMEs.\n'
            '7. Changes that are purely cosmetic, stylistic, or subjective.\n'
            '8. "Test" files, "test" functions, or test-related modifications.\n\n'
            'ONLY report if it is ONE of the following:\n'
            '- A REAL logic bug that causes runtime crashes or incorrect behavior.\n'
            '- A proven security vulnerability with a concrete attack vector.\n'
            '- A memory leak, race condition, or concurrency bug.\n'
            '- A mathematically provable performance regression (O(n²) → O(n) '
            'with measurements).\n'
            '- A null/dereference that WILL crash if triggered.\n\n'
            'If the code works fine, OUTPUT NOTHING. '
            'Do NOT invent fake issues to look busy.\n'
            'Quality over quantity — return findings: [] if nothing real exists.\n'
            '═══════════════════════════════════════════════════════════════\n\n'
            "ANTI-FALSE-POSITIVE RULES (mandatory checks before reporting):\n"
            "1. ALREADY HANDLED — Is the code already protected by try/except, "
            "guards, or fallback patterns? If yes, do NOT report.\n"
            "2. BY DESIGN — Is the pattern intentional? (e.g., bare except in a "
            "daemon, hardcoded values in test fixtures). If yes, do NOT report.\n"
            "3. BOUNDED CONTEXT — Does the call chain guarantee safety? "
            "(e.g., dict access after `if key in dict`). If yes, do NOT report.\n"
            "4. TRIVIAL FIX — Would the fix add complexity without real benefit? "
            "(e.g., adding type hints to a 10-line script). If yes, do NOT report.\n"
            "5. COSMETIC — Is this purely stylistic with no functional impact? "
            "(e.g., prefer f-strings over .format()). If yes, do NOT report.\n\n"
            "Report ONLY issues that a senior developer would actually fix in a PR review. "
            "Quality over quantity — 1 genuine finding beats 5 false positives.\n"
            "Maximum 3 findings per analyzer."
        )

        try:
            response = await self._llm.complete(prompt, system=system, temperature=0.2)
            return self._parse_findings(response, name, context)
        except Exception as e:
            logger.error("Analyzer %s failed: %s", name, e)
            raise AnalysisError(
                f"Analyzer {name} failed: {e}",
                details={"analyzer": name},
            ) from e

    def _security_prompt(self, ctx: RepoContext) -> str:
        files_text = self._format_files(ctx)
        return (
            f"Analyze this {ctx.repo.language} repository for SECURITY vulnerabilities:\n\n"
            f"Repository: {ctx.repo.full_name}\n\n"
            f"{files_text}\n\n"
            "Focus on vulnerabilities with REAL exploitability:\n"
            "1. Hardcoded secrets/credentials (NOT test fixtures or placeholders)\n"
            "2. SQL injection (only if raw queries are used, NOT ORM calls)\n"
            "3. Command injection via unsanitized user input\n"
            "4. Path traversal in file operations\n"
            "5. Insecure deserialization (pickle, yaml.load without SafeLoader)\n"
            "6. Missing authentication on sensitive endpoints\n\n"
            "DO NOT report:\n"
            "- Hardcoded values in test/fixture files\n"
            "- Missing CSRF if the framework handles it (Django, etc.)\n"
            "- Generic 'missing input validation' without a concrete attack vector\n"
            "- Theoretical vulnerabilities that require physical access\n"
        )

    def _code_quality_prompt(self, ctx: RepoContext) -> str:
        files_text = self._format_files(ctx)
        return (
            f"Analyze this {ctx.repo.language} repository for CODE QUALITY bugs:\n\n"
            f"Repository: {ctx.repo.full_name}\n\n"
            f"{files_text}\n\n"
            "Focus on issues that cause BUGS or CRASHES in production:\n"
            "1. Unhandled None/null that will crash at runtime\n"
            "2. Resource leaks (unclosed files, connections, cursors)\n"
            "3. Race conditions in concurrent code\n"
            "4. Off-by-one errors in loops or slices\n"
            "5. Silent data corruption (wrong type coercion, truncation)\n"
            "6. Missing error propagation (swallowed exceptions hiding failures)\n\n"
            "DO NOT report:\n"
            "- Missing type hints (unless the project uses them everywhere else)\n"
            "- Code style preferences (naming, formatting)\n"
            "- 'Could be refactored' without a concrete bug\n"
            "- Missing logging (unless an error path silently fails)\n"
        )

    def _docs_prompt(self, ctx: RepoContext) -> str:
        readme = ctx.readme_content or "No README found"
        files_text = self._format_files(ctx)
        return (
            f"Analyze this {ctx.repo.language} repository for DOCUMENTATION gaps:\n\n"
            f"Repository: {ctx.repo.full_name}\n\n"
            f"README:\n{readme[:2000]}\n\n"
            f"{files_text}\n\n"
            "⚠️ ANTI-FARMING WARNING: Documentation-only changes are LOW VALUE.\n"
            "Set impact_level to TRIVIAL for ALL documentation findings UNLESS:\n"
            "- The documentation causes users to execute dangerous commands\n"
            "- Installation instructions are completely wrong and break setup\n"
            "- API examples have bugs that cause runtime errors when copied\n\n"
            "Look for ONLY these critical documentation issues:\n"
            "1. Code examples in README/docs that contain bugs causing crashes\n"
            "2. Installation instructions that are fundamentally broken\n"
            "3. Outdated API docs that reference removed functions\n\n"
            "DO NOT report:\n"
            "- Missing docstrings on functions\n"
            "- Missing type hints\n"
            "- Typos in comments or documentation\n"
            "- Missing CHANGELOG entries\n"
            "- Missing contributing guidelines\n"
            "- Formatting or style issues in docs\n"
        )

    def _ui_ux_prompt(self, ctx: RepoContext) -> str:
        files_text = self._format_files(ctx)
        return (
            f"Analyze this repository for UI/UX issues:\n\n"
            f"Repository: {ctx.repo.full_name} ({ctx.repo.language})\n\n"
            f"{files_text}\n\n"
            "Look for:\n"
            "1. Accessibility (a11y) issues (missing ARIA labels, alt text)\n"
            "2. Missing loading/skeleton states\n"
            "3. Missing error boundaries/states\n"
            "4. Responsiveness issues\n"
            "5. Color contrast problems\n"
            "6. Missing keyboard navigation\n"
            "7. Missing form validation feedback\n"
            "8. Poor empty states\n"
            "NOTE: Only analyze if the repo contains frontend code (HTML/CSS/JS/React/Vue/etc). "
            "If no frontend code found, return 'findings: []'.\n"
        )

    def _performance_prompt(self, ctx: RepoContext) -> str:
        files_text = self._format_files(ctx)
        return (
            f"Analyze this {ctx.repo.language} repository for PERFORMANCE issues:\n\n"
            f"Repository: {ctx.repo.full_name}\n\n"
            f"{files_text}\n\n"
            "Focus on issues with MEASURABLE impact (>10% improvement):\n"
            "1. N+1 queries — database/API calls inside loops\n"
            "2. Blocking I/O in async code — sync calls in event loop\n"
            "3. O(n²) algorithms where O(n) or O(n log n) is possible\n"
            "4. Memory leaks — growing collections without bounds\n"
            "5. Repeated expensive computation that should be cached\n\n"
            "DO NOT report:\n"
            "- Micro-optimizations (f-string vs .format(), list comp vs loop)\n"
            "- Theoretical perf issues in code that runs once at startup\n"
            "- 'Could use caching' without evidence the operation is expensive\n"
            "- String concatenation unless it's in a tight loop with large data\n"
        )

    def _refactor_prompt(self, ctx: RepoContext) -> str:
        files_text = self._format_files(ctx)
        return (
            f"Analyze this {ctx.repo.language} repository for REFACTORING opportunities:\n\n"
            f"Repository: {ctx.repo.full_name}\n\n"
            f"{files_text}\n\n"
            "⚠️ ANTI-FARMING WARNING: Subjective refactoring is FORBIDDEN.\n"
            "Set impact_level to TRIVIAL for ANY refactoring that is purely aesthetic.\n"
            "ONLY report refactorings that FIX or PREVENT real bugs:\n\n"
            "Look for:\n"
            "1. Dead code that could mask bugs or confuse maintainers\n"
            "2. DRY violations causing inconsistent bug fixes across copies\n"
            "3. God classes/modules with tangled state causing race conditions\n"
            "4. Deeply nested conditionals (>3 levels) hiding logic bugs\n\n"
            "DO NOT report:\n"
            "- Magic numbers/strings that are obvious from context\n"
            "- 'Could be cleaner' without a concrete bug risk\n"
            "- Renaming variables for style preference\n"
            "- Splitting functions just because they are long\n"
            "- Import ordering or formatting\n"
        )

    def _testing_prompt(self, ctx: RepoContext) -> str:
        files_text = self._format_files(ctx)
        return (
            f"Analyze this {ctx.repo.language} repository for TESTING gaps:\n\n"
            f"Repository: {ctx.repo.full_name}\n\n"
            f"{files_text}\n\n"
            "Look for:\n"
            "1. Public functions/methods with NO unit tests\n"
            "2. Critical business logic without test coverage\n"
            "3. Edge cases not covered by existing tests\n"
            "4. Error handling paths without tests\n"
            "5. Missing integration tests for API endpoints\n"
            "6. Untested configuration validation\n"
            "7. Missing tests for data transformations/serialization\n"
            "8. Race conditions or concurrency that needs testing\n\n"
            "For each finding, suggest a specific test that should be written. "
            "Focus on the most impactful missing tests — those covering critical "
            "code paths or frequently modified code.\n"
            "NOTE: If the repo has no test directory/framework at all, suggest "
            "setting up a test framework as one finding and specific tests as others.\n"
        )

    def _format_files(self, ctx: RepoContext) -> str:
        """Format relevant files for the prompt."""
        parts = []
        for path, content in ctx.relevant_files.items():
            truncated = content[:3000] if len(content) > 3000 else content
            parts.append(f"### {path}\n```\n{truncated}\n```")
        return "\n\n".join(parts) if parts else "No source files available."

    def _parse_findings(self, response: str, analyzer_name: str, ctx: RepoContext) -> list[Finding]:
        """Parse LLM response into Finding objects."""
        import yaml

        findings: list[Finding] = []

        type_map = {
            "security": ContributionType.SECURITY_FIX,
            "code_quality": ContributionType.CODE_QUALITY,
            "docs": ContributionType.README_FIX,
            "ui_ux": ContributionType.UI_UX_FIX,
            "performance": ContributionType.PERFORMANCE_OPT,
            "refactor": ContributionType.REFACTOR,
            "testing": ContributionType.CODE_QUALITY,
        }
        contrib_type = type_map.get(analyzer_name, ContributionType.CODE_QUALITY)

        try:
            yaml_text = response.strip()

            fence_match = re.search(
                r"```(?:yaml|yml|json)?\s*(.*?)```",
                response,
                re.IGNORECASE | re.DOTALL,
            )
            if fence_match:
                yaml_text = fence_match.group(1).strip()
            else:
                marker_positions = [
                    idx
                    for idx in (
                        response.find("findings:"),
                        response.find("- title:"),
                        response.find("title:"),
                    )
                    if idx >= 0
                ]
                if marker_positions:
                    yaml_text = response[min(marker_positions) :].strip()

            yaml_text = yaml_text.strip("` \n")

            try:
                parsed = yaml.safe_load(yaml_text)
            except Exception:
                parsed = self._parse_findings_fallback(yaml_text)

            if not parsed:
                return []

            if isinstance(parsed, list):
                items = parsed
            elif isinstance(parsed, dict):
                items = parsed.get("findings", [])
            else:
                items = self._parse_findings_fallback(yaml_text)

            for item in items:
                if not isinstance(item, dict):
                    continue

                severity_str = str(item.get("severity", "medium")).lower()
                try:
                    severity = Severity(severity_str)
                except ValueError:
                    severity = Severity.MEDIUM

                # Parse impact_level (Anti-Farming field)
                impact_str = str(item.get("impact_level", "MEDIUM")).upper()
                try:
                    impact = ImpactLevel(impact_str)
                except ValueError:
                    impact = ImpactLevel.MEDIUM

                findings.append(
                    Finding(
                        id=str(uuid.uuid4())[:8],
                        type=contrib_type,
                        severity=severity,
                        title=str(item.get("title", "Untitled finding")),
                        description=str(item.get("description", "")),
                        file_path=str(item.get("file_path", "")),
                        line_start=item.get("line_start"),
                        line_end=item.get("line_end"),
                        suggestion=item.get("suggestion"),
                        impact_level=impact,
                    )
                )
        except Exception as e:
            logger.warning("Failed to parse %s findings: %s", analyzer_name, e)

        logger.info("Analyzer %s found %d issues", analyzer_name, len(findings))
        return findings

    @staticmethod
    def _parse_findings_fallback(text: str) -> list[dict[str, str]]:
        """Parse loosely structured key/value findings when YAML decoding fails."""
        items: list[dict[str, str]] = []
        current: dict[str, str] | None = None
        current_field: str | None = None

        for raw_line in text.splitlines():
            line = raw_line.rstrip()
            match = re.match(
                r"^\s*(?:-\s*)?"
                r"(title|severity|file_path|line_start|line_end|description|suggestion)"
                r"\s*:\s*(.*)$",
                line,
                re.IGNORECASE,
            )
            if match:
                field = match.group(1).lower()
                value = match.group(2).strip().strip("`")
                if field == "title":
                    if current:
                        items.append(current)
                    current = {}
                if current is None:
                    current = {}
                current[field] = value
                current_field = field
                continue

            if current and current_field in {"description", "suggestion"}:
                continuation = line.strip().strip("`")
                if continuation:
                    existing = current.get(current_field, "")
                    current[current_field] = f"{existing}\n{continuation}".strip()

        if current:
            items.append(current)

        return items

    def _deduplicate(self, findings: list[Finding]) -> list[Finding]:
        """Remove duplicate findings."""
        seen: set[str] = set()
        unique: list[Finding] = []
        for f in findings:
            key = f"{f.file_path}:{f.title}:{f.severity}"
            if key not in seen:
                seen.add(key)
                unique.append(f)
        return unique

    def _filter_severity(self, findings: list[Finding]) -> list[Finding]:
        """Filter findings by minimum severity threshold."""
        order = [Severity.LOW, Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL]
        # Define a mapping from Severity enum to an integer order for comparison
        severity_order = {
            Severity.LOW.value: 0,
            Severity.MEDIUM.value: 1,
            Severity.HIGH.value: 2,
            Severity.CRITICAL.value: 3,
        }
        try:
            threshold_enum = Severity(self._config.severity_threshold)
            threshold = severity_order.get(threshold_enum.value, 1) # Default to MEDIUM's order
        except ValueError:
            threshold = severity_order.get(Severity.MEDIUM.value, 1) # Default to MEDIUM's order
        return [f for f in findings if severity_order.get(f.severity.value, 0) >= threshold]

    # ── Maintainer Vibe Check ─────────────────────────────────────────────

    async def check_maintainer_vibe(
        self, repo_full_name: str, comments_context: str
    ) -> str:
        """Classify maintainer persona from recent PR review comments.

        Uses the LLM to analyze comment tone and returns one of:
        - WELCOMING: polite, constructive, encourages contributors.
        - STRICT: demanding about quality, but professional and fair.
        - HOSTILE: toxic, insulting, passive-aggressive, or arbitrary rejections.

        Returns the classification string. Defaults to "WELCOMING" on failure.
        """
        system = (
            "You are a senior developer evaluating open-source repository culture. "
            "Read the following recent comments made by maintainers of this repository.\n\n"
            "CRITICAL: Focus ONLY on the interpersonal tone and attitude between "
            "the reviewer and the author. Completely ignore technical discussions "
            "about system behavior (e.g., 'the network environment is hostile', "
            "'strict mode is enabled'). We are evaluating human-to-human toxicity, "
            "not code logic."
        )
        prompt = (
            f"## Maintainer Comments from {repo_full_name}\n\n"
            f"{comments_context}\n\n"
            "## Task\n"
            "Classify the maintainer's persona into EXACTLY one of three categories:\n"
            "1. WELCOMING — Polite, constructive, encourages contributors.\n"
            "2. STRICT — Highly demanding about code quality, but professional and fair.\n"
            "3. HOSTILE — Toxic, insulting, passive-aggressive, or arbitrarily "
            "rejecting PRs without clear guidance.\n\n"
            "Respond with ONLY the single category word (WELCOMING, STRICT, or HOSTILE)."
        )

        try:
            response = await self._llm.complete(
                prompt, system=system, temperature=0.1
            )
            classification = response.strip().upper()
            # Extract the classification word from potential surrounding text
            for label in ("HOSTILE", "STRICT", "WELCOMING"):
                if label in classification:
                    logger.info(
                        "Vibe check for %s: %s", repo_full_name, label
                    )
                    return label
            # Fallback if response is unexpected
            logger.warning(
                "Vibe check: unexpected LLM response for %s: %s",
                repo_full_name, classification[:50],
            )
            return "WELCOMING"
        except Exception as exc:
            logger.warning(
                "Vibe check LLM call failed for %s: %s, assuming WELCOMING",
                repo_full_name, exc,
            )
            return "WELCOMING"


# ── Bloodhound Red Team Analyzer ────────────────────────────────────────────────


class BloodhoundAnalyzer:
    """AST-grep pre-filter → LLM White-Hat audit pipeline.

    Uses local ast-grep (sg) rules to find exact bug patterns first,
    then sends ONLY the flagged snippets to the LLM for validation,
    POC generation, and fix suggestion. This drastically reduces LLM
    API costs compared to blind-reading entire codebases.
    """

    LANGUAGE_RULE_PREFIX: dict[str, str] = {
        "Python": "python",
        "JavaScript": "js",
        "TypeScript": "ts",
        "Go": "go",
        "Rust": "rust",
        "Solidity": "solidity",
    }

    SG_SCAN_TIMEOUT = 120
    SEMGREP_TIMEOUT = 180

    def __init__(
        self,
        llm: LLMProvider,
        github: GitHubClient,
        config: AnalysisConfig,
        memory=None,
    ):
        self._llm = llm
        self._github = github
        self._config = config
        self._memory = memory
        self._sg_available: bool | None = None
        self._red_team_client: LLMProvider | None = None

    def _forbidden_paths(self) -> list[str]:
        """Return the lowercase set of directory names indicating non-production code."""
        return [p.lower() for p in getattr(self._config, "forbidden_paths", [])]

    def _check_sg_available(self) -> bool:
        if self._sg_available is not None:
            return self._sg_available

        import shutil

        if shutil.which("sg") is None:
            logger.error(
                "ast-grep (sg) binary not found in PATH. "
                "Bloodhound requires sg. Aborting scan."
            )
            self._sg_available = False
        else:
            logger.info("ast-grep (sg) binary found — Bloodhound ready")
            self._sg_available = True
        return self._sg_available

    def _get_red_team_provider(self) -> LLMProvider | None:
        """Lazily create an OpenRouter LLM provider for Red Team audits.

        Returns None if the OpenRouter API key is not configured.
        """
        if self._red_team_client is not None:
            return self._red_team_client

        from farm_agent.core.config import LLMConfig
        from farm_agent.llm.provider import OpenRouterProvider

        api_key = ""
        if hasattr(self._config, "openrouter_api_key"):
            api_key = self._config.openrouter_api_key
        if not api_key and hasattr(self, "_llm") and hasattr(self._llm, "config"):
            api_key = getattr(self._llm.config, "openrouter_api_key", "")

        if not api_key:
            logger.debug("No OpenRouter API key configured — will use default LLM for Red Team audit")
            return None

        red_team_model = getattr(self._config, "red_team_model", "cognitivecomputations/dolphin-mistral-24b-venice-edition:free")
        rt_config = LLMConfig(
            provider="openrouter",
            model=red_team_model,
            api_key="",
            openrouter_api_key=api_key,
            temperature=0.1,
            max_tokens=4096,
        )
        self._red_team_client = OpenRouterProvider(rt_config)
        logger.info(
            "Red Team provider initialized: OpenRouter (%s)",
            red_team_model,
        )
        return self._red_team_client

    def _resolve_rule_files(self, language: str | None) -> list[Path]:
        rules_dir = Path("ast_rules")
        if not rules_dir.is_dir():
            logger.warning("ast_rules/ directory not found at %s", rules_dir.resolve())
            return []

        if not language:
            all_rules = sorted(rules_dir.glob("*.yaml"))
            if all_rules:
                logger.info("No language specified — using all %d rule files", len(all_rules))
            return all_rules

        prefix = self.LANGUAGE_RULE_PREFIX.get(language)
        if prefix is None:
            logger.info("No ast-grep rule prefix for language '%s' — skipping bloodhound", language)
            return []

        rule_files = sorted(rules_dir.glob(f"{prefix}-*.yaml"))
        logger.info("Language '%s' → prefix '%s' → %d rule files", language, prefix, len(rule_files))
        return rule_files

    async def _clone_repo_shallow(self, repo: Repository) -> Path | None:
        import shutil as shutil_mod
        import subprocess
        import tempfile

        clone_url = repo.clone_url or f"https://github.com/{repo.full_name}.git"
        tmp_dir = tempfile.mkdtemp(prefix=f"bloodhound_{repo.full_name.replace('/', '_')}_")

        try:
            proc = subprocess.run(
                ["git", "clone", "--depth", "1", clone_url, tmp_dir],
                capture_output=True,
                text=True,
                timeout=120,
            )
            if proc.returncode != 0:
                logger.error("Failed to clone %s: %s", repo.full_name, proc.stderr[:500])
                shutil_mod.rmtree(tmp_dir, ignore_errors=True)
                return None

            logger.info("Cloned %s → %s", repo.full_name, tmp_dir)
            return Path(tmp_dir)
        except subprocess.TimeoutExpired:
            logger.error("Timeout cloning %s", repo.full_name)
            shutil_mod.rmtree(tmp_dir, ignore_errors=True)
            return None
        except Exception as exc:
            logger.error("Error cloning %s: %s", repo.full_name, exc)
            shutil_mod.rmtree(tmp_dir, ignore_errors=True)
            return None

    async def _run_sg_scan(self, rule_file: Path, repo_path: Path) -> list[dict]:
        try:
            proc = await asyncio.create_subprocess_exec(
                "sg", "scan", "--rule", str(rule_file), "--json=compact", str(repo_path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=self.SG_SCAN_TIMEOUT
            )

            # ast-grep exits with code 1 when it finds matches (diagnostic tool
            # convention).  Only treat exit code >= 2 as a true failure.
            if proc.returncode not in (0, 1):
                stderr_text = stderr.decode("utf-8", errors="replace")[:500]
                logger.debug("sg scan returned %d for rule %s: %s", proc.returncode, rule_file.name, stderr_text)
                return []

            raw = stdout.decode("utf-8", errors="replace").strip()
            if not raw:
                return []

            try:
                json_data = json.loads(raw)
            except json.JSONDecodeError as e:
                logger.warning("sg scan returned invalid JSON for rule %s: %s", rule_file.name, e)
                return []

            # ast-grep may emit:
            #   - A JSON object with "matches" / "results" key → list of match dicts
            #   - A JSON array directly → list of match dicts
            #   - A JSON scalar or deeply nested struct → skip safely
            raw_matches: list[dict] = []
            if isinstance(json_data, list):
                raw_matches = json_data
            elif isinstance(json_data, dict):
                for key in ("matches", "results"):
                    val = json_data.get(key)
                    if isinstance(val, list):
                        raw_matches = val
                        break

            matches = []
            for item in raw_matches:
                try:
                    if not isinstance(item, dict):
                        continue

                    file_path = item.get("file") or item.get("path") or ""
                    if file_path:
                        try:
                            file_path = str(Path(file_path).relative_to(repo_path))
                        except ValueError:
                            pass

                    range_obj = item.get("range") or {}
                    start_obj = range_obj.get("start") if isinstance(range_obj, dict) else {}
                    line_num = start_obj.get("line") if isinstance(start_obj, dict) else 0
                    if not line_num:
                        line_num = item.get("line", 0)

                    text = item.get("text") or item.get("match") or ""

                    matches.append({
                        "file": str(file_path),
                        "line": int(line_num) if line_num else 0,
                        "match": str(text),
                        "rule": rule_file.stem,
                    })
                except Exception:
                    continue

            if matches:
                logger.info("Rule %s: %d matches", rule_file.name, len(matches))
            return matches

        except asyncio.TimeoutError:
            logger.warning("sg scan timed out for rule %s", rule_file.name)
            return []
        except Exception as exc:
            logger.error("sg scan failed for rule %s: %s", rule_file.name, exc)
            return []

    def _check_semgrep_available(self) -> bool:
        if hasattr(self, "_semgrep_available") and self._semgrep_available is not None:
            return self._semgrep_available

        import shutil

        if shutil.which("semgrep") is None:
            logger.info("semgrep binary not found — Bloodhound Semgrep radar disabled")
            self._semgrep_available = False
        else:
            logger.info("semgrep binary found — Bloodhound Semgrep radar ready")
            self._semgrep_available = True
        return self._semgrep_available

    async def _run_semgrep(
        self, repo_path: Path, extra_rulesets: list[str] | None = None
    ) -> list[dict]:
        if not self._check_semgrep_available():
            return []

        rulesets = list(getattr(self._config, "semgrep_rulesets", []))
        if extra_rulesets:
            rulesets.extend(extra_rulesets)
        if not rulesets:
            logger.info("No Semgrep rulesets configured — skipping Semgrep radar")
            return []

        cmd = ["semgrep", "scan", "--json", "--quiet"]
        for ruleset in rulesets:
            cmd.extend(["--config", ruleset])
        cmd.append(str(repo_path))

        logger.info(
            "Running Semgrep with %d rulesets against %s",
            len(rulesets),
            repo_path.name,
        )

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=self.SEMGREP_TIMEOUT
            )

            if proc.returncode not in (0, 1):
                stderr_text = stderr.decode("utf-8", errors="replace")[:500]
                logger.warning(
                    "Semgrep returned exit code %d: %s",
                    proc.returncode,
                    stderr_text,
                )

            data = json.loads(stdout.decode("utf-8", errors="replace"))
            results = data.get("results", [])

            matches = []
            for result in results:
                file_path = result.get("path", "")
                if file_path:
                    try:
                        file_path = str(Path(file_path).relative_to(repo_path))
                    except ValueError:
                        pass

                line_num = result.get("start", {}).get("line", 0)
                lines_text = result.get("extra", {}).get("lines", "")
                check_id = result.get("check_id", "semgrep-unknown")

                rule_name = f"semgrep:{check_id}"

                matches.append({
                    "file": file_path,
                    "line": line_num,
                    "match": lines_text,
                    "rule": rule_name,
                })

            logger.info("Semgrep found %d matches for %s", len(matches), repo_path.name)
            return matches

        except asyncio.TimeoutError:
            logger.warning("Semgrep scan timed out (%ds) for %s", self.SEMGREP_TIMEOUT, repo_path.name)
            return []
        except json.JSONDecodeError:
            logger.warning("Semgrep returned invalid JSON for %s", repo_path.name)
            return []
        except Exception as exc:
            logger.error("Semgrep scan failed for %s: %s", repo_path.name, exc)
            return []

    async def _run_ast_grep(self, rule_files: list[Path], repo_path: Path) -> list[dict]:
        logger.info("Running %d ast-grep rules against %s", len(rule_files), repo_path.name)
        scan_tasks = [self._run_sg_scan(rf, repo_path) for rf in rule_files]
        all_results = await asyncio.gather(*scan_tasks)

        all_matches = []
        for result in all_results:
            all_matches.extend(result)

        seen: set[tuple[str, int, str]] = set()
        unique = []
        for m in all_matches:
            key = (m["file"], m["line"], m["rule"])
            if key not in seen:
                seen.add(key)
                unique.append(m)

        logger.info("ast-grep found %d unique matches across %d rules", len(unique), len(rule_files))
        return unique

    async def _white_hat_audit(
        self, repo_url: str, repo_name: str, matches: list[dict]
    ) -> VulnerabilityDossier:
        context_parts = []
        max_chars = getattr(self._llm.config, "max_snippet_chars", 15000) if hasattr(self, "_llm") and hasattr(self._llm, "config") else 15000
        
        for m in matches:
            severity = m.get("severity", "UNKNOWN").upper()
            if severity in ("INFO", "LOW"):
                continue
                
            snippet = m.get('match', '')
            if len(snippet) > max_chars:
                logger.warning("[FINOPS] Snippet truncated to fit 32k context window.")
                snippet = snippet[:max_chars]

            context_parts.append(
                f"File: {m['file']}\nLine: {m['line']}\nRule: {m['rule']}\nSnippet:\n{snippet}\n"
            )
            
        if not context_parts:
            # If everything was filtered out, skip LLM call
            return VulnerabilityDossier(repo_url=repo_url, target_commit="unknown", vulnerabilities=[])

        context_str = "\n---\n".join(context_parts)

        system_prompt = """You are an elite, ruthless Red Team exploit developer and vulnerability researcher. 
Your singular goal is to discover and weaponize ZERO-DAY vulnerabilities in the provided code snippets. 
DO NOT act as a polite auditor. Think strictly like an attacker.

Your core directives:
1. THE ATTACK VECTOR: Look for deeply hidden flaws—Race Conditions, Deserialization triggers, Memory Corruptions (Use-After-Free), Prototype Pollution, Logic Bypasses, and Blind SQLi.
2. CHAINING: Do not just look at the single line; deduce how this snippet connects to user input or global state to form an exploit chain.
3. RUTHLESSNESS: If the code relies on "security by obscurity" or weak default configurations, tear it apart.

You will receive an ast-grep match report. 
- If the code is genuinely secure and cannot be exploited in any scenario, you MUST return [{"file": "NONE"}].
- If it is exploitable, you must provide the exact attack path.

You MUST respond strictly in the following JSON array format. No markdown, no conversational text.
[
    {
        "file": "path/to/file",
        "line": 123,
        "snippet": "the vulnerable code",
        "poc": "Step-by-step ATTACK PAYLOAD to exploit this flaw (be technical and precise).",
        "fix": "The architectural patch to kill this attack vector.",
        "impact": "CRITICAL: Remote Code Execution via..."
    }
]"""

        user_prompt = (
            f"Repository: {repo_url}\n\n"
            f"The following code snippets were flagged by our static analyzer "
            f"for repository {repo_name}:\n\n"
            f"{context_str}\n\n"
            f"Audit each snippet. Validate true positives and reject false positives. "
            f"Return the JSON array."
        )

        try:
            client = self._get_red_team_provider()
            if client is not None:
                daily_limit = getattr(self._config, "red_team_daily_limit", 1000)
                if self._memory is not None:
                    usage = await self._memory.get_openrouter_usage_today()
                    if usage >= daily_limit:
                        logger.warning(
                            "OpenRouter daily limit reached (%d/%d) — falling back to default LLM",
                            usage, daily_limit,
                        )
                        client = None
                    else:
                        logger.info("OpenRouter Red Team audit (%d/%d today)", usage + 1, daily_limit)

            if client is not None:
                response = await client.complete(user_prompt, system=system_prompt, temperature=0.1)
                if self._memory is not None:
                    await self._memory.record_openrouter_usage()
            else:
                logger.info("No OpenRouter provider — using default LLM for White-Hat audit")
                response = await self._llm.complete(user_prompt, system=system_prompt, temperature=0.1)

            return self._parse_audit_response(response, repo_url, forbidden_paths=self._forbidden_paths())
        except Exception as exc:
            # If OpenRouter rate-limits (429, 403, 5xx), fall back to default LLM
            # rather than discarding the matches entirely.
            from farm_agent.core.exceptions import LLMRateLimitError
            if isinstance(exc, LLMRateLimitError):
                logger.warning(
                    "[RED TEAM OFFLINE] OpenRouter rate limit hit. Initiating Fallback to Minimax M2.7."
                )
                try:
                    response = await self._llm.complete(user_prompt, system=system_prompt, temperature=0.1)
                    return self._parse_audit_response(response, repo_url, forbidden_paths=self._forbidden_paths())
                except Exception as fallback_exc:
                    logger.error("White-Hat audit fallback LLM also failed: %s", fallback_exc)
                    return VulnerabilityDossier(repo_url=repo_url, target_commit="unknown", vulnerabilities=[])
            logger.error("White-Hat audit LLM call failed: %s", exc)
            return VulnerabilityDossier(repo_url=repo_url, target_commit="unknown", vulnerabilities=[])

    def _classify_context(self, file_path: str, forbidden_paths: list[str] | None = None) -> str:
        """Classify a file path as PRODUCTION or LOW_PRIORITY_CONTEXT.

        If any segment of the normalized path matches a forbidden directory
        name, the file is considered non-production (test, example, demo, etc.)
        and tagged LOW_PRIORITY_CONTEXT.
        """
        if forbidden_paths is None:
            forbidden_paths = []

        normalized = file_path.replace("\\", "/").lower()
        segments = normalized.split("/")

        for segment in segments:
            if segment in forbidden_paths:
                return "LOW_PRIORITY_CONTEXT"

        return "PRODUCTION"

    def _parse_audit_response(self, response: str, repo_url: str, forbidden_paths: list[str] | None = None) -> VulnerabilityDossier:
        import re as _re

        text = response.strip()

        fence_match = _re.search(r"```(?:json)?\s*(.*?)```", text, _re.DOTALL | _re.IGNORECASE)
        if fence_match:
            text = fence_match.group(1).strip()

        bracket_start = text.find("[")
        bracket_end = text.rfind("]")
        if bracket_start != -1 and bracket_end != -1 and bracket_end > bracket_start:
            text = text[bracket_start:bracket_end + 1]

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            logger.warning("Failed to parse LLM audit response as JSON")
            return VulnerabilityDossier(repo_url=repo_url, target_commit="unknown", vulnerabilities=[])

        if not isinstance(parsed, list):
            logger.warning("LLM audit response is not a JSON array")
            return VulnerabilityDossier(repo_url=repo_url, target_commit="unknown", vulnerabilities=[])

        vulns = []
        for item in parsed:
            if not isinstance(item, dict):
                continue
            try:
                file_path = str(item.get("file", ""))
                context_type = self._classify_context(file_path, forbidden_paths)
                vulns.append(Vulnerability(
                    file=file_path,
                    line=int(item.get("line", 0)),
                    snippet=str(item.get("snippet", "")),
                    poc=str(item.get("poc", "")),
                    fix=str(item.get("fix", "")),
                    impact=str(item.get("impact", "")),
                    context_type=context_type,
                ))
            except (ValueError, TypeError):
                continue

        return VulnerabilityDossier(repo_url=repo_url, target_commit="unknown", vulnerabilities=vulns)

    async def run_bloodhound(self, repo: Repository) -> VulnerabilityDossier:
        """Execute the full Bloodhound pipeline for a repository.

        Runs ast-grep and optionally Semgrep concurrently, merges
        findings, then sends to the Red Team LLM for validation.
        """
        empty_dossier = VulnerabilityDossier(
            repo_url=repo.url, target_commit="unknown", vulnerabilities=[]
        )

        import shutil

        clone_path = await self._clone_repo_shallow(repo)
        if clone_path is None:
            logger.error("Failed to clone %s — aborting bloodhound", repo.full_name)
            return empty_dossier

        try:
            # ── Concurrent Radar: ast-grep + Semgrep ──
            tasks = []
            task_labels = []

            # ast-grep radar
            sg_available = self._check_sg_available()
            if sg_available:
                rule_files = self._resolve_rule_files(repo.language)
                if rule_files:
                    tasks.append(self._run_ast_grep(rule_files, clone_path))
                    task_labels.append(f"ast-grep({len(rule_files)} rules)")

            # Semgrep radar
            use_semgrep = getattr(self._config, "use_semgrep", False)
            if use_semgrep:
                extra_rulesets: list[str] = []
                if repo.language:
                    lang_lower = repo.language.lower()
                    if lang_lower == "go":
                        extra_rulesets.append("p/golang")
                    elif lang_lower == "solidity":
                        extra_rulesets.extend(["p/solidity", "p/smart-contracts", "p/jwt"])
                tasks.append(self._run_semgrep(clone_path, extra_rulesets=extra_rulesets or None))
                base_rulesets = list(getattr(self._config, "semgrep_rulesets", []))
                total_rulesets = len(base_rulesets) + len(extra_rulesets)
                task_labels.append(f"semgrep({total_rulesets} rulesets)")

            # If neither tool is available, return empty dossier
            if not tasks:
                logger.warning(
                    "No radar tools available (ast-grep=%s, semgrep=%s) for %s — skipping bloodhound",
                    sg_available, use_semgrep, repo.full_name,
                )
                return empty_dossier

            results = await asyncio.gather(*tasks)

            # Merge and cross-tool deduplicate by (file, line)
            all_matches = []
            for result in results:
                all_matches.extend(result)

            seen: set[tuple[str, int]] = set()
            unique_matches = []
            for m in all_matches:
                key = (m["file"], m["line"])
                if key not in seen:
                    seen.add(key)
                    unique_matches.append(m)

            logger.info(
                "Radar [%s]: %d unique matches for %s",
                " + ".join(task_labels) if task_labels else "none",
                len(unique_matches),
                repo.full_name,
            )

            if not unique_matches:
                logger.info("Clean sweep — no matches for %s, skipping LLM audit", repo.full_name)
                return empty_dossier

            dossier = await self._white_hat_audit(
                repo_url=repo.url, repo_name=repo.full_name, matches=unique_matches,
            )

            if dossier.has_bugs():
                logger.info(
                    "Bloodhound: %d validated vulnerabilities in %s",
                    len(dossier.vulnerabilities), repo.full_name,
                )
            else:
                logger.info("Bloodhound: all matches were false positives for %s", repo.full_name)

            return dossier

        finally:
            try:
                shutil.rmtree(str(clone_path), ignore_errors=True)
                logger.debug("Cleaned up clone at %s", clone_path)
            except Exception:
                pass
