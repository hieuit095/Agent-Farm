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
CODE_EXTENSIONS = frozenset(
    {
        ".py",
        ".js",
        ".ts",
        ".jsx",
        ".tsx",
        ".go",
        ".rs",
        ".java",
        ".rb",
        ".c",
        ".cpp",
        ".h",
        ".hpp",
        ".cs",
        ".swift",
        ".kt",
    }
)

# Extensions explicitly skipped (non-code / config / docs)
SKIP_EXTENSIONS = frozenset(
    {
        ".md",
        ".txt",
        ".rst",
        ".json",
        ".yaml",
        ".yml",
        ".toml",
        ".cfg",
        ".ini",
        ".lock",
        ".csv",
        ".xml",
        ".html",
        ".css",
        ".scss",
        ".svg",
        ".png",
        ".jpg",
        ".gif",
        ".ico",
        ".woff",
        ".woff2",
        ".eot",
        ".ttf",
        ".map",
        ".min.js",
        ".min.css",
    }
)

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
            f for f in file_tree if getattr(f, "type", "") == "blob" and self._is_code_file(f.path)
        ]

        # Enforce hard file limit
        if len(code_files) > MAX_FILES:
            logger.warning(
                "RepoMapper: capping file scan from %d to %d files",
                len(code_files),
                MAX_FILES,
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
