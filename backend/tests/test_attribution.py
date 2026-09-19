from types import SimpleNamespace
from unittest.mock import patch

import pytest

from services import portfolio_service as service
from services import review_service


def holding(code="000001", shares=100, fund_type="股票型"):
    return SimpleNamespace(fund_code=code, fund_name=code, shares=shares,
                           fund_type=fund_type, current_nav=2, buy_nav=1)


def calculate(holdings, quotes):
    with patch.object(service, "list_holdings", return_value=holdings), \
         patch.object(service.fund_service, "_load_fund_list", return_value=[]), \
         patch.object(service, "_open_fund_nav_change", side_effect=lambda code: quotes[code]), \
         patch.object(service, "_etf_nav_change", side_effect=lambda code: quotes[code]):
        return service.attribution()


def test_empty_portfolio():
    result = calculate([], {})
    assert result["today_return"] == 0
    assert result["top_gainer"] is None
    assert result["top_loser"] is None


def test_group_lots_and_reconcile_contributions():
    result = calculate([holding(shares=1), holding(shares=2)], {"000001": (1.004, 1, .4)})
    assert len(result["contributions"]) == 1
    assert result["contributions"][0]["shares"] == 3
    assert result["today_return"] == .01
    assert result["today_return"] == sum(c["contribution"] for c in result["contributions"])
    assert result["top_loser"] is None


def test_largest_loss_matches_summary():
    result = calculate([holding("000001"), holding("000002")],
                       {"000001": (1.9, 2, -5), "000002": (1.5, 2, -25)})
    assert result["top_gainer"] is None
    assert result["top_loser"]["fund_code"] == "000002"
    assert result["summary"]["top_loser_name"] == "000002"
    assert result["today_return"] == -60
    assert result["today_return_pct"] == -15


@pytest.mark.parametrize("code", ["000001", "510300"])
@pytest.mark.parametrize("quote", [(0, 0, 0), (float("nan"), 2, 0), (2, -1, 0)])
def test_missing_quote_is_reported_unavailable_not_as_a_stale_value(code, quote):
    """Unusable quotes must not be valued at all.

    The holding has current_nav=2, so a fallback would produce a plausible
    looking 200. That is exactly the failure mode this asserts against: no
    total_assets, no 0% return, and an explicit 'unavailable' status.
    """
    result = calculate([holding(code)], {code: quote})
    assert result["summary"]["total_assets"] is None
    assert result["summary"]["today_return"] is None
    assert result["summary"]["today_return_pct"] is None
    assert result["summary"]["status"] == "unavailable"
    assert result["summary"]["has_stale_nav"] is True
    assert result["today_return"] is None
    assert result["today_return_pct"] is None
    assert result["yesterday_value"] is None
    # A holding with no usable quote contributes nothing rather than a zero row.
    assert result["contributions"] == []


def test_review_weights_use_assets_even_when_returns_negative():
    attribution = calculate([holding()], {"000001": (1.9, 2, -5)})
    with patch.object(service, "attribution", return_value=attribution), \
         patch.object(review_service, "_load_recent_snapshots", return_value=[]):
        result = review_service.generate_daily_review("rules")
    assert any("权益类占比约 100%" in s["text"] for s in result["segments"])
