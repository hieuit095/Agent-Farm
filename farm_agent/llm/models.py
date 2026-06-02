"""Model registry with capabilities, costs, and context windows.

Catalogs available Gemini models and their strengths for
intelligent task-to-model routing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import StrEnum

logger = logging.getLogger(__name__)


class TaskType(StrEnum):
    """Types of tasks that models can be assigned to."""

    ANALYSIS = "analysis"  # Security, code quality analysis
    CODE_GEN = "code_gen"  # Code generation / fixes
    REVIEW = "review"  # Self-review, PR review
    DOCS = "docs"  # Documentation improvements
    QUICK_FIX = "quick_fix"  # Simple, targeted fixes
    BULK = "bulk"  # High-volume, low-complexity
    PLANNING = "planning"  # Architecture, strategy
    MULTIMODAL = "multimodal"  # Image/UI analysis


class ModelTier(StrEnum):
    """Model performance tiers."""

    PRO = "pro"  # Highest capability, highest cost
    FLASH = "flash"  # Good capability, balanced cost
    LITE = "lite"  # Basic capability, lowest cost


@dataclass
class ModelSpec:
    """Specification of a model's capabilities and costs."""

    name: str  # e.g. "gemini-3.1-pro-preview"
    display_name: str  # e.g. "Gemini 3.1 Pro"
    tier: ModelTier = ModelTier.FLASH
    context_window: int = 1_000_000  # tokens
    max_output: int = 65_536

    # Cost per 1M tokens (approximate, USD)
    input_cost: float = 0.0
    output_cost: float = 0.0

    # Capability scores (0-100)
    coding: int = 70
    analysis: int = 70
    reasoning: int = 70
    speed: int = 70
    multimodal: int = 50

    # Best-fit task types
    best_for: list[TaskType] = field(default_factory=list)

    # Description
    description: str = ""

    @property
    def overall_score(self) -> float:
        return (self.coding + self.analysis + self.reasoning + self.speed) / 4.0

    @property
    def cost_efficiency(self) -> float:
        """Higher = more cost-efficient."""
        total_cost = self.input_cost + self.output_cost
        if total_cost == 0:
            return 100.0
        return self.overall_score / total_cost


# ── DeepSeek Models ────────────────────────────────────

DEEPSEEK_V32 = ModelSpec(
    name="deepseek/deepseek-v3.2",
    display_name="DeepSeek V3.2",
    tier=ModelTier.PRO,
    context_window=1000000,
    max_output=16384,
    input_cost=0.14,
    output_cost=0.28,
    coding=95,
    analysis=90,
    reasoning=92,
    speed=85,
    multimodal=0,
    best_for=[
        TaskType.CODE_GEN,
        TaskType.ANALYSIS,
        TaskType.REVIEW,
        TaskType.PLANNING,
    ],
    description="Primary Generator Model via OpenRouter",
)

DEEPSEEK_V4_FLASH = ModelSpec(
    name="deepseek/deepseek-v4-flash",
    display_name="DeepSeek V4 Flash",
    tier=ModelTier.FLASH,
    context_window=1000000,
    max_output=16384,
    input_cost=0.07,
    output_cost=0.14,
    coding=85,
    analysis=85,
    reasoning=80,
    speed=95,
    multimodal=0,
    best_for=[
        TaskType.QUICK_FIX,
        TaskType.DOCS,
        TaskType.BULK,
    ],
    description="High volume, cheap, fast model via OpenRouter",
)

DEEPSEEK_V4_PRO = ModelSpec(
    name="deepseek/deepseek-v4-pro",
    display_name="DeepSeek V4 Pro",
    tier=ModelTier.PRO,
    context_window=1000000,
    max_output=16384,
    input_cost=0.14,
    output_cost=0.28,
    coding=98,
    analysis=95,
    reasoning=96,
    speed=80,
    multimodal=0,
    best_for=[
        TaskType.CODE_GEN,
        TaskType.ANALYSIS,
        TaskType.REVIEW,
        TaskType.PLANNING,
    ],
    description="Deep reasoning, complex coding flagship model via OpenRouter",
)

# ── Filter Models (Defense-in-Depth) ──────────────────

KIMI_K2_APPRAISER = ModelSpec(
    name="moonshotai/kimi-k2.5",
    display_name="Kimi K2.5 Appraiser",
    tier=ModelTier.PRO,
    context_window=200_000,
    max_output=16_384,
    description="Layer 1 Expert Appraiser"
)

GEMINI_31_AUDITOR = ModelSpec(
    name="google/gemini-3.1-pro-preview",
    display_name="Gemini 3.1 Pro Supreme Auditor",
    tier=ModelTier.PRO,
    context_window=1_000_000,
    max_output=16_384,
    description="Layer 2 Supreme Auditor"
)

QWEN_37_MAX = ModelSpec(
    name="qwen/qwen3.7-max",
    display_name="Qwen 3.7 Max",
    tier=ModelTier.PRO,
    context_window=200_000,
    max_output=16_384,
    description="Hardcore strict QA, Adversarial Review"
)

GEMINI_35_FLASH = ModelSpec(
    name="google/gemini-3.5-flash",
    display_name="Gemini 3.5 Flash",
    tier=ModelTier.FLASH,
    context_window=1_000_000,
    max_output=16_384,
    description="Massive context, CI logs, diplomatic communication"
)


# ── Registry ──────────────────────────────────────────


ALL_MODELS: list[ModelSpec] = [
    DEEPSEEK_V32,
    DEEPSEEK_V4_FLASH,
    DEEPSEEK_V4_PRO,
    KIMI_K2_APPRAISER,
    GEMINI_31_AUDITOR,
    QWEN_37_MAX,
    GEMINI_35_FLASH,
]

MODELS_BY_NAME: dict[str, ModelSpec] = {m.name: m for m in ALL_MODELS}

MODELS_BY_TIER: dict[ModelTier, list[ModelSpec]] = {}
for _m in ALL_MODELS:
    MODELS_BY_TIER.setdefault(_m.tier, []).append(_m)


def get_model(name: str) -> ModelSpec | None:
    """Get model spec by name."""
    return MODELS_BY_NAME.get(name)


def get_models_for_task(
    task_type: TaskType,
) -> list[ModelSpec]:
    """Get models best suited for a task type, sorted by fit."""
    matching = [m for m in ALL_MODELS if task_type in m.best_for]
    # Sort by relevant capability score
    score_key = {
        TaskType.CODE_GEN: lambda m: m.coding,
        TaskType.ANALYSIS: lambda m: m.analysis,
        TaskType.REVIEW: lambda m: m.reasoning,
        TaskType.PLANNING: lambda m: m.reasoning,
        TaskType.DOCS: lambda m: m.speed,
        TaskType.QUICK_FIX: lambda m: m.speed,
        TaskType.BULK: lambda m: m.cost_efficiency,
        TaskType.MULTIMODAL: lambda m: m.multimodal,
    }
    key_fn = score_key.get(task_type, lambda m: m.overall_score)
    return sorted(matching, key=key_fn, reverse=True)


def get_cheapest_capable(
    task_type: TaskType,
    min_score: int = 70,
) -> ModelSpec | None:
    """Get the cheapest model that meets minimum capability."""
    candidates = get_models_for_task(task_type)
    capable = [m for m in candidates if m.overall_score >= min_score]
    if not capable:
        return None
    return min(
        capable,
        key=lambda m: m.input_cost + m.output_cost,
    )
