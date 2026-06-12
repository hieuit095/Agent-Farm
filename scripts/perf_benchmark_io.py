import asyncio
import os
import shutil
import tempfile
import time


# Mocking the FileChange structure
class MockFileChange:
    def __init__(
        self, path, new_content, original_content=None, is_new_file=False, is_deleted=False
    ):
        self.path = path
        self.new_content = str(new_content)
        self.original_content = original_content
        self.is_new_file = is_new_file
        self.is_deleted = is_deleted


async def heartbeat(interval):
    """A task that runs in the event loop to check for blockage."""
    latencies = []
    while True:
        last_time = time.time()
        try:
            await asyncio.sleep(interval)
        except asyncio.CancelledError:
            break
        now = time.time()
        # Measure how much later we woke up than requested
        latencies.append(now - last_time - interval)

    if not latencies:
        return 0, 0
    avg_latency = sum(latencies) / len(latencies)
    max_latency = max(latencies)
    return avg_latency, max_latency


def apply_patch_sync(clone_path, change):
    """Synchronous file I/O logic similar to pipeline.py."""
    file_path = os.path.normpath(os.path.join(clone_path, change.path))
    # Simulated work (including some blocking time)
    time.sleep(0.01)
    if not file_path.startswith(clone_path + os.sep) and file_path != clone_path:
        return

    try:
        if change.is_new_file:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(change.new_content)
        elif change.is_deleted:
            if os.path.exists(file_path):
                os.remove(file_path)
        else:
            if os.path.exists(file_path):
                with open(file_path, encoding="utf-8") as f:
                    content = f.read()
                if change.original_content and change.original_content in content:
                    content = content.replace(change.original_content, change.new_content, 1)
                else:
                    content = change.new_content
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)
            else:
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(change.new_content)
    except Exception as e:
        print(f"Error: {e}")


async def run_benchmark(mode="sync"):
    clone_path = tempfile.mkdtemp()
    changes = [
        MockFileChange(f"file_{i}.txt", "content " * 100, is_new_file=True) for i in range(50)
    ]

    async def run_hb():
        avg, max_l = await heartbeat(0.001)
        return avg, max_l

    hb_task = asyncio.create_task(run_hb())

    # Warm up heartbeat
    await asyncio.sleep(0.05)

    start_time = time.time()
    if mode == "sync":
        # Process changes sequentially (blocks the loop between each change)
        for change in changes:
            apply_patch_sync(clone_path, change)
            await asyncio.sleep(0)  # yield to loop
    else:
        # Optimized: processing in parallel threads
        tasks = [asyncio.to_thread(apply_patch_sync, clone_path, change) for change in changes]
        await asyncio.gather(*tasks)
    end_time = time.time()

    hb_task.cancel()
    try:
        avg_hb_latency, max_hb_latency = await hb_task
    except (asyncio.CancelledError, TypeError):
        avg_hb_latency, max_hb_latency = 0, 0

    duration = end_time - start_time
    print(f"Mode: {mode}")
    print(f"Total Duration: {duration:.4f}s")
    print(f"Heartbeat Avg Latency: {avg_hb_latency * 1000:.4f}ms")
    print(f"Heartbeat Max Latency: {max_hb_latency * 1000:.4f}ms")

    shutil.rmtree(clone_path)
    return duration


if __name__ == "__main__":
    import sys

    mode = sys.argv[1] if len(sys.argv) > 1 else "sync"
    asyncio.run(run_benchmark(mode=mode))
