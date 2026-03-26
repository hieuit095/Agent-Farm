import asyncio
import time
from pathlib import Path
import pytest
from contribai.orchestrator.memory import Memory

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

    # Quota should still be OK
    assert await memory.check_minimax_quota() is True

    # Insert 1 more request to hit 950
    await memory.log_api_request("minimax")
    
    # Quota should now be exhausted (False means exhausted)
    assert await memory.check_minimax_quota() is False

    # Clean up
    await memory.close()

@pytest.mark.asyncio
async def test_minimax_quota_7_day(tmp_path: Path):
    db_path = tmp_path / "memory.db"
    memory = Memory(db_path)
    await memory.init()

    now = time.time()
    
    # Insert 9499 requests within the 7 day window
    # We can use executemany forスピード
    timestamps = [(now - 86400 * 2, "minimax") for _ in range(9499)]
    await memory._db.executemany(
        "INSERT INTO api_usage_log (timestamp, provider) VALUES (?, ?)",
        timestamps
    )
    await memory._db.commit()

    # Quota should still be OK
    assert await memory.check_minimax_quota() is True

    # Add 1 more
    await memory.log_api_request("minimax")
    
    # Quota should now be exhausted
    assert await memory.check_minimax_quota() is False

    await memory.close()
