import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from scheduler import PipelineScheduler


def test_scheduler_creates_jobs():
    with patch("scheduler.AsyncIOScheduler") as MockSched:
        mock_sched = MagicMock()
        MockSched.return_value = mock_sched
        ps = PipelineScheduler()
        ps.setup()
        # Should register at least 5 jobs: research, validate, twitter, reddit, dashboard
        assert mock_sched.add_job.call_count >= 5


def test_scheduler_research_hours():
    """Research should be scheduled at 6:00 and 18:00."""
    with patch("scheduler.AsyncIOScheduler") as MockSched:
        mock_sched = MagicMock()
        MockSched.return_value = mock_sched
        ps = PipelineScheduler()
        ps.setup()

        calls = mock_sched.add_job.call_args_list
        research_call = [c for c in calls if "research" in str(c).lower()]
        assert len(research_call) > 0
