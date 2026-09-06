"""Use an isolated database before importing any service modules."""
import os
import tempfile
from pathlib import Path

_test_db = tempfile.TemporaryDirectory(prefix="fund-analyzer-tests-")
_previous_path = os.environ.get("FUND_ANALYZER_DB_PATH")
os.environ["FUND_ANALYZER_DB_PATH"] = str(Path(_test_db.name) / "portfolio.db")


def pytest_unconfigure(config):
    if _previous_path is None:
        os.environ.pop("FUND_ANALYZER_DB_PATH", None)
    else:
        os.environ["FUND_ANALYZER_DB_PATH"] = _previous_path
    _test_db.cleanup()
