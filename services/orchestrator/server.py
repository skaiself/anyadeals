"""Orchestrator service — coordinates pipeline, manages schedules, serves dashboard."""

import json
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

logger = logging.getLogger("orchestrator")
logging.basicConfig(level=logging.INFO)

DATA_DIR = os.environ.get("DATA_DIR", "/data")


@asynccontextmanager
async def lifespan(app: FastAPI):
    from scheduler import PipelineScheduler
    app.state.scheduler = PipelineScheduler()
    app.state.scheduler.setup()
    app.state.scheduler.start()
    logger.info("Orchestrator started")
    yield
    app.state.scheduler.shutdown()
    logger.info("Orchestrator stopped")


app = FastAPI(title="Orchestrator Service", lifespan=lifespan)


@app.get("/status")
def get_status():
    return {"healthy": True, "service": "orchestrator"}


@app.get("/jobs")
def get_jobs():
    """List all scheduled jobs with next run times."""
    try:
        return app.state.scheduler.get_jobs()
    except Exception:
        return []


@app.get("/dashboard", response_class=HTMLResponse)
def get_dashboard():
    """Serve a simple HTML dashboard showing pipeline status."""
    dashboard_path = os.path.join(DATA_DIR, "dashboard.json")
    try:
        with open(dashboard_path) as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {"jobs": {}, "stats": {}}

    jobs_html = ""
    for name, info in data.get("jobs", {}).items():
        status = info.get("status", "unknown")
        color = {"success": "green", "failure": "red"}.get(status, "orange")
        last_run = info.get("last_run", "never")
        jobs_html += f'<tr><td>{name}</td><td style="color:{color}">{status}</td><td>{last_run}</td></tr>'

    stats = data.get("stats", {})
    html = f"""<!DOCTYPE html>
<html><head><title>anyadeals Pipeline Dashboard</title>
<style>
body {{ font-family: 'Public Sans', sans-serif; background: #FAF8F5; color: #0F0D0B; max-width: 800px; margin: 40px auto; padding: 0 20px; }}
h1 {{ color: #EA580C; }}
table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
th {{ background: #0F0D0B; color: #FAF8F5; }}
.stat {{ display: inline-block; background: white; padding: 20px; margin: 10px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
.stat-value {{ font-size: 2em; font-weight: bold; color: #EA580C; }}
</style></head><body>
<h1>anyadeals Pipeline</h1>
<div>
  <div class="stat"><div class="stat-value">{stats.get('total_active_codes', 0)}</div>Active Codes</div>
  <div class="stat"><div class="stat-value">{stats.get('total_posts_this_week', 0)}</div>Posts This Week</div>
  <div class="stat"><div class="stat-value">{stats.get('last_deploy', 'never')[:10]}</div>Last Deploy</div>
</div>
<h2>Pipeline Jobs</h2>
<table><tr><th>Service</th><th>Status</th><th>Last Run</th></tr>{jobs_html}</table>
<p><small>Last updated: {stats.get('last_deploy', 'unknown')}</small></p>
</body></html>"""
    return HTMLResponse(content=html)


@app.post("/trigger/{service_name}")
async def trigger_service(service_name: str):
    """Manually trigger a specific pipeline job."""
    import asyncio
    scheduler = app.state.scheduler
    if service_name == "research":
        asyncio.create_task(scheduler.run_research_pipeline())
        return {"status": "triggered", "job": "research_pipeline"}
    elif service_name == "validate":
        asyncio.create_task(scheduler.run_validation_only())
        return {"status": "triggered", "job": "validation"}
    elif service_name == "post":
        asyncio.create_task(scheduler.run_posting())
        return {"status": "triggered", "job": "posting"}
    else:
        return {"status": "error", "message": f"Unknown service: {service_name}"}
