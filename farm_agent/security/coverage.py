"""Coverage is explicit; missing or blocked work never becomes a clean verdict."""

from dataclasses import dataclass
from enum import StrEnum


class CoverageOutcome(StrEnum):
    NOT_TESTED = "not_tested"
    TESTED = "tested"
    BLOCKED = "blocked"
    INCONCLUSIVE = "inconclusive"


@dataclass(frozen=True)
class CoverageSummary:
    scan_id: str
    total: int
    tested: int
    not_tested: int
    blocked: int
    inconclusive: int

    @property
    def complete(self) -> bool:
        return self.total > 0 and self.tested == self.total

    @property
    def statement(self) -> str:
        if self.complete:
            return "Completed scoped coverage; findings require separate proof review."
        return (
            f"Coverage incomplete: {self.not_tested} not tested, "
            f"{self.blocked} blocked, {self.inconclusive} inconclusive."
        )
