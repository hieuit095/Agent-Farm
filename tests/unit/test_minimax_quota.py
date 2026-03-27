import asyncio
import time
from pathlib import Path
import pytest
from contribai.orchestrator.memory import Memory
from contribai.core.exceptions import LLMRateLimitError

@pytest.mark.asyncio
async def test_minimax_quota_tracking(tmp_path: Path):
    db_path = tmp_path / "memory.db"
    memory = Memory(db_path)
    await memory.init()

    now = time.time()
    
    # Insert 949 requests within the 5 hour window
    for _ in range(949):
        await memory._db.execute(
            "INSERT INTO api_usage_log (timestamp, provider) VALUES (?, ?)",
            (now - 100, "minimax")
        )
    await memory._db.commit()

    # Quota should still be OK. This successful call logs the 950th.
    await memory.check_and_record_llm_quota("minimax")

    # Quota should now be exhausted
    with pytest.raises(LLMRateLimitError):
        await memory.check_and_record_llm_quota("minimax")

    # Clean up
    await memory.close()

@pytest.mark.asyncio
async def test_minimax_quota_7_day(tmp_path: Path):
    db_path = tmp_path / "memory.db"
    memory = Memory(db_path)
    await memory.init()

    now = time.time()
    
    # Insert 9499 requests within the 7 day window
    timestamps = [(now - 86400 * 2, "minimax") for _ in range(9499)]
    await memory._db.executemany(
        "INSERT INTO api_usage_log (timestamp, provider) VALUES (?, ?)",
        timestamps
    )
    await memory._db.commit()

    # Quota should still be OK. This successful call logs the 9500th.
    await memory.check_and_record_llm_quota("minimax")

    # Quota should now be exhausted
    with pytest.raises(LLMRateLimitError):
        await memory.check_and_record_llm_quota("minimax")

    await memory.close()
