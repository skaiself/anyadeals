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

# All regions split into 3 batches for spread-out validation
ALL_REGIONS = ["us", "kr", "jp", "de", "gb", "au", "sa", "ca", "cn", "rs", "hr",
               "it", "fr", "at", "nl", "se", "ch", "ie", "tw", "in", "hk"]


class PipelineScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.researcher = ServiceClient(RESEARCHER_URL, timeout=600)
        self.validator = ServiceClient(VALIDATOR_URL, timeout=7200)
        self.poster = ServiceClient(POSTER_URL, timeout=300)

    def setup(self):
        """Register all scheduled jobs."""
        # Research pipeline (scraping only, no validation): 2x/day random
        self._schedule_next_research_run()

        # Validation: 1x/day, random time, random region batch
        self._schedule_next_validation_run()

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

    def _random_time_in_window(self, window_start: datetime, window_end: datetime) -> datetime:
        """Pick a random time within a window."""
        window_seconds = int((window_end - window_start).total_seconds())
        offset = random.randint(0, max(window_seconds, 1))
        return window_start + timedelta(seconds=offset)

    def _next_window(self, start_hour: int, end_hour: int) -> tuple[datetime, datetime]:
        """Return (start, end) for the next occurrence of a time window.

        If we're inside the window, clamp start to now (only future times).
        If the window has passed, move to tomorrow.
        """
        now = datetime.now(timezone.utc)
        start = now.replace(hour=start_hour, minute=0, second=0, microsecond=0)
        end = now.replace(hour=end_hour, minute=0, second=0, microsecond=0)
        if end <= now:
            start += timedelta(days=1)
            end += timedelta(days=1)
        elif start < now:
            # Inside the window — only pick future times
            start = now + timedelta(minutes=1)
        return start, end

    def _schedule_next_research_run(self):
        """Schedule next research scrape: random time in 01:00-02:00 UTC."""
        start, end = self._next_window(1, 2)
        run_time = self._random_time_in_window(start, end)

        try:
            self.scheduler.remove_job("research_run")
        except Exception:
            pass

        self.scheduler.add_job(
            self.run_research_only,
            DateTrigger(run_date=run_time),
            id="research_run",
            name=f"Research (random: {run_time.strftime('%H:%M UTC')})",
        )
        logger.info("Next research run scheduled for %s UTC", run_time.strftime("%Y-%m-%d %H:%M"))

    def _schedule_next_validation_run(self):
        """Schedule next validation: random time in 04:00-07:00 UTC, all regions.

        All 21 regions tested each night. The browser validator adds random
        30-120s delays between regions to avoid bot detection.
        """
        start, end = self._next_window(4, 7)
        run_time = self._random_time_in_window(start, end)

        # Shuffle region order (US always first for the filter phase)
        non_us = [r for r in ALL_REGIONS if r != "us"]
        random.shuffle(non_us)
        all_regions = ["us"] + non_us

        try:
            self.scheduler.remove_job("validation_run")
        except Exception:
            pass

        self.scheduler.add_job(
            self.run_validation,
            DateTrigger(run_date=run_time),
            id="validation_run",
            name=f"Validation (all {len(all_regions)} regions, {run_time.strftime('%H:%M UTC')})",
            kwargs={"regions": all_regions},
        )
        logger.info(
            "Next validation scheduled for %s UTC with regions: %s",
            run_time.strftime("%Y-%m-%d %H:%M"),
            ",".join(all_regions),
        )

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

    async def run_research_only(self):
        """Research only: scrape new codes, no validation.

        After completion, schedules the next random research run.
        """
        logger.info("Starting research (scraping only)")
        try:
            result = await self.researcher.trigger_run()
            logger.info("Research: %s", result.get("summary", {}))
            await update_dashboard("researcher", result)
            await git_commit_and_push("Research: scrape new codes")
        except Exception as e:
            logger.error("Research failed: %s", e)
            await update_dashboard("researcher", {"status": "failure", "error": str(e)})
        finally:
            self._schedule_next_research_run()

    async def run_validation(self, regions: list[str] | None = None):
        """Validate coupons in a subset of regions.

        After completion, schedules the next random validation run.
        """
        region_str = ",".join(regions) if regions else ""
        logger.info("Starting validation (regions: %s)", region_str or "all")
        try:
            params = {"regions": region_str} if region_str else None
            result = await self.validator.trigger_run(params=params)
            logger.info("Validation: %s", result.get("summary", {}))
            await update_dashboard("validator", result)
            await git_commit_and_push(f"Validation: {region_str or 'all regions'}")
        except Exception as e:
            logger.error("Validation failed: %s", e)
            await update_dashboard("validator", {"status": "failure", "error": str(e)})
        finally:
            self._schedule_next_validation_run()

    async def run_research_pipeline(self):
        """Legacy: research + validation combined. Kept for /trigger/research."""
        logger.info("Starting research + validation pipeline")
        try:
            result = await self.researcher.trigger_run()
            logger.info("Research: %s", result.get("summary", {}))
            await update_dashboard("researcher", result)

            result = await self.validator.trigger_run()
            logger.info("Validation: %s", result.get("summary", {}))
            await update_dashboard("validator", result)

            await git_commit_and_push("Pipeline run: research + validation")
        except Exception as e:
            logger.error("Pipeline failed: %s", e)
            await update_dashboard("researcher", {"status": "failure", "error": str(e)})

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
