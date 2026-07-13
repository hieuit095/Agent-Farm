"""Smart task-to-model router.

Routes tasks to the optimal model. In the Minimax-only ecosystem,
this always returns MiniMax M2.7.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from farm_agent.llm.models import (
    DEEPSEEK_V4_FLASH,
    DEEPSEEK_V4_PRO,
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
        default_model: str = "deepseek/deepseek-v4-flash",
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
        """Route a task to the best model based on type, complexity, and strategy."""
        from farm_agent.llm.models import ModelTier, get_models_for_task

        light_tasks = {TaskType.QUICK_FIX, TaskType.DOCS, TaskType.BULK}
        heavy_tasks = {TaskType.ANALYSIS, TaskType.CODE_GEN, TaskType.PLANNING}

        if task_type in light_tasks and complexity <= 3 and self._strategy != CostStrategy.PERFORMANCE:  # noqa: E501
            model = DEEPSEEK_V4_FLASH
            reason = f"Light task ({task_type.value}, complexity={complexity}) routed to default."
        elif task_type in heavy_tasks and complexity >= 7:
            model = DEEPSEEK_V4_PRO
            reason = f"Heavy task ({task_type.value}, complexity={complexity}) routed to flagship model."  # noqa: E501
        elif token_estimate > 100_000:
            model = DEEPSEEK_V4_PRO
            reason = f"Large context ({token_estimate} tokens) routed to flagship model."
        else:
            best = get_models_for_task(task_type)
            model = best[0] if best else DEEPSEEK_V4_FLASH
            reason = f"Task ({task_type.value}) routed by best-fit score."

        if self._strategy == CostStrategy.ECONOMY and model.tier == ModelTier.PRO:
            candidates = get_models_for_task(task_type)
            economy_pick = [c for c in candidates if c.tier == ModelTier.FLASH]
            if economy_pick:
                model = economy_pick[0]
                reason = f"Economy strategy downgraded to {model.name}."

        self._task_count[model.name] = self._task_count.get(model.name, 0) + 1

        return RoutingDecision(
            model=model,
            task_type=task_type,
            reason=reason,
            fallback=DEEPSEEK_V4_FLASH,
        )

    def get_default_assignments(self) -> dict[str, str]:
        """Get default model assignment for each task type."""
        return {
            TaskType.ANALYSIS: DEEPSEEK_V4_FLASH.name,
            TaskType.CODE_GEN: DEEPSEEK_V4_FLASH.name,
            TaskType.REVIEW: DEEPSEEK_V4_FLASH.name,
            TaskType.PLANNING: DEEPSEEK_V4_FLASH.name,
            TaskType.DOCS: DEEPSEEK_V4_FLASH.name,
            TaskType.QUICK_FIX: DEEPSEEK_V4_FLASH.name,
            TaskType.BULK: DEEPSEEK_V4_FLASH.name,
            TaskType.MULTIMODAL: DEEPSEEK_V4_FLASH.name,
        }

    @property
    def stats(self) -> dict:
        """Get routing statistics."""
        return {
            "strategy": self._strategy,
            "tasks_routed": self._task_count,
            "total_tasks": sum(self._task_count.values()),
        }
