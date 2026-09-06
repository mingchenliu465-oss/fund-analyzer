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
    def setUp(self):
        self.original_lookup = portfolio_service._get_holding_nav
        self.original_last_good = dict(portfolio_service._LAST_GOOD_NAV)
        portfolio_service._LAST_GOOD_NAV.clear()

    def tearDown(self):
        portfolio_service._get_holding_nav = self.original_lookup
        portfolio_service._LAST_GOOD_NAV.clear()
        portfolio_service._LAST_GOOD_NAV.update(self.original_last_good)

    def test_latest_nav_is_used_and_is_not_stale(self):
        portfolio_service._get_holding_nav = lambda _: 1.2345
        nav, stale = portfolio_service._getportfolio_nav_fallback("000001", 0.8)
        self.assertEqual(nav, 1.2345)
        self.assertFalse(stale)

    def test_last_known_nav_is_marked_stale(self):
        portfolio_service._LAST_GOOD_NAV["000001"] = 1.1
        portfolio_service._get_holding_nav = lambda _: None
        nav, stale = portfolio_service._getportfolio_nav_fallback("000001", 0.8)
        self.assertEqual(nav, 1.1)
        self.assertTrue(stale)

    def test_buy_nav_fallback_is_marked_stale(self):
        portfolio_service._get_holding_nav = lambda _: 0
        nav, stale = portfolio_service._getportfolio_nav_fallback("000001", 0.8)
        self.assertEqual(nav, 0.8)
        self.assertTrue(stale)

    def test_missing_nav_does_not_silently_become_zero(self):
        portfolio_service._get_holding_nav = lambda _: None
        nav, stale = portfolio_service._getportfolio_nav_fallback("000001", 0)
        self.assertIsNone(nav)
        self.assertTrue(stale)


if __name__ == "__main__":
    unittest.main()
