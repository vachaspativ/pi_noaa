"""
Wraps APScheduler AsyncIOScheduler for pi_noaa background job management.
Provides helpers for interval and cron-based jobs.
"""
import asyncio
from typing import Callable, Any
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from core.logger import get_logger

logger = get_logger(__name__)


class Scheduler:
    """
    Job orchestrator wrapping APScheduler.
    Manages periodic tasks like TLE refresh, alert polling, and mode rechecking.
    """

    def __init__(self):
        self._scheduler = AsyncIOScheduler()
        self._started = False

    def add_interval_job(
        self,
        func: Callable,
        minutes: float,
        job_id: str | None = None,
        **kwargs: Any,
    ) -> str:
        """
        Add a job that runs at a fixed interval.

        Args:
            func: Async or sync callable to run.
            minutes: Interval in minutes.
            job_id: Optional unique ID for the job.
            **kwargs: Extra arguments passed to the callable.

        Returns:
            The job ID string.
        """
        job = self._scheduler.add_job(
            func,
            trigger=IntervalTrigger(minutes=minutes),
            id=job_id,
            replace_existing=True,
            kwargs=kwargs,
        )
        logger.info(f"Scheduled interval job '{job.id}' every {minutes} min")
        return job.id

    def add_cron_job(
        self,
        func: Callable,
        cron_str: str,
        job_id: str | None = None,
        **kwargs: Any,
    ) -> str:
        """
        Add a job using a cron expression.

        Args:
            func: Async or sync callable to run.
            cron_str: Cron expression string (5 fields: min hour dom mon dow).
            job_id: Optional unique ID for the job.
            **kwargs: Extra arguments passed to the callable.

        Returns:
            The job ID string.
        """
        parts = cron_str.split()
        if len(parts) != 5:
            raise ValueError(f"Invalid cron expression (need 5 fields): '{cron_str}'")

        trigger = CronTrigger(
            minute=parts[0],
            hour=parts[1],
            day=parts[2],
            month=parts[3],
            day_of_week=parts[4],
        )
        job = self._scheduler.add_job(
            func,
            trigger=trigger,
            id=job_id,
            replace_existing=True,
            kwargs=kwargs,
        )
        logger.info(f"Scheduled cron job '{job.id}' with '{cron_str}'")
        return job.id

    def start(self) -> None:
        """Start the scheduler."""
        if not self._started:
            self._scheduler.start()
            self._started = True
            logger.info("Scheduler started")

    def shutdown(self, wait: bool = False) -> None:
        """Stop the scheduler."""
        if self._started:
            self._scheduler.shutdown(wait=wait)
            self._started = False
            logger.info("Scheduler stopped")

    @property
    def is_running(self) -> bool:
        return self._started

    def get_jobs(self) -> list:
        """Return list of all scheduled jobs."""
        return self._scheduler.get_jobs()
