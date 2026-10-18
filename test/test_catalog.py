import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from mcdstrip.catalog import Builder, load_fixture, parse_diff  # noqa: E402
from mcdstrip.library import build_library, load_priors  # noqa: E402
from mcdstrip.nutrition import parse_table  # noqa: E402
from mcdstrip.pricing import items_for, modification  # noqa: E402
from mcdstrip.solver import Constraints, Plan, solve  # noqa: E402

STORE = ROOT / "data/fixtures/stores/1450441/2026-10-16T1900"


class CatalogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tab = parse_table((ROOT / "data/fixtures/nutrition_raw.txt").read_text())
        recipes = json.loads((ROOT / "data/reference/recipes_draft.json").read_text())
        cls.lib = build_library(cls.tab, recipes, load_priors(ROOT / "data/reference/priors_us.json"))
        cls.modmap = json.loads((ROOT / "data/reference/modifier_map.json").read_text())
        cls.cat = load_fixture(STORE)
        cls.builder = Builder(cls.tab, cls.lib, cls.modmap)

    def test_parse_diff(self):
        self.assertEqual(parse_diff("+ ¥0"), 0)
        self.assertEqual(parse_diff("+ ¥1"), 100)
        self.assertEqual(parse_diff("- ¥1"), -100)
        self.assertEqual(parse_diff("+ ¥0.5"), 50)
        self.assertEqual(parse_diff(None), 0)
        with self.assertRaises(ValueError):
            parse_diff("免费")

    def test_store_code_from_fixture(self):
        self.assertEqual(self.cat.store_code, "1450441")

    def test_eat_plans_conserve_official_total(self):
        p = next(p for p in self.cat.products.values() if p.name == "双层吉士汉堡")
        plans = self.builder.eat_plans(p.name, p.modifiers, allow_split=True)
        whole = next(e for e in plans if not e.removed and not e.split)
        self.assertEqual(whole.tonight.vec(), self.tab["双层吉士汉堡"].vec())
        for e in plans:
            if e.split:
                same = next(x for x in plans if x.removed == e.removed and not x.split)
                for a, b in zip((e.tonight + e.leftover).vec(), same.tonight.vec()):
                    self.assertAlmostEqual(a, b, places=6)
        # 番茄酱、芥末酱热量太低，不生成单独的去酱吃法
        self.assertFalse(any("番茄酱" in e.removed for e in plans))
        self.assertTrue(any(e.removed == ("吉士",) for e in plans))

    def test_modification_payload_shape(self):
        p = next(p for p in self.cat.products.values() if p.name == "双层吉士汉堡")
        mod = modification(p.modifiers, ("吉士",))
        self.assertEqual(len(mod["values"]), len(p.modifiers))
        cheese = next(v for v in mod["values"] if v["code"] == "100141")
        self.assertEqual((cheese["quantity"], cheese["key"]), (0, "0-0"))
        self.assertTrue(all(v["quantity"] == 1 for v in mod["values"] if v["code"] != "100141"))
        with self.assertRaises(ValueError):
            modification(p.modifiers, ("面包",))

    def test_best_plan_payload_matches_live_verified_shape(self):
        """这个参数形状已在 2026-10-15 用算价接口实测通过（2980 分）。"""
        opts = self.builder.options(self.cat, kcal_max=400)
        best = solve(opts, Constraints(kcal_max=400, protein_min=30), top_k=1)[0]
        self.assertEqual(best.price_cents, 2980)
        items = items_for(best, self.cat)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["productCode"], "9900013304")
        self.assertEqual(items[0]["quantity"], 2)
        rl = items[0]["roundList"]
        self.assertEqual([r["round"] for r in rl], [1, 2])
        self.assertEqual(rl[0]["comboItemList"][0]["code"], "1120")
        self.assertIn("modification", rl[0]["comboItemList"][0])


    def test_with_order_items_priced_without_card(self):
        # 「随单购麦金卡优惠」的现价要连同会员卡一起买；不带卡按原价（2026-10-15 实测）
        from mcdstrip.catalog import price_cents
        item = {"currentPrice": "28", "originalPrice": "57", "discountType": "随单购麦金卡优惠", "canWithOrder": True}
        self.assertEqual(price_cents(item), 5700)
        self.assertEqual(price_cents({"currentPrice": "13.5", "originalPrice": "16", "discountType": "促销优惠"}), 1350)
        self.assertEqual(price_cents({"currentPrice": "13.5", "originalPrice": "16", "discountType": None}), 1350)

    def test_multi_quantity_rounds(self):
        # 堡堡随心拼（7件任选）：主食 2、小食 3、饮料 2，营养和核价参数都要按份数算
        p = self.cat.products["9900004066"]
        self.assertEqual([r.quantity for r in p.rounds], [2, 3, 2])
        opts = [o for o in self.builder.options(self.cat, kcal_max=3000) if o.payload[1] == "9900004066"]
        self.assertTrue(opts)
        o = min(opts, key=lambda o: o.tonight.kcal)
        self.assertEqual(len(o.items), 7)
        self.assertAlmostEqual(o.tonight.kcal, sum(it.tonight.kcal for it in o.items))
        plan = Plan((0,), (o,))
        rl = items_for(plan, self.cat)[0]["roundList"]
        self.assertEqual({r["round"]: sum(e["quantity"] for e in r["comboItemList"]) for r in rl}, {1: 2, 2: 3, 3: 2})

    def test_choice_max_quantity_respected(self):
        # BFF四宫格：3 份小食，每样最多 1 份
        p = next(p for p in self.cat.products.values() if "四宫格" in p.name)
        opts = [o for o in self.builder.options(self.cat, kcal_max=3000) if o.payload[1] == p.code]
        for o in opts:
            for rid, n in __import__("collections").Counter((x[0], x[1]) for x in o.payload[2]).items():
                ch = next(c for r in p.rounds if r.id == rid[0] for c in r.choices if c.code == rid[1])
                if ch.max_quantity > 0:
                    self.assertLessEqual(n, ch.max_quantity)

    def test_no_negative_nutrients(self):
        for o in self.builder.options(self.cat, kcal_max=800):
            self.assertTrue(all(x >= 0 for x in o.tonight.vec()), o.label)
            self.assertTrue(all(x >= 0 for x in o.leftover.vec()), o.label)

    def test_relative_fixture_path(self):
        import os
        cwd = os.getcwd()
        try:
            os.chdir(STORE)
            cat = load_fixture(Path("."))
        finally:
            os.chdir(cwd)
        self.assertEqual((cat.store_code, cat.slot), ("1450441", "2026-10-16T1900"))


class NamesTest(unittest.TestCase):
    def test_normalize_rules(self):
        from mcdstrip.nutrition import normalize
        cases = {"麦咖啡™冰美式中杯": "冰美式中杯", "5块麦乐鸡": "麦乐鸡5块", "麦乐鸡-4块": "麦乐鸡4块",
                 "麦辣鸡翅2块": "麦辣鸡翅-2块", "可口可乐（小杯）": "可乐小杯", "雪碧(小杯)": "雪碧小杯",
                 "纯牛奶": "纯牛奶（盒装）", "麦乐鸡": "麦乐鸡5块"}
        for raw, want in cases.items():
            self.assertEqual(normalize(raw), want, raw)

    def test_piece_scaling(self):
        tab = parse_table((ROOT / "data/fixtures/nutrition_raw.txt").read_text())
        b = Builder(tab, None, {})
        self.assertEqual(b.base_nutrition("麦辣鸡翅4块"), tab["麦辣鸡翅-2块"].scale(2))
        self.assertEqual(b.base_nutrition("麦乐鸡4块"), tab["麦乐鸡4块"])      # 表里有就不换算


if __name__ == "__main__":
    unittest.main()
