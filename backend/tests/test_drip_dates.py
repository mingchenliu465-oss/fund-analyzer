import unittest
import sys
import types

from pydantic import ValidationError

from models.portfolio import DripCreate

# Date generation is pure, but its service module also owns optional market-data
# integrations. Stub the unavailable integration for this isolated unit test.
sys.modules.setdefault("akshare", types.ModuleType("akshare"))
from services import portfolio_service
from services.portfolio_service import _generate_drip_dates


class DripDateGenerationTests(unittest.TestCase):
    def test_monday_across_weeks_from_midweek_start(self):
        self.assertEqual(
            _generate_drip_dates("2026-08-05", "2026-08-18", "weekly", 1),
            ["2026-08-10", "2026-08-17"],
        )

    def test_sunday_across_month_boundary(self):
        self.assertEqual(
            _generate_drip_dates("2026-08-29", "2026-09-14", "weekly", 7),
            ["2026-08-30", "2026-09-06", "2026-09-13"],
        )

    def test_inclusive_boundary_when_start_and_end_are_target_day(self):
        self.assertEqual(
            _generate_drip_dates("2026-08-31", "2026-09-07", "weekly", 1),
            ["2026-08-31", "2026-09-07"],
        )

    def test_range_without_target_weekday_is_empty(self):
        self.assertEqual(
            _generate_drip_dates("2026-08-03", "2026-08-04", "weekly", 7),
            [],
        )

    def test_weekly_rejects_values_outside_one_to_seven(self):
        with self.assertRaises(ValidationError):
            DripCreate(
                fund_code="000001",
                fund_name="测试基金",
                amount=100,
                frequency="weekly",
                start_date="2026-08-01",
                end_date="2026-08-31",
                day_of_week=8,
            )

    def test_rejects_reversed_date_range(self):
        with self.assertRaises(ValidationError):
            DripCreate(
                fund_code="000001",
                fund_name="测试基金",
                amount=100,
                frequency="weekly",
                start_date="2026-09-01",
                end_date="2026-08-31",
                day_of_week=1,
            )


class NavFallbackTests(unittest.TestCase):
    """Locks the post-audit rule: a missing or expired quote must stay missing.

    `_getportfolio_nav_fallback` is declared as `(code) -> (nav, nav_date, stale)`
    and only treats a NAV as "current" when the trading calendar says it is fresh.
    It must never substitute the purchase price, a last-known value, or 0.
    """

    def setUp(self):
        self.original_lookup = portfolio_service._get_holding_nav
        self.original_is_current = portfolio_service.fund_service.is_current_nav

    def tearDown(self):
        portfolio_service._get_holding_nav = self.original_lookup
        portfolio_service.fund_service.is_current_nav = self.original_is_current

    def test_latest_nav_is_used_and_is_not_stale(self):
        portfolio_service._get_holding_nav = lambda _: (1.2345, "2026-09-18")
        portfolio_service.fund_service.is_current_nav = lambda *_: True
        nav, nav_date, stale = portfolio_service._getportfolio_nav_fallback("000001")
        self.assertEqual(nav, 1.2345)
        self.assertEqual(nav_date, "2026-09-18")
        self.assertFalse(stale)

    def test_buy_nav_is_never_returned_as_valuation(self):
        """A real buy price must NOT be substituted when the quote is missing."""
        portfolio_service._get_holding_nav = lambda _: None
        nav, nav_date, stale = portfolio_service._getportfolio_nav_fallback("000001")
        self.assertIsNone(nav)
        self.assertNotEqual(nav, 0.8)
        self.assertIsNone(nav_date)
        self.assertTrue(stale)

    def test_expired_nav_is_not_used_as_current_but_keeps_its_observation_date(self):
        """数据过期时不得当作当前净值，但观测日要保留下来说明"最后已知是哪天"。"""
        portfolio_service._get_holding_nav = lambda _: (1.1111, "2020-12-31")
        portfolio_service.fund_service.is_current_nav = lambda *_: False
        nav, nav_date, stale = portfolio_service._getportfolio_nav_fallback("000001")
        self.assertIsNone(nav)
        self.assertEqual(nav_date, "2020-12-31")
        self.assertTrue(stale)

    def test_non_positive_quote_is_treated_as_missing_not_as_zero(self):
        """0 / negative quotes are unusable, and must not surface as a real 0."""
        for bad_quote in (0, 0.0, -1.0):
            with self.subTest(quote=bad_quote):
                portfolio_service._get_holding_nav = lambda _, q=bad_quote: (q, "2026-09-18")
                nav, _nav_date, stale = portfolio_service._getportfolio_nav_fallback("000001")
                self.assertIsNone(nav)
                self.assertTrue(stale)

    def test_missing_nav_does_not_silently_become_zero(self):
        portfolio_service._get_holding_nav = lambda _: None
        nav, _nav_date, stale = portfolio_service._getportfolio_nav_fallback("000001")
        self.assertIsNone(nav)
        self.assertTrue(stale)


if __name__ == "__main__":
    unittest.main()
