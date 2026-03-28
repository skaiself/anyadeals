"""APScheduler job definitions for the coupon pipeline."""

import asyncio
import logging
import httpx
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

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
        self.validator = ServiceClient(VALIDATOR_URL, timeout=600)
        self.poster = ServiceClient(POSTER_URL, timeout=300)

    def setup(self):
        """Register all scheduled jobs."""
        # Research pipeline: twice daily at 6:00 and 18:00
        self.scheduler.add_job(
            self.run_research_pipeline,
            CronTrigger(hour="6,18", minute=0),
            id="research_pipeline",
            name="Research + Validate + Deploy",
        )

        # Daily re-validation of existing codes at 12:00
        self.scheduler.add_job(
            self.run_validation_only,
            CronTrigger(hour=12, minute=0),
            id="daily_revalidation",
            name="Daily Re-validation",
        )

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
        """Chained: research -> validate -> git push."""
        logger.info("Starting research pipeline")
        try:
            result = await self.researcher.trigger_run()
            logger.info("Research: %s", result.get("summary", {}))
            await update_dashboard("researcher", result)

            result = await self.validator.trigger_run()
            logger.info("Validation: %s", result.get("summary", {}))
            await update_dashboard("validator", result)

            # Step 2: Browser-based validation for region-specific testing
            try:
                browser_result = await self.validator.trigger_run(
                    endpoint="/browser-validate", params={"regions": "us,de"}
                )
                logger.info("Browser validation: %s", browser_result.get("summary", {}))
            except Exception as e:
                logger.warning("Browser validation skipped: %s", e)

            await git_commit_and_push("Pipeline run: research + validation")

        except Exception as e:
            logger.error("Research pipeline failed: %s", e)
            await update_dashboard("researcher", {"status": "failure", "error": str(e)})

    async def run_validation_only(self):
        """Re-validate existing codes."""
        logger.info("Starting daily re-validation")
        try:
            result = await self.validator.trigger_run()
            await update_dashboard("validator", result)
            await git_commit_and_push("Daily re-validation")
        except Exception as e:
            logger.error("Re-validation failed: %s", e)

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
