"""Smart task-to-model router.

Routes tasks to the optimal model. In the Minimax-only ecosystem,
this always returns MiniMax M2.7.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from farm_agent.llm.models import (
    MINIMAX_ABAB65S_CHAT,
    MINIMAX_M27,
    ModelSpec,
    TaskType,
)

logger = logging.getLogger(__name__)


class CostStrategy:
    """Cost optimization strategies."""

    PERFORMANCE = "performance"
    BALANCED = "balanced"
    ECONOMY = "economy"


@dataclass
class RoutingDecision:
    """Result of a routing decision."""

    model: ModelSpec
    task_type: TaskType
    reason: str
    fallback: ModelSpec | None = None


class TaskRouter:
    """Routes tasks to optimal models."""

    def __init__(
        self,
        strategy: str = CostStrategy.BALANCED,
        default_model: str = "MiniMax-M2.7",
    ):
        self._strategy = strategy
        self._default = default_model
        self._task_count: dict[str, int] = {}

    def route(
        self,
        task_type: TaskType,
        *,
        complexity: int = 5,
        file_count: int = 1,
        token_estimate: int = 1000,
    ) -> RoutingDecision:
        """Route a task to the best model."""
        model = MINIMAX_M27
        self._task_count[model.name] = self._task_count.get(model.name, 0) + 1

        return RoutingDecision(
            model=model,
            task_type=task_type,
            reason="Minimax ecosystem exclusively.",
            fallback=MINIMAX_ABAB65S_CHAT,
        )

    def get_default_assignments(self) -> dict[str, str]:
        """Get default model assignment for each task type."""
        return {
            TaskType.ANALYSIS: MINIMAX_M27.name,
            TaskType.CODE_GEN: MINIMAX_M27.name,
            TaskType.REVIEW: MINIMAX_M27.name,
            TaskType.PLANNING: MINIMAX_M27.name,
            TaskType.DOCS: MINIMAX_M27.name,
            TaskType.QUICK_FIX: MINIMAX_M27.name,
            TaskType.BULK: MINIMAX_M27.name,
            TaskType.MULTIMODAL: MINIMAX_M27.name,
        }

    @property
    def stats(self) -> dict:
        """Get routing statistics."""
        return {
            "strategy": self._strategy,
            "tasks_routed": self._task_count,
            "total_tasks": sum(self._task_count.values()),
        }
