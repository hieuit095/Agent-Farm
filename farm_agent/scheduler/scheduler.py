"""Scheduled pipeline execution using APScheduler.

Supports cron expressions for periodic automated runs
with graceful shutdown and logging.
"""

from __future__ import annotations

import asyncio
import logging
import signal

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from farm_agent.core.config import FarmAgentConfig
from farm_agent.orchestrator.pipeline import ContribPipeline

logger = logging.getLogger(__name__)


class ContribScheduler:
    """Scheduler for automated pipeline runs."""

    def __init__(self, config: FarmAgentConfig):
        self.config = config
        self._scheduler: AsyncIOScheduler | None = None
        self._running = False

    def _parse_cron(self, cron_expr: str) -> dict:
        """Parse a cron expression into APScheduler kwargs."""
        parts = cron_expr.strip().split()
        if len(parts) != 5:
            raise ValueError(
                f"Invalid cron expression: {cron_expr!r}. "
                "Expected 5 fields: minute hour day month day_of_week"
            )
        return {
            "minute": parts[0],
            "hour": parts[1],
            "day": parts[2],
            "month": parts[3],
            "day_of_week": parts[4],
        }

    async def _run_pipeline(self):
        """Execute a single pipeline run."""
        logger.info("Scheduled pipeline run starting...")
        pipeline = ContribPipeline(self.config)
        try:
            result = await pipeline.run()
            logger.info(
                "Scheduled run complete: %d repos analyzed, %d PRs created, %d errors",
                result.repos_analyzed,
                result.prs_created,
                len(result.errors),
            )
        except Exception:
            logger.exception("Scheduled pipeline run failed")

    async def start_async(self):
        """Start the scheduler (non-blocking async)."""
        sched_config = self.config.scheduler

        if not sched_config.enabled:
            logger.warning("Scheduler is disabled in config. Set scheduler.enabled=true to enable.")
            return

        cron_kwargs = self._parse_cron(sched_config.cron)

        self._scheduler = AsyncIOScheduler(timezone=sched_config.timezone)
        self._scheduler.add_job(
            self._run_pipeline,
            trigger=CronTrigger(**cron_kwargs),
            id="farm_agent_pipeline",
            name="Farm-Agent Pipeline Run",
            replace_existing=True,
        )

        # Attach to the running event loop so scheduler integrates with existing loop
        loop = asyncio.get_running_loop()
        self._scheduler.start()
        logger.info("Scheduler started with cron: %s", sched_config.cron)
        self._running = True

        # Block forever — scheduler jobs fire in background, this keeps the method alive
        shutdown_event = asyncio.Event()
        loop.add_signal_handler(signal.SIGINT, lambda: shutdown_event.set())
        loop.add_signal_handler(signal.SIGTERM, lambda: shutdown_event.set())
        await shutdown_event.wait()

    def stop(self):
        """Stop the scheduler."""
        self._running = False
        if self._scheduler and self._scheduler.running:
            self._scheduler.shutdown()
            logger.info("Scheduler stopped.")
