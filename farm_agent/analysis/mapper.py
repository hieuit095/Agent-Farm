"""Repository skeleton mapper.

Generates a token-efficient structural map of a repository listing
file paths, classes, and function signatures — strictly excluding
function bodies, variable assignments, and docstrings.

Uses Python's ``ast`` module for ``.py`` files and regex patterns
for JS/TS/Go/Rust.  No external parsing libraries required.
"""

from __future__ import annotations

import ast
import contextlib
import logging
import re
from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)

# Extensions considered "code" files
CODE_EXTENSIONS = frozenset({
    ".py", ".js", ".ts", ".jsx", ".tsx",
    ".go", ".rs",
    ".java", ".rb", ".c", ".cpp", ".h", ".hpp",
    ".cs", ".swift", ".kt",
})

# Extensions explicitly skipped (non-code / config / docs)
SKIP_EXTENSIONS = frozenset({
    ".md", ".txt", ".rst", ".json", ".yaml", ".yml",
    ".toml", ".cfg", ".ini", ".lock", ".csv", ".xml",
    ".html", ".css", ".scss", ".svg", ".png", ".jpg",
    ".gif", ".ico", ".woff", ".woff2", ".eot", ".ttf",
    ".map", ".min.js", ".min.css",
})

# Hard limits to protect the LLM context window
MAX_FILES = 500
MAX_OUTPUT_CHARS = 100_000


