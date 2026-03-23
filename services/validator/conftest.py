# conftest.py
# Provide a stub for playwright_stealth so tests can import main.py on
# Python versions (3.14+) where pkg_resources is no longer available.
import sys
from unittest.mock import AsyncMock, MagicMock

if "playwright_stealth" not in sys.modules:
    mock_stealth = MagicMock()
    mock_stealth.stealth_async = AsyncMock()
    sys.modules["playwright_stealth"] = mock_stealth
