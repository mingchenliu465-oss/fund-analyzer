from services import portfolio_service


def test_insights_explains_return_and_marks_missing_market_data(monkeypatch):
    monkeypatch.setattr(portfolio_service, "portfolio_summary", lambda: object())
    monkeypatch.setattr(
        portfolio_service,
        "attribution",
        lambda: {
            "today_return": 12.5,
            "today_return_pct": 0.42,
            "contributions": [
                {
                    "fund_code": "A",
                    "fund_name": "基金 A",
                    "fund_type": "股票型",
                    "current_value": 1000.0,
                    "change_pct": 1.2,
                    "contribution": 12.5,
                    "contribution_rate": 1.0,
                    "nav_stale": False,
                }
            ],
        },
    )
    monkeypatch.setattr(
        portfolio_service,
        "portfolio_history",
        lambda period: [
            {"date": "2026-09-11", "total_value": 990, "profit": -10},
            {"date": "2026-09-12", "total_value": 1000, "profit": 0},
        ],
    )
    monkeypatch.setattr(portfolio_service, "_build_overlap_pairs", lambda values: ("unavailable", []))
    monkeypatch.setattr(portfolio_service, "_fetch_index_return", lambda code, cutoff: None)

    result = portfolio_service.insights("1M")

    assert result["headline"]["today_return"] == 12.5
    assert result["headline"]["data_status"] == "partial"
    assert result["return_explanation"]["top_gainers"][0]["fund_code"] == "A"
    assert result["risk"]["concentration_level"] == "高"
    assert result["risk"]["overlap_status"] == "unavailable"
    assert len(result["market_comparison"]) == 4
    assert all(not item["available"] for item in result["market_comparison"])
    assert result["history"]["trend"] == "上升"


def test_history_marks_large_change_after_enough_snapshots():
    points = [
        {"date": f"2026-09-{day:02d}", "total_value": value, "profit": 0}
        for day, value in ((1, 1000), (2, 1002), (3, 1001), (4, 1003), (5, 1002), (6, 1500))
    ]

    result = portfolio_service._build_history_insight(points)

    assert result["data_sufficiency"] == "ready"
    assert result["anomaly_detected"] is True
    assert result["anomaly_date"] == "2026-09-06"
