"""净值最小落库：只存「基金代码 + 日期 + 累计净值」。

回测需要反复读取单只基金的完整历史累计净值，每次都现拉 akshare 既慢又受
上游抖动影响（实测同一代码会出现空错误失败、重试才成功）。这里提供一个
与持仓库（portfolio.db）完全隔离的独立 SQLite 文件，只做缓存性质的落盘：

- 只存累计净值，绝不用单位净值替代（口径纪律与 fund_service.total_return_series
  一致：除息日单位净值会被扣掉分红，用它算收益等于把分红误算成亏损）。
- 累计净值缺失的行直接丢弃，不回退、不插值、不编造。
- 路径可用环境变量 FUND_ANALYZER_NAV_DB_PATH 覆盖（与 conftest 隔离
  FUND_ANALYZER_DB_PATH 的做法同构），测试可传显式路径。
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Callable

import pandas as pd

_DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "database" / "nav_history.db"

# 落库 / 读取统一使用的列名（与 fund_service 的净值帧保持一致）
DATE_COL = "净值日期"
CUM_COL = "累计净值"


def default_db_path() -> Path:
    return Path(os.environ.get("FUND_ANALYZER_NAV_DB_PATH", str(_DEFAULT_DB_PATH)))


def _connect(db_path: Path | None) -> sqlite3.Connection:
    path = Path(db_path) if db_path is not None else default_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS nav_history (
            code TEXT NOT NULL,
            date TEXT NOT NULL,
            cumulative_nav REAL NOT NULL,
            PRIMARY KEY (code, date)
        )
        """
    )
    return conn


def _normalize(frame: pd.DataFrame) -> pd.DataFrame:
    """把任意来源的净值帧收敛为 [净值日期(datetime), 累计净值(float)]，按日升序。

    累计净值缺失/非数值的行直接丢弃；同一天多行保留最后一行（与
    fund_service._fetch_nav_history 的 drop_duplicates(keep="last") 一致）。
    """
    if frame is None:
        return pd.DataFrame(columns=[DATE_COL, CUM_COL])
    if DATE_COL not in frame.columns or CUM_COL not in frame.columns:
        raise ValueError(f"净值帧必须包含 {DATE_COL} 与 {CUM_COL} 两列")
    if frame.empty:
        return pd.DataFrame(columns=[DATE_COL, CUM_COL])
    out = pd.DataFrame(
        {
            DATE_COL: pd.to_datetime(frame[DATE_COL], errors="coerce"),
            CUM_COL: pd.to_numeric(frame[CUM_COL], errors="coerce"),
        }
    )
    out = out.dropna(subset=[DATE_COL, CUM_COL])
    out = out.drop_duplicates(subset=[DATE_COL], keep="last")
    return out.sort_values(DATE_COL).reset_index(drop=True)


def save_nav(code: str, frame: pd.DataFrame, db_path: Path | None = None) -> int:
    """把净值帧中的累计净值落库（按 code+date 覆盖写）。返回实际写入行数。"""
    normalized = _normalize(frame)
    if normalized.empty:
        return 0
    rows = [
        (code, d.strftime("%Y-%m-%d"), float(v))
        for d, v in zip(normalized[DATE_COL], normalized[CUM_COL])
    ]
    conn = _connect(db_path)
    try:
        conn.executemany(
            "INSERT OR REPLACE INTO nav_history (code, date, cumulative_nav) VALUES (?, ?, ?)",
            rows,
        )
        conn.commit()
    finally:
        conn.close()
    return len(rows)


def load_nav(code: str, db_path: Path | None = None) -> pd.DataFrame:
    """读出某基金的全部落库累计净值，列 [净值日期, 累计净值]，按日升序。

    库中没有该代码时返回同结构的空帧，不生成任何替代数据。
    """
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT date, cumulative_nav FROM nav_history WHERE code = ? ORDER BY date ASC",
            (code,),
        ).fetchall()
    finally:
        conn.close()
    if not rows:
        return pd.DataFrame(columns=[DATE_COL, CUM_COL])
    return pd.DataFrame(
        {
            DATE_COL: pd.to_datetime([r[0] for r in rows]),
            CUM_COL: [float(r[1]) for r in rows],
        }
    )


def get_nav_history(
    code: str,
    fetcher: Callable[[str], pd.DataFrame] | None = None,
    db_path: Path | None = None,
) -> pd.DataFrame:
    """缓存优先地取得某基金的累计净值帧。

    先读落库；为空才调用 fetcher（默认 fund_service.nav_history，即项目现有
    取数路径）拉取并落库。拉取失败/为空时返回空帧——如实反映“没有数据”，
    绝不生成替代序列。
    """
    stored = load_nav(code, db_path=db_path)
    if not stored.empty:
        return stored
    if fetcher is None:
        from services import fund_service

        fetcher = fund_service.nav_history
    fetched = fetcher(code)
    if fetched is None or fetched.empty:
        return pd.DataFrame(columns=[DATE_COL, CUM_COL])
    save_nav(code, fetched, db_path=db_path)
    return load_nav(code, db_path=db_path)