class RepoMapper:
    """Generates a structural skeleton map of a repository."""

    async def generate_map(
        self,
        file_tree: list,
        fetch_content: Callable[[str], Awaitable[str]],
    ) -> str:
        """Build a text-based skeleton map of the repository.

        Args:
            file_tree: List of FileNode-like objects with ``path`` and
                       ``type`` attributes (``"blob"`` for files).
            fetch_content: Async callable that accepts a file path and
                           returns the file content as a string.

        Returns:
            A formatted skeleton string listing file paths, classes,
            and function/method signatures.
        """
        # Filter to code files only
        code_files = [
            f for f in file_tree
            if getattr(f, "type", "") == "blob" and self._is_code_file(f.path)
        ]

        # Enforce hard file limit
        if len(code_files) > MAX_FILES:
            logger.warning(
                "RepoMapper: capping file scan from %d to %d files",
                len(code_files), MAX_FILES,
            )
            code_files = code_files[:MAX_FILES]

        output_parts: list[str] = []
        total_chars = 0

        for node in code_files:
            if total_chars >= MAX_OUTPUT_CHARS:
                output_parts.append("... (output truncated — limit reached)")
                break

            try:
                content = await fetch_content(node.path)
            except Exception:
                logger.debug("RepoMapper: could not fetch %s, skipping", node.path)
                continue

            signatures = self._extract_signatures(node.path, content)
            if signatures:
                block = f"{node.path}\n" + "\n".join(f"  {s}" for s in signatures)
            else:
                block = node.path

            output_parts.append(block)
            total_chars += len(block)

        return "\n\n".join(output_parts)

    # ── Routing ───────────────────────────────────────────────────────────

    def _extract_signatures(self, path: str, content: str) -> list[str]:
        """Route to the correct extractor based on file extension."""
        ext = self._get_ext(path)
        if ext == ".py":
            return self._extract_python_signatures(content)
        if ext in (".js", ".jsx", ".ts", ".tsx"):
            return self._extract_js_ts_signatures(content)
        if ext == ".go":
            return self._extract_go_signatures(content)
        if ext == ".rs":
            return self._extract_rust_signatures(content)
        if ext == ".java":
            return self._extract_java_signatures(content)
        return []

    # ── Python (ast) ──────────────────────────────────────────────────────

    def _extract_python_signatures(self, content: str) -> list[str]:
        """Extract class and function signatures from Python source."""
        try:
            tree = ast.parse(content)
        except SyntaxError as exc:
            logger.warning("RepoMapper: SyntaxError parsing Python file: %s", exc)
            return []

        sigs: list[str] = []
        self._walk_python_node(tree, sigs, indent=0)
        return sigs

    def _walk_python_node(
        self,
        node: ast.AST,
        sigs: list[str],
        indent: int,
    ) -> None:
        """Recursively walk AST nodes collecting signatures only."""
        prefix = "  " * indent

        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                # Class with bases
                bases = ", ".join(self._format_base(b) for b in child.bases)
                base_str = f"({bases})" if bases else ""
                sigs.append(f"{prefix}class {child.name}{base_str}:")
                self._walk_python_node(child, sigs, indent + 1)

            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                prefix_kw = "async " if isinstance(child, ast.AsyncFunctionDef) else ""
                args_str = self._format_args(child.args)
                ret = ""
                if child.returns:
                    try:
                        ret = f" -> {ast.unparse(child.returns)}"
                    except Exception:
                        ret = ""
                sigs.append(f"{prefix}{prefix_kw}def {child.name}({args_str}){ret}")

    @staticmethod
    def _format_base(node: ast.expr) -> str:
        """Format a base class node to string."""
        try:
            return ast.unparse(node)
        except Exception:
            return "?"

    @staticmethod
    def _format_args(args: ast.arguments) -> str:
        """Format function arguments to a concise signature string."""
        parts: list[str] = []
        # positional args
        for arg in args.args:
            ann = ""
            if arg.annotation:
                with contextlib.suppress(Exception):
                    ann = f": {ast.unparse(arg.annotation)}"
            parts.append(f"{arg.arg}{ann}")
        # *args
        if args.vararg:
            parts.append(f"*{args.vararg.arg}")
        # keyword-only
        for arg in args.kwonlyargs:
            parts.append(f"{arg.arg}")
        # **kwargs
        if args.kwarg:
            parts.append(f"**{args.kwarg.arg}")
        return ", ".join(parts)

    # ── JavaScript / TypeScript (regex) ───────────────────────────────────

    _JS_PATTERNS = [
        # class declarations
        re.compile(
            r"^\s*(?:export\s+)?(?:default\s+)?(?:abstract\s+)?class\s+(\w+)"
            r"(?:\s+extends\s+\w+)?(?:\s+implements\s+[\w,\s]+)?\s*\{",
            re.MULTILINE,
        ),
        # function declarations
        re.compile(
            r"^\s*(?:export\s+)?(?:async\s+)?function\s*\*?\s*(\w+)\s*\([^)]*\)",
            re.MULTILINE,
        ),
        # arrow / const functions
        re.compile(
            r"^\s*(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s+)?"
            r"(?:\([^)]*\)|[a-zA-Z_]\w*)\s*=>",
            re.MULTILINE,
        ),
        # class methods
        re.compile(
            r"^\s+(?:static\s+)?(?:async\s+)?(\w+)\s*\([^)]*\)\s*(?::\s*\w+)?\s*\{",
            re.MULTILINE,
        ),
    ]

    def _extract_js_ts_signatures(self, content: str) -> list[str]:
        """Extract signatures from JavaScript/TypeScript source."""
        sigs: list[str] = []
        seen: set[str] = set()

        for pattern in self._JS_PATTERNS:
            for match in pattern.finditer(content):
                line = match.group(0).strip().rstrip("{").strip()
                if line not in seen:
                    seen.add(line)
                    sigs.append(line)

        return sigs

    # ── Go (regex) ────────────────────────────────────────────────────────

    _GO_PATTERNS = [
        # func with receiver: func (r *Repo) Method(...)
        re.compile(
            r"^func\s+\([^)]+\)\s+\w+\s*\([^)]*\)(?:\s*\([^)]*\)|\s*\w+)?",
            re.MULTILINE,
        ),
        # standalone func: func Name(...)
        re.compile(
            r"^func\s+\w+\s*\([^)]*\)(?:\s*\([^)]*\)|\s*\w+)?",
            re.MULTILINE,
        ),
        # type struct/interface
        re.compile(r"^type\s+\w+\s+(?:struct|interface)\s*\{", re.MULTILINE),
    ]

    def _extract_go_signatures(self, content: str) -> list[str]:
        """Extract signatures from Go source."""
        sigs: list[str] = []
        for pattern in self._GO_PATTERNS:
            for match in pattern.finditer(content):
                line = match.group(0).strip().rstrip("{").strip()
                sigs.append(line)
        return sigs

    # ── Rust (regex) ──────────────────────────────────────────────────────

    _RUST_PATTERNS = [
        # pub fn / fn
        re.compile(
            r"^\s*(?:pub(?:\([^)]*\))?\s+)?(?:async\s+)?fn\s+\w+(?:<[^>]*>)?\s*\([^)]*\)"
            r"(?:\s*->\s*[^\{]+)?",
            re.MULTILINE,
        ),
        # impl / struct / enum / trait
        re.compile(
            r"^\s*(?:pub(?:\([^)]*\))?\s+)?(?:impl|struct|enum|trait)\s+\w+(?:<[^>]*>)?",
            re.MULTILINE,
        ),
    ]

    def _extract_rust_signatures(self, content: str) -> list[str]:
        """Extract signatures from Rust source."""
        sigs: list[str] = []
        for pattern in self._RUST_PATTERNS:
            for match in pattern.finditer(content):
                line = match.group(0).strip().rstrip("{").strip()
                sigs.append(line)
        return sigs

    # ── Java (regex) ─────────────────────────────────────────────────────

    _JAVA_PATTERNS = [
        # class / interface
        re.compile(
            r"^\s*(?:public|private|protected)?\s*(?:abstract\s+)?(?:class|interface|enum)\s+\w+"
            r"(?:\s+extends\s+\w+)?(?:\s+implements\s+[\w,\s]+)?\s*\{",
            re.MULTILINE,
        ),
        # methods
        re.compile(
            r"^\s+(?:public|private|protected)\s+(?:static\s+)?(?:final\s+)?"
            r"(?:\w+(?:<[^>]*>)?)\s+(\w+)\s*\([^)]*\)",
            re.MULTILINE,
        ),
    ]

    def _extract_java_signatures(self, content: str) -> list[str]:
        """Extract signatures from Java source."""
        sigs: list[str] = []
        for pattern in self._JAVA_PATTERNS:
            for match in pattern.finditer(content):
                line = match.group(0).strip().rstrip("{").strip()
                sigs.append(line)
        return sigs

    # ── Utilities ─────────────────────────────────────────────────────────

    @staticmethod
    def _is_code_file(path: str) -> bool:
        """Check if a file path is a code file worth mapping."""
        ext = RepoMapper._get_ext(path)
        if ext in SKIP_EXTENSIONS:
            return False
        return ext in CODE_EXTENSIONS

    @staticmethod
    def _get_ext(path: str) -> str:
        """Get lowercase file extension including the dot."""
        dot_idx = path.rfind(".")
        if dot_idx == -1:
            return ""
        return path[dot_idx:].lower()

    # ── Synchronous skeleton (in-memory) ─────────────────────────────────

    def generate_repo_skeleton(self, file_contents: dict[str, str]) -> str:
        """Build a text-based skeleton from an already-fetched {path: content} dict.

        Synchronous counterpart to ``generate_map`` — reuses the same
        ``_extract_signatures`` and ``_is_code_file`` helpers but works
        directly against an in-memory mapping rather than async fetch calls.

        Args:
            file_contents: Mapping of file path → raw source code.

        Returns:
            Formatted skeleton string (same layout as ``generate_map``).
        """
        output_parts: list[str] = []
        total_chars = 0
        file_count = 0

        for path, content in file_contents.items():
            if file_count >= MAX_FILES:
                output_parts.append("... (output truncated — file limit reached)")
                break
            if total_chars >= MAX_OUTPUT_CHARS:
                output_parts.append("... (output truncated — char limit reached)")
                break
            if not self._is_code_file(path):
                continue

            signatures = self._extract_signatures(path, content)
            if signatures:
                block = f"{path}\n" + "\n".join(f"  {s}" for s in signatures)
            else:
                block = path

            output_parts.append(block)
            total_chars += len(block)
            file_count += 1

        logger.debug(
            "RepoMapper.generate_repo_skeleton: %d files, %d chars",
            file_count, total_chars,
        )
        return "\n\n".join(output_parts)

    # ── Dependency tracing ────────────────────────────────────────────────

    def resolve_file_dependencies(
        self,
        target_path: str,
        all_file_contents: dict[str, str],
    ) -> dict[str, list[str]]:
        """Identify files imported by target and files that import target.

        Args:
            target_path: Repo-relative path of the file being patched.
            all_file_contents: Full {path: content} map of fetched files.

        Returns:
            Dict with two keys:
            - ``"imports"``: paths of files that target_path imports (its deps).
            - ``"callers"``: paths of files that import target_path (its dependents).
            Each list is deduplicated and capped at 5 entries.
        """
        imports: list[str] = []
        callers: list[str] = []

        target_content = all_file_contents.get(target_path, "")
        target_ext = self._get_ext(target_path)

        # ── Step 1: what does target_path import? ──────────────────────────
        if target_ext == ".py":
            imported_modules = self._extract_python_imports(target_content)
        else:
            imported_modules = self._extract_js_ts_imports(target_content)

        for mod in imported_modules:
            resolved = self._resolve_module_to_path(mod, target_path, all_file_contents)
            if resolved and resolved not in imports:
                imports.append(resolved)
            if len(imports) >= 5:
                break

        # ── Step 2: what imports target_path? ──────────────────────────────
        target_module_variants = self._path_to_module_variants(target_path)
        for path, content in all_file_contents.items():
            if path == target_path:
                continue
            if self._file_imports_module(content, target_module_variants, self._get_ext(path)):
                if path not in callers:
                    callers.append(path)
            if len(callers) >= 5:
                break

        logger.debug(
            "resolve_file_dependencies(%s): imports=%s callers=%s",
            target_path, imports, callers,
        )
        return {"imports": imports, "callers": callers}

    # ── Import extraction ─────────────────────────────────────────────────

    _PY_IMPORT_REGEX = re.compile(
        r"^\s*(?:from\s+([\w.]+)\s+import|import\s+([\w.,\s]+))",
        re.MULTILINE,
    )
    _JS_IMPORT_REGEX = re.compile(
        r"""(?:import\s+.*?from\s+['"]([^'"]+)['"]|require\s*\(\s*['"]([^'"]+)['"]\s*\))""",
        re.MULTILINE,
    )

    def _extract_python_imports(self, content: str) -> list[str]:
        """Extract dotted module names from Python import statements via AST."""
        modules: list[str] = []
        try:
            tree = ast.parse(content)
        except SyntaxError:
            # Regex fallback for truncated / partial content
            for match in self._PY_IMPORT_REGEX.finditer(content):
                mod = match.group(1) or ""
                if not mod:
                    for part in (match.group(2) or "").split(","):
                        m = part.strip().split()[0] if part.strip() else ""
                        if m:
                            modules.append(m)
                else:
                    modules.append(mod)
            return modules

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    modules.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    # node.level > 0 means relative import (from . import …)
                    # We still record the module name; relative resolution
                    # happens in _resolve_module_to_path.
                    modules.append(node.module)
        return modules

    def _extract_js_ts_imports(self, content: str) -> list[str]:
        """Extract local specifiers from JS/TS import / require statements."""
        modules: list[str] = []
        for match in self._JS_IMPORT_REGEX.finditer(content):
            spec = match.group(1) or match.group(2) or ""
            # Only consider local (relative or absolute-from-root) imports
            if spec and (spec.startswith(".") or spec.startswith("/")):
                modules.append(spec)
        return modules

    # ── Module → path resolution ──────────────────────────────────────────

    def _resolve_module_to_path(
        self,
        module: str,
        referencing_file: str,
        all_file_contents: dict[str, str],
    ) -> str | None:
        """Map a dotted Python module name or JS path specifier to a repo file.

        Python: ``farm_agent.core.config`` → ``farm_agent/core/config.py``
                also tries ``farm_agent/core/__init__.py`` for package imports.

        JS/TS: relative specifiers are resolved relative to referencing_file.
        """
        candidates: list[str] = []

        if module.startswith(".") or module.startswith("/"):
            # JS/TS relative import
            ref_dir = "/".join(referencing_file.split("/")[:-1])
            raw = (ref_dir + "/" + module) if ref_dir else module
            parts = raw.split("/")
            resolved_parts: list[str] = []
            for part in parts:
                if part == "..":
                    if resolved_parts:
                        resolved_parts.pop()
                elif part and part != ".":
                    resolved_parts.append(part)
            base = "/".join(resolved_parts)
            candidates = [
                base,
                f"{base}.ts",
                f"{base}.tsx",
                f"{base}.js",
                f"{base}.jsx",
                f"{base}/index.ts",
                f"{base}/index.js",
            ]
        else:
            # Python dotted module
            slash_path = module.replace(".", "/")
            candidates = [
                f"{slash_path}.py",
                f"{slash_path}/__init__.py",
            ]

        for candidate in candidates:
            if candidate in all_file_contents:
                return candidate
        return None

    def _path_to_module_variants(self, path: str) -> list[str]:
        """Return all plausible module-name forms for a file path.

        e.g. ``farm_agent/core/config.py``
        → ``["farm_agent.core.config", "farm_agent/core/config", "config",
              "./config", "/farm_agent/core/config"]``
        """
        no_ext = path
        for ext in (".py", ".ts", ".tsx", ".js", ".jsx"):
            if no_ext.endswith(ext):
                no_ext = no_ext[: -len(ext)]
                break
        if no_ext.endswith("/__init__"):
            no_ext = no_ext[: -len("/__init__")]

        dotted = no_ext.replace("/", ".")
        slash = no_ext
        basename = no_ext.split("/")[-1]
        return [dotted, slash, basename, f"./{basename}", f"/{slash}"]

    def _file_imports_module(
        self,
        content: str,
        module_variants: list[str],
        ext: str,
    ) -> bool:
        """Return True if content imports any of the given module variant names."""
        if ext == ".py":
            try:
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            if any(
                                alias.name == mv or alias.name.startswith(mv + ".")
                                for mv in module_variants
                            ):
                                return True
                    elif isinstance(node, ast.ImportFrom):
                        if node.module and any(
                            node.module == mv or node.module.startswith(mv + ".")
                            for mv in module_variants
                        ):
                            return True
            except SyntaxError:
                pass

        # Regex fallback — covers JS/TS and failed Python parse
        for mv in module_variants:
            if re.search(rf"""["'`]{re.escape(mv)}["'`]""", content):
                return True
        return False
