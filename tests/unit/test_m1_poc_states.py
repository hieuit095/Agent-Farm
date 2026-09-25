"""Infrastructure and evaluator errors stay distinct from a negative PoC."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from farm_agent.core.models import ContributionType, Finding, Severity
from farm_agent.generator.poc import PoCGenerator
from farm_agent.security.state import PoCStatus


@pytest.fixture
def generator():
    llm = MagicMock()
    llm.complete = AsyncMock(return_value='{"is_triggered": true, "reason": "assertion"}')
    return PoCGenerator(llm)


@pytest.fixture
def finding():
    return Finding(
        type=ContributionType.SECURITY_FIX, severity=Severity.HIGH,
        title="IDOR", description="cross tenant read", file_path="app.py",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("output", "expected"),
    [
        ({"timed_out": True, "exit_code": 1}, PoCStatus.EXECUTION_ERROR),
        ({"timed_out": False, "exit_code": None}, PoCStatus.EXECUTION_ERROR),
        ({"timed_out": False, "exit_code": 1,
          "stderr": "ModuleNotFoundError: no module"}, PoCStatus.EXECUTION_ERROR),
        ({"timed_out": False, "exit_code": 0}, PoCStatus.INCONCLUSIVE),
    ],
)
async def test_poc_does_not_confirm_infrastructure_or_contradictory_output(
    generator, finding, output, expected,
):
    verdict = await generator.evaluate_poc_result(finding, "poc", output)
    assert verdict.status == expected
