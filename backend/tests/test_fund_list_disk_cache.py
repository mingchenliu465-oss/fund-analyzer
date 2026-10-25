"""基金列表落盘缓存测试。

规则：
- 拉取成功 -> 列表落盘到 backend/database/fund_list_cache.json（gitignore 覆盖）；
- 拉取失败且内存无缓存 -> 读回落盘的旧列表，列表项的 nav_date/nav_status
  等字段原样保留，不得篡改成"新数据"；
- 没有落盘文件 -> 维持原有行为（返回空列表，不编造）。
"""

import json
from unittest.mock import patch

import pandas as pd

from models.fund import FundSummary
from services import fund_service


def _sample_funds() -> list[FundSummary]:
    return [
        FundSummary(
            code="000001", name="华夏成长混合", company="华夏", type="混合型",
            nav=1.2345, nav_date="2026-09-18", nav_status="fresh",
            change_pct=0.5, one_year_return=0.1, risk_level=None, size="-", heat=None,
        )
    ]


def test_disk_cache_roundtrip_preserves_fields(tmp_path):
    path = tmp_path / "fund_list_cache.json"
    with patch.object(fund_service, "_FUND_LIST_DISK_CACHE_PATH", path):
        fund_service._write_fund_list_disk_cache(_sample_funds())
        assert path.exists()
        loaded = fund_service._read_fund_list_disk_cache()
    assert len(loaded) == 1
    assert loaded[0].code == "000001"
    assert loaded[0].nav == 1.2345
    # 日期与新鲜度必须原样保留：落盘兜底不能把旧数据伪装成新数据。
    assert loaded[0].nav_date == "2026-09-18"
    assert loaded[0].nav_status == "fresh"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["saved_at"]


def test_load_fund_list_falls_back_to_disk_cache_on_source_failure(tmp_path):
    path = tmp_path / "fund_list_cache.json"
    with patch.object(fund_service, "_FUND_LIST_DISK_CACHE_PATH", path):
        fund_service._write_fund_list_disk_cache(_sample_funds())
        with patch.dict(fund_service._CACHE, {}, clear=True), patch.object(
            fund_service.ak, "fund_name_em", side_effect=RuntimeError("offline")
        ), patch.object(
            fund_service, "_build_enrichment_lookup", side_effect=RuntimeError("offline")
        ):
            funds = fund_service._load_fund_list()
    assert [f.code for f in funds] == ["000001"]
    assert funds[0].nav_date == "2026-09-18"


def test_load_fund_list_empty_when_source_fails_and_no_disk_cache(tmp_path):
    with patch.object(
        fund_service, "_FUND_LIST_DISK_CACHE_PATH", tmp_path / "missing.json"
    ), patch.dict(fund_service._CACHE, {}, clear=True), patch.object(
        fund_service.ak, "fund_name_em", side_effect=RuntimeError("offline")
    ), patch.object(
        fund_service, "_build_enrichment_lookup", side_effect=RuntimeError("offline")
    ):
        assert fund_service._load_fund_list() == []


def test_successful_load_writes_disk_cache(tmp_path):
    path = tmp_path / "fund_list_cache.json"
    frame = pd.DataFrame({
        "基金代码": ["000001"],
        "基金简称": ["华夏成长混合"],
        "基金类型": ["混合型-偏股"],
    })
    with patch.object(fund_service, "_FUND_LIST_DISK_CACHE_PATH", path), \
            patch.dict(fund_service._CACHE, {}, clear=True), \
            patch.object(fund_service.ak, "fund_name_em", return_value=frame), \
            patch.object(fund_service, "_build_enrichment_lookup", return_value={}), \
            patch.object(fund_service, "_etf_registry", return_value={}):
        funds = fund_service._load_fund_list()
    assert [f.code for f in funds] == ["000001"]
    assert path.exists()
    with patch.object(fund_service, "_FUND_LIST_DISK_CACHE_PATH", path):
        cached = fund_service._read_fund_list_disk_cache()
    assert [f.code for f in cached] == ["000001"]
