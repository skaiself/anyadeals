"""Git operations for the orchestrator — add, commit, push with retry."""

import asyncio
import logging
import os

logger = logging.getLogger("orchestrator")

REPO_DIR = os.environ.get("REPO_DIR", "/repo")
MAX_RETRIES = 3
RETRY_DELAY = 30  # seconds


async def _run_git(*args: str) -> tuple[str, int]:
    """Run a git command in the repo directory."""
    cmd = ["git", "-C", REPO_DIR, *args]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    output = stdout.decode("utf-8", errors="replace").strip()
    if proc.returncode != 0:
        error = stderr.decode("utf-8", errors="replace").strip()
        logger.warning("git %s failed (exit %d): %s", args[0], proc.returncode, error)
        output = error or output
    return output, proc.returncode


async def git_commit_and_push(message: str) -> bool:
    """Stage data files, commit, and push. Returns True on success."""

    # Stage data files
    await _run_git("add", "site/src/data/")

    # Check for changes
    status, _ = await _run_git("status", "--porcelain", "site/src/data/")
    if not status.strip():
        logger.info("No data changes to commit")
        return True

    # Commit
    full_message = f"chore(pipeline): {message}"
    _, rc = await _run_git("commit", "-m", full_message)
    if rc != 0:
        logger.error("git commit failed")
        return False

    # Push with retry
    for attempt in range(1, MAX_RETRIES + 1):
        _, rc = await _run_git("push")
        if rc == 0:
            logger.info("git push succeeded (attempt %d)", attempt)
            return True
        if attempt < MAX_RETRIES:
            logger.warning("git push failed, retrying in %ds (attempt %d/%d)", RETRY_DELAY, attempt, MAX_RETRIES)
            await asyncio.sleep(RETRY_DELAY)

    logger.error("git push failed after %d attempts", MAX_RETRIES)
    return False
