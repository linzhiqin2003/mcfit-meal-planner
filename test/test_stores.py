import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from mcdstrip.stores import Period, parse_periods, parse_stores  # noqa: E402

FIX = ROOT / "data/fixtures/store_search/上海-人民广场.json"


class StoresTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stores = parse_stores(json.loads(FIX.read_text()))

    def test_parse_periods_with_split_ranges(self):
        ps = parse_periods("宵夜(00:00至04:45,22:14至23:59)，早餐(05:14至10:15)，午餐(10:44至14:15)")
        self.assertEqual(ps, (Period("宵夜", "00:00", "04:45"), Period("早餐", "05:14", "10:15"),
                              Period("午餐", "10:44", "14:15"), Period("宵夜", "22:14", "23:59")))
        self.assertEqual(parse_periods(""), ())

    def test_sorted_by_distance(self):
        self.assertEqual(self.stores[0].code, "1450713")
        self.assertEqual([s.distance_m for s in self.stores], sorted(s.distance_m for s in self.stores))

    def test_period_and_gap(self):
        s = next(s for s in self.stores if s.code == "1450441")
        self.assertEqual(s.period_at("2026-10-16", "07:30").name, "早餐")
        self.assertIsNone(s.period_at("2026-10-16", "10:30"))           # 早餐与午餐之间的空档
        self.assertEqual(s.next_orderable("2026-10-16", "10:30"), ("2026-10-16", "10:44", Period("午餐", "10:44", "14:15")))
        self.assertEqual(s.next_orderable("2026-10-16", "12:00")[:2], ("2026-10-16", "12:00"))

    def test_next_day_after_close(self):
        s = next(s for s in self.stores if s.code == "1450441")
        d, t, p = s.next_orderable("2026-10-15", "23:30")
        self.assertEqual((d, t, p.name), ("2026-10-16", "06:44", "早餐"))


if __name__ == "__main__":
    unittest.main()
