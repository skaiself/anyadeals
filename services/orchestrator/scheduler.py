"""APScheduler job definitions for the coupon pipeline."""

import asyncio
import logging
import random
from datetime import datetime, timedelta, timezone

import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from service_client import ServiceClient
from dashboard_writer import update_dashboard
from git_ops import git_commit_and_push

logger = logging.getLogger("orchestrator")

RESEARCHER_URL = "http://researcher:8001"
VALIDATOR_URL = "http://validator:8002"
POSTER_URL = "http://poster:8003"


class PipelineScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.researcher = ServiceClient(RESEARCHER_URL, timeout=600)
        self.validator = ServiceClient(VALIDATOR_URL, timeout=7200)  # Up to 2h for full browser validation
        self.poster = ServiceClient(POSTER_URL, timeout=300)

    def setup(self):
        """Register all scheduled jobs."""
        # Research + validation pipeline: schedule first random run on startup,
        # then each run schedules the next one
        self._schedule_next_pipeline_run()

        # Twitter posting: 3x/day at 9:00, 13:00, 18:00
        self.scheduler.add_job(
            self.run_posting,
            CronTrigger(hour="9,13,18", minute=0),
            id="twitter_posting",
            name="Twitter Posting",
            kwargs={"platform": "twitter"},
        )

        # Reddit posting: 2x/week on Tuesday and Friday at 10:00
        self.scheduler.add_job(
            self.run_posting,
            CronTrigger(day_of_week="tue,fri", hour=10, minute=0),
            id="reddit_posting",
            name="Reddit Posting",
            kwargs={"platform": "reddit"},
        )

        # Dashboard update: every hour
        self.scheduler.add_job(
            self.run_dashboard_update,
            CronTrigger(minute=0),
            id="dashboard_update",
            name="Dashboard Update + Deploy",
        )

    def _schedule_next_pipeline_run(self):
        """Schedule the next pipeline run at a random time.

        Two runs per day: one in a morning window (5:00-11:00 UTC)
        and one in an evening window (15:00-21:00 UTC).
        Random times avoid bot detection patterns.
        """
        now = datetime.now(timezone.utc)
        hour = now.hour

        # Determine which window to schedule for
        if hour < 11:
            # We're in the morning — schedule for this morning window
            window_start = now.replace(hour=5, minute=0, second=0, microsecond=0)
            window_end = now.replace(hour=11, minute=0, second=0, microsecond=0)
            if now >= window_end:
                # Morning window passed, schedule evening
                window_start = now.replace(hour=15, minute=0, second=0, microsecond=0)
                window_end = now.replace(hour=21, minute=0, second=0, microsecond=0)
        elif hour < 15:
            # Between windows — schedule for evening
            window_start = now.replace(hour=15, minute=0, second=0, microsecond=0)
            window_end = now.replace(hour=21, minute=0, second=0, microsecond=0)
        elif hour < 21:
            # We're in the evening window
            window_start = now.replace(hour=15, minute=0, second=0, microsecond=0)
            window_end = now.replace(hour=21, minute=0, second=0, microsecond=0)
            if now >= window_end:
                # Evening window passed, schedule next morning
                tomorrow = now + timedelta(days=1)
                window_start = tomorrow.replace(hour=5, minute=0, second=0, microsecond=0)
                window_end = tomorrow.replace(hour=11, minute=0, second=0, microsecond=0)
        else:
            # Past 21:00 — schedule next morning
            tomorrow = now + timedelta(days=1)
            window_start = tomorrow.replace(hour=5, minute=0, second=0, microsecond=0)
            window_end = tomorrow.replace(hour=11, minute=0, second=0, microsecond=0)

        # Pick a random time within the window
        window_seconds = int((window_end - window_start).total_seconds())
        random_offset = random.randint(0, max(window_seconds, 1))
        run_time = window_start + timedelta(seconds=random_offset)

        # If the random time is in the past, bump to next window
        if run_time <= now:
            if run_time.hour < 12:
                window_start = now.replace(hour=15, minute=0, second=0, microsecond=0)
                window_end = now.replace(hour=21, minute=0, second=0, microsecond=0)
            else:
                tomorrow = now + timedelta(days=1)
                window_start = tomorrow.replace(hour=5, minute=0, second=0, microsecond=0)
                window_end = tomorrow.replace(hour=11, minute=0, second=0, microsecond=0)
            window_seconds = int((window_end - window_start).total_seconds())
            random_offset = random.randint(0, max(window_seconds, 1))
            run_time = window_start + timedelta(seconds=random_offset)

        # Remove any existing pipeline job before adding new one
        try:
            self.scheduler.remove_job("pipeline_run")
        except Exception:
            pass

        self.scheduler.add_job(
            self.run_research_pipeline,
            DateTrigger(run_date=run_time),
            id="pipeline_run",
            name=f"Pipeline (random: {run_time.strftime('%H:%M UTC')})",
        )
        logger.info("Next pipeline run scheduled for %s UTC", run_time.strftime("%Y-%m-%d %H:%M"))

    def start(self):
        self.scheduler.start()
        logger.info("Scheduler started with %d jobs", len(self.scheduler.get_jobs()))

    def shutdown(self):
        self.scheduler.shutdown()

    def get_jobs(self) -> list[dict]:
        """Return list of scheduled jobs with next run times."""
        return [
            {
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            }
            for job in self.scheduler.get_jobs()
        ]

    async def run_research_pipeline(self):
        """Chained: research -> browser validate -> git push.

        After completion, schedules the next random run.
        """
        logger.info("Starting research + browser validation pipeline")
        try:
            # Step 1: Research (discover new codes)
            result = await self.researcher.trigger_run()
            logger.info("Research: %s", result.get("summary", {}))
            await update_dashboard("researcher", result)

            # Step 2: Browser-only validation (US filter + all regions)
            result = await self.validator.trigger_run()
            logger.info("Validation: %s", result.get("summary", {}))
            await update_dashboard("validator", result)

            await git_commit_and_push("Pipeline run: research + browser validation")

        except Exception as e:
            logger.error("Research pipeline failed: %s", e)
            await update_dashboard("researcher", {"status": "failure", "error": str(e)})
        finally:
            # Always schedule the next run
            self._schedule_next_pipeline_run()

    async def run_posting(self, platform: str = "twitter"):
        """Post to social media. platform: 'twitter' or 'reddit'."""
        logger.info("Starting %s posting", platform)
        try:
            async with httpx.AsyncClient(timeout=300) as client:
                resp = await client.post(f"{POSTER_URL}/run?platform={platform}")
                result = resp.json()
            await update_dashboard("poster", result)
            await git_commit_and_push(f"{platform.capitalize()} posting")
        except Exception as e:
            logger.error("Posting failed: %s", e)

    async def run_dashboard_update(self):
        """Update dashboard.json and deploy."""
        logger.info("Updating dashboard")
        try:
            await update_dashboard("_hourly", {"status": "success"})
            await git_commit_and_push("Hourly dashboard update")
        except Exception as e:
            logger.error("Dashboard update failed: %s", e)
