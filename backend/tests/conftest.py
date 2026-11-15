"""Use an isolated database and pristine network globals before importing services."""
import os
import socket
import tempfile
import urllib.request
from pathlib import Path

import pytest
import requests.utils

_test_db = tempfile.TemporaryDirectory(prefix="fund-analyzer-tests-")
_previous_path = os.environ.get("FUND_ANALYZER_DB_PATH")
os.environ["FUND_ANALYZER_DB_PATH"] = str(Path(_test_db.name) / "portfolio.db")

# main.py 在 import 时会改写进程级网络全局量（清空系统代理、强制 IPv4），
# 这些补丁是给应用运行用的，测试不应继承：只要某个 import main 的测试模块
# 在收集阶段被导入（如 test_overview/test_research_pages），后续需要真实
# 网络路径的测试（交易日历）就会被迫直连并失败。conftest 先于测试模块导入，
# 在此保存原始值，并在每个测试前后恢复，避免测试顺序影响结果。
_PRISTINE_GETPROXIES = urllib.request.getproxies
_PRISTINE_REQUESTS_GETPROXIES = requests.utils.getproxies
_PRISTINE_GETADDRINFO = socket.getaddrinfo
_PRISTINE_NO_PROXY = os.environ.get("no_proxy")


def _restore_network_globals() -> None:
    urllib.request.getproxies = _PRISTINE_GETPROXIES
    # requests 在 import 时就绑定了 getproxies 引用，只还原 urllib.request
    # 不够；main 的补丁会让这份副本永久返回 {}（等同禁用代理）。
    requests.utils.getproxies = _PRISTINE_REQUESTS_GETPROXIES
    socket.getaddrinfo = _PRISTINE_GETADDRINFO
    if _PRISTINE_NO_PROXY is None:
        os.environ.pop("no_proxy", None)
    else:
        os.environ["no_proxy"] = _PRISTINE_NO_PROXY


@pytest.fixture(autouse=True)
def _isolate_main_import_side_effects():
    _restore_network_globals()
    yield
    _restore_network_globals()


def pytest_unconfigure(config):
    if _previous_path is None:
        os.environ.pop("FUND_ANALYZER_DB_PATH", None)
    else:
        os.environ["FUND_ANALYZER_DB_PATH"] = _previous_path
    _test_db.cleanup()
