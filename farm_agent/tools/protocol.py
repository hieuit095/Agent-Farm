"""Tool protocol and registry for extensible tool support.

Inspired by DeerFlow's MCP tool ecosystem: tools follow a common protocol
and can be swapped, extended, or composed via a registry.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Protocol

logger = logging.getLogger(__name__)


@dataclass
class ToolResult:
    """Result from a tool execution."""

    success: bool
    data: Any = None
    error: str | None = None
    metadata: dict[str, Any] | None = None


class Tool(Protocol):
    """Protocol for all tools in the system."""

    @property
    def name(self) -> str:
        """Unique tool name."""
        ...

    @property
    def description(self) -> str:
        """Human-readable description."""
        ...

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute the tool with given parameters."""
        ...


class ToolRegistry:
    """Registry for managing tools.

    Supports registration, lookup, and capability checking.
    Designed for future MCP server integration.
    """

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool."""
        self._tools[tool.name] = tool
        logger.info("Registered tool: %s — %s", tool.name, tool.description)

    def get(self, name: str) -> Tool | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> list[dict[str, str]]:
        """List all registered tools."""
        return [{"name": t.name, "description": t.description} for t in self._tools.values()]

    def has(self, name: str) -> bool:
        """Check if a tool is registered."""
        return name in self._tools

    async def execute(self, name: str, **kwargs: Any) -> ToolResult:
        """Execute a tool by name."""
        tool = self._tools.get(name)
        if not tool:
            return ToolResult(success=False, error=f"Tool not found: {name}")
        try:
            return await tool.execute(**kwargs)
        except Exception as e:
            logger.error("Tool %s failed: %s", name, e)
            return ToolResult(success=False, error=str(e))


# ── Built-in Tool Wrappers ────────────────────────────────────────────────


class GitHubTool:
    """Wraps GitHubClient as a tool."""

    # File extensions that should never be fetched (binary, lock, config)
    BLOCKED_EXTENSIONS = frozenset({
        ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".webp",
        ".woff", ".woff2", ".eot", ".ttf", ".otf",
        ".zip", ".tar", ".gz", ".bz2", ".7z",
        ".exe", ".dll", ".so", ".dylib",
        ".pyc", ".pyo", ".class",
        ".lock", ".min.js", ".min.css", ".map",
    })

    # Maximum file size to fetch (100KB)
    MAX_FILE_SIZE = 100_000

    def __init__(self, client: Any, *, owner: str = "", repo: str = ""):
        self._client = client
        self._owner = owner
        self._repo = repo

    @property
    def name(self) -> str:
        return "github"

    @property
    def description(self) -> str:
        return "GitHub API: repos, files, PRs, issues, reviews"

    async def execute(self, **kwargs: Any) -> ToolResult:
        action = kwargs.get("action", "")
        try:
            if action == "get_file":
                content = await self._client.get_file_content(
                    kwargs["owner"], kwargs["repo"], kwargs["path"]
                )
                return ToolResult(success=True, data=content)
            elif action == "read_file":
                return await self.read_file(kwargs.get("filepath", ""))
            elif action == "create_pr":
                result = await self._client.create_pull_request(
                    kwargs["owner"],
                    kwargs["repo"],
                    kwargs["title"],
                    kwargs["body"],
                    kwargs["head"],
                    kwargs.get("base"),
                )
                return ToolResult(success=True, data=result)
            elif action == "get_user":
                user = await self._client.get_authenticated_user()
                return ToolResult(success=True, data=user)
            else:
                return ToolResult(success=False, error=f"Unknown action: {action}")
        except Exception as e:
            return ToolResult(success=False, error=str(e))

    async def read_file(self, filepath: str) -> ToolResult:
        """Fetch the full raw content of a file from the repository.

        Guards:
        - Blocks binary / lock / minified files by extension.
        - Returns a clear error message if the file is not found (404).
        - Caps content at ``MAX_FILE_SIZE`` characters.
        """
        if not filepath or not filepath.strip():
            return ToolResult(
                success=False,
                error="Error: No file path provided. Please specify a file path.",
            )

        # Extension guard
        ext = ""
        dot_idx = filepath.rfind(".")
        if dot_idx != -1:
            ext = filepath[dot_idx:].lower()
        if ext in self.BLOCKED_EXTENSIONS:
            return ToolResult(
                success=False,
                error=f"Error: Cannot fetch '{filepath}' — binary or non-code file.",
            )

        try:
            content = await self._client.get_file_content(
                self._owner, self._repo, filepath,
            )

            # Size guard
            if len(content) > self.MAX_FILE_SIZE:
                content = (
                    content[: self.MAX_FILE_SIZE]
                    + "\n... [truncated — file exceeds 100KB]"
                )

            return ToolResult(success=True, data=content)

        except Exception as exc:
            error_msg = str(exc).lower()
            if "404" in error_msg or "not found" in error_msg:
                return ToolResult(
                    success=False,
                    error=(
                        f"Error: File '{filepath}' not found in the repository. "
                        "Please check the Project Map and try again."
                    ),
                )
            return ToolResult(success=False, error=f"Error fetching '{filepath}': {exc}")


# JSON Schema for LLM function calling (provider-agnostic)
READ_FILE_TOOL_SCHEMA = {
    "name": "read_file",
    "description": (
        "Fetch the full raw content of a file from the repository. "
        "Use this ONLY when you see a relevant utility or class in the "
        "Project Map but need to see its exact implementation to write "
        "your code. Do NOT use this for binary files, lock files, or "
        "files larger than 100KB."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "filepath": {
                "type": "string",
                "description": (
                    "The relative file path in the repository "
                    "(e.g. 'src/utils/helpers.py')."
                ),
            },
        },
        "required": ["filepath"],
    },
}


class LLMTool:
    """Wraps LLMProvider as a tool."""

    def __init__(self, provider: Any):
        self._provider = provider

    @property
    def name(self) -> str:
        return "llm"

    @property
    def description(self) -> str:
        return "LLM completion: analyze, generate, classify text"

    async def execute(self, **kwargs: Any) -> ToolResult:
        try:
            prompt = kwargs.get("prompt", "")
            system = kwargs.get("system")
            response = await self._provider.complete(prompt, system_prompt=system)
            return ToolResult(success=True, data=response)
        except Exception as e:
            return ToolResult(success=False, error=str(e))


def create_default_tools(
    github_client: Any = None,
    llm_provider: Any = None,
    *,
    owner: str = "",
    repo: str = "",
) -> ToolRegistry:
    """Create a tool registry with default tools."""
    registry = ToolRegistry()
    if github_client:
        registry.register(GitHubTool(github_client, owner=owner, repo=repo))
    if llm_provider:
        registry.register(LLMTool(llm_provider))
    return registry
