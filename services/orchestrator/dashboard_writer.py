"""Read/write dashboard.json — pipeline status and statistics."""

import json
import os
import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger("orchestrator")

DATA_DIR = os.environ.get("DATA_DIR", "/data")

DEFAULT_DASHBOARD = {
    "affiliate_code": "OFR0296",
    "jobs": {
        "researcher": {"last_run": None, "status": "unknown", "next_run": None, "last_error": None, "codes_found": 0},
        "validator": {"last_run": None, "status": "unknown", "next_run": None, "last_error": None, "codes_validated": 0},
        "poster": {"last_run": None, "status": "unknown", "next_run": None, "last_error": None, "posts_today": 0},
    },
    "stats": {
        "total_active_codes": 0,
        "total_expired_codes": 0,
        "total_posts_this_week": 0,
        "last_deploy": None,
    },
}


def load_dashboard(path: str | None = None) -> dict:
    path = path or os.path.join(DATA_DIR, "dashboard.json")
    if not os.path.exists(path):
        return DEFAULT_DASHBOARD.copy()
    with open(path) as f:
        return json.load(f)


def write_dashboard(data: dict, path: str | None = None) -> None:
    path = path or os.path.join(DATA_DIR, "dashboard.json")
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp_path = path + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(data, f, indent=2, default=str)
    os.replace(tmp_path, path)


async def update_dashboard(service_name: str, result: dict) -> None:
    """Update dashboard.json with a service run result."""
    path = os.path.join(DATA_DIR, "dashboard.json")
    dashboard = load_dashboard(path)
    now = datetime.now(timezone.utc).isoformat()

    if service_name == "_hourly":
        # Only recalculate stats; don't update last_deploy timestamp
        # so we avoid a git diff (and push) every hour when nothing changed
        old_json = json.dumps(dashboard.get("stats", {}), sort_keys=True)
        _update_stats(dashboard, path)
        new_json = json.dumps(dashboard.get("stats", {}), sort_keys=True)
        if old_json == new_json:
            logger.info("Dashboard stats unchanged, skipping write")
            return
        dashboard["stats"]["last_deploy"] = now
        write_dashboard(dashboard, path)
        return

    if service_name not in dashboard["jobs"]:
        dashboard["jobs"][service_name] = {}

    job = dashboard["jobs"][service_name]
    job["last_run"] = now
    job["status"] = result.get("status", "unknown")

    if result.get("status") == "failure":
        job["last_error"] = result.get("error", "Unknown error")
    else:
        job["last_error"] = None

    summary = result.get("summary", {})
    if service_name == "researcher":
        job["codes_found"] = summary.get("codes_found", 0)
    elif service_name == "validator":
        job["codes_validated"] = summary.get("codes_validated", 0)
    elif service_name == "poster":
        job["posts_today"] = summary.get("posts_created", 0)

    _update_stats(dashboard, path)
    dashboard["stats"]["last_deploy"] = now
    write_dashboard(dashboard, path)
    logger.info("Dashboard updated for %s: %s", service_name, result.get("status"))


def _update_stats(dashboard: dict, dashboard_path: str) -> None:
    """Recalculate stats from coupons.json and posts.json."""
    data_dir = os.path.dirname(dashboard_path) or DATA_DIR

    coupons_path = os.path.join(data_dir, "coupons.json")
    if os.path.exists(coupons_path):
        with open(coupons_path) as f:
            coupons = json.load(f)
        dashboard["stats"]["total_active_codes"] = sum(1 for c in coupons if c.get("status") == "valid")
        dashboard["stats"]["total_expired_codes"] = sum(1 for c in coupons if c.get("status") == "expired")

    posts_path = os.path.join(data_dir, "posts.json")
    if os.path.exists(posts_path):
        with open(posts_path) as f:
            posts = json.load(f)
        now = datetime.now(timezone.utc)
        today_str = now.strftime("%Y-%m-%d")
        week_start = (now - timedelta(days=now.weekday())).strftime("%Y-%m-%d")
        week_posts = [p for p in posts if p.get("posted_at", "")[:10] >= week_start]
        today_posts = [p for p in posts if p.get("posted_at", "")[:10] == today_str]
        dashboard["stats"]["total_posts_this_week"] = len(week_posts)
