import pytest
from unittest.mock import AsyncMock, patch
from git_ops import git_commit_and_push, _run_git


@pytest.mark.asyncio
async def test_run_git_success():
    with patch("git_ops.asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"success", b""))
        mock_proc.returncode = 0
        mock_exec.return_value = mock_proc

        stdout, returncode = await _run_git("status")
        assert returncode == 0
        assert "success" in stdout


@pytest.mark.asyncio
async def test_git_commit_and_push_no_changes():
    """If there are no changes, skip commit."""
    # add returns ("", 0), status returns ("", 0) → empty porcelain output → skip commit
    with patch("git_ops._run_git", new_callable=AsyncMock) as mock_git:
        mock_git.return_value = ("", 0)
        result = await git_commit_and_push("test")
        assert result is True
        calls = [call.args for call in mock_git.call_args_list]
        # Only "add" and "status" should have been called, not "commit"
        assert all(args[0] != "commit" for args in calls)
