"""Custom exception hierarchy for Farm-Agent."""


class FarmAgentError(Exception):
    """Base exception for all Farm-Agent errors."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.details = details or {}


class ConfigError(FarmAgentError):
    """Configuration loading or validation error."""


class GitHubAPIError(FarmAgentError):
    """GitHub API request failure."""

    def __init__(self, message: str, status_code: int | None = None, **kwargs):
        super().__init__(message, **kwargs)
        self.status_code = status_code


class RateLimitError(GitHubAPIError):
    """GitHub API rate limit exceeded."""

    def __init__(self, reset_at: int | None = None, **kwargs):
        super().__init__("GitHub API rate limit exceeded", **kwargs)
        self.reset_at = reset_at


class LLMError(FarmAgentError):
    """LLM provider error."""


class LLMRateLimitError(LLMError):
    """LLM rate limit exceeded."""


class AnalysisError(FarmAgentError):
    """Code analysis failure."""


class ContributionError(FarmAgentError):
    """Contribution generation failure."""


class GenerationError(FarmAgentError):
    """LLM generation output is invalid or unsafe (includes Gag Order violations)."""


class ContextMissingError(FarmAgentError):
    """RAG/context lookup returned no usable context for a target file.

    Raised when ChromaDB returns zero relevant chunks and the agent must
    NOT proceed with blind code generation.
    """


class PRCreationError(FarmAgentError):
    """Pull request creation failure."""
