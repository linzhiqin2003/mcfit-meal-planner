"""一餐的结构（汉堡 + 小食 + 饮料）、健康配餐与「多样」（几套方案用不同的汉堡）。"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from mcdstrip.catalog import Builder, Item, load_fixture  # noqa: E402
from mcdstrip.cli import _burger_signature, load_core  # noqa: E402
from mcdstrip.meal import burgers_of, healthy, parse_meal, role, role_vec  # noqa: E402
from mcdstrip.nutrition import Nutrition  # noqa: E402
from mcdstrip.render import TRAIN_RULES  # noqa: E402
from mcdstrip.solver import Constraints, Option, is_minimal, solve  # noqa: E402

DINNER = ROOT / "data/fixtures/stores/1450441/2026-10-16T1900"


def opt(name, price, kcal, protein, *items):
    its = tuple(Item(n, "整份吃", Nutrition(kcal=k, protein=p)) for n, k, p in items)
    return Option(id=name, label=name, price_cents=price, tonight=Nutrition(kcal=kcal, protein=protein), items=its)


class RoleTest(unittest.TestCase):
    def test_roles(self):
        for n in ["双层吉士汉堡", "汉堡包", "巨无霸", "板烧鸡腿堡", "麦香鱼", "麦香鸡", "酥酥多笋卷", "Hold不住鸡排堡"]:
            self.assertEqual(role(n), "burger", n)
        for n in ["无糖可口可乐中杯", "锡兰红茶", "纯牛奶(盒装)", "牛奶", "麦咖啡™美式", "纯悦", "100% 苹果汁(盒装)", "可乐麦炫酷"]:
            self.assertEqual(role(n), "drink", n)
        for n in ["苹果片一袋(60g)", "小杯玉米杯", "中薯条", "麦乐鸡5块", "那么大鸡排（椒盐风味）", "麦麦脆汁鸡-琵琶腿", "菠萝派"]:
            self.assertEqual(role(n), "side", n)
        self.assertEqual(role("海绵宝宝×航海王系列玩具"), "other")

    def test_healthy(self):
        for n in ["苹果片", "小杯玉米杯", "无糖可口可乐中杯", "锡兰红茶", "纯牛奶", "牛奶", "麦咖啡™热美式中杯", "纯悦",
                  "双层吉士汉堡", "巨无霸", "板烧鸡腿堡", "培根蔬萃双层牛堡", "汉堡包"]:
            self.assertTrue(healthy(n), n)
        for n in ["中薯条", "麦乐鸡5块", "可乐中杯", "浓浓抹茶牛奶", "菠萝派", "麦辣鸡腿汉堡", "麦香鸡", "麦香鱼"]:
            self.assertFalse(healthy(n), n)

    def test_parse_meal(self):
        self.assertEqual(parse_meal("汉堡+小食+饮料"), (("burger", 1), ("drink", 1), ("side", 1)))
        with self.assertRaises(ValueError):
            parse_meal("汉堡+甜品")


class MealSolveTest(unittest.TestCase):
    """小例子：结构必须恰好凑齐；0 蛋白的饮料是结构所需，不算多余。"""
    BURGER = opt("双吉", 2300, 429, 27, ("双层吉士汉堡", 429, 27))
    APPLE = opt("苹果片", 700, 33, 0, ("苹果片", 33, 0))
    COKE = opt("无糖可乐", 900, 0, 0, ("无糖可口可乐中杯", 0, 0))
    PAIR = opt("随心配", 1490, 429, 27, ("双层吉士汉堡", 429, 27), ("无糖可口可乐中杯", 0, 0))
    TWO = opt("两个汉堡", 3000, 600, 30, ("汉堡包", 300, 15), ("汉堡包", 300, 15))

    def test_exact_structure(self):
        c = Constraints(kcal_max=500, meal=parse_meal("汉堡+小食+饮料"))
        plans = solve([self.BURGER, self.APPLE, self.COKE, self.PAIR, self.TWO], c, top_k=5)
        self.assertTrue(plans)
        for p in plans:
            self.assertEqual(role_vec([it.name for o in p.options for it in o.items]), (1, 1, 1))
        # 随心配（汉堡 + 可乐）¥14.9 + 苹果片 ¥7 = ¥21.9，比三样单点（¥41）便宜，排第一
        self.assertEqual(plans[0].price_cents, 2190)

    def test_drink_not_redundant(self):
        c = Constraints(kcal_max=500, protein_min=20, meal=parse_meal("汉堡+小食+饮料"))
        self.assertTrue(is_minimal((self.BURGER, self.APPLE, self.COKE), c))
        # 没有结构要求时，0 蛋白的饮料和苹果片是多余的
        self.assertFalse(is_minimal((self.BURGER, self.APPLE, self.COKE), Constraints(kcal_max=500, protein_min=20)))

    def test_without_meal_unchanged(self):
        plans = solve([self.BURGER, self.APPLE, self.COKE, self.PAIR], Constraints(kcal_max=500, protein_min=20), top_k=1)
        self.assertEqual(plans[0].price_cents, 1490)     # 不要求结构时只点随心配就够


class MergedTipTest(unittest.TestCase):
    """两个同款汉堡、一个整份吃一个只吃馅 → 训练卡写成「两份馅夹进一份面包，另一份面包留到明早」。"""

    def test_two_double_cheeseburgers(self):
        from mcdstrip.render import merged_tips
        from mcdstrip.solver import Plan
        whole = Option(id="w", label="w", price_cents=1490, tonight=Nutrition(kcal=339, protein=21),
                       items=(Item("双层吉士汉堡", "下单去吉士", Nutrition(kcal=339, protein=21)),))
        split = Option(id="s", label="s", price_cents=1490, tonight=Nutrition(kcal=182, protein=16),
                       items=(Item("双层吉士汉堡", "下单去吉士，到手只吃馅，面包留到下一顿", Nutrition(kcal=182, protein=16)),))
        tips = merged_tips(Plan((0,), (whole, split)), "明早")
        self.assertEqual(tips, ["合并吃：两个双层吉士汉堡，今晚把两份馅夹进一份面包，另外一份面包留到明早当早餐"])
        self.assertEqual(merged_tips(Plan((0,), (whole,)), "明早"), [])


class CardTest(unittest.TestCase):
    def test_single_zero_kcal_drink_not_a_move(self):
        from mcdstrip.render import render_gym
        from mcdstrip.solver import Plan
        water = Option(id="w", label="纯悦", price_cents=500, tonight=Nutrition(),
                       items=(Item("纯悦", "整份吃", Nutrition(), single=True),))
        burger = Option(id="b", label="双吉", price_cents=2300, tonight=Nutrition(kcal=429, protein=27),
                        items=(Item("双层吉士汉堡", "整份吃", Nutrition(kcal=429, protein=27), single=True),))
        card = render_gym(Plan((0,), (water, burger)))
        self.assertNotIn("纯悦：1 个一组", card)
        self.assertIn("双层吉士汉堡：1 个一组", card)


class StoreMealTest(unittest.TestCase):
    """示例门店快照上的真实求解：500 大卡以内、蛋白质 25 克以上、汉堡 + 小食 + 饮料、健康配餐。"""

    @classmethod
    def setUpClass(cls):
        cat = load_fixture(DINNER)
        table, lib, modmap = load_core()
        b = Builder(table, lib, modmap, TRAIN_RULES)
        opts = [o for o in b.options(cat, allow_split=True, kcal_max=625) if all(healthy(it.name) for it in o.items)]
        c = Constraints(kcal_max=500, protein_min=25, meal=parse_meal("汉堡+小食+饮料"))
        cls.plans = solve(opts, c, top_k=4, distinct_key=_burger_signature)

    def test_each_plan_is_burger_side_drink(self):
        self.assertEqual(len(self.plans), 4)
        for p in self.plans:
            names = [it.name for o in p.options for it in o.items]
            self.assertEqual(role_vec(names), (1, 1, 1), names)
            self.assertTrue(all(healthy(n) for n in names), names)
            self.assertLessEqual(p.tonight.kcal, 500 + 1e-9)
            self.assertGreaterEqual(p.tonight.protein, 25 - 1e-9)

    def test_diverse_burgers(self):
        burgers = [burgers_of([it.name for o in p.options for it in o.items]) for p in self.plans]
        self.assertEqual(len(set(burgers)), len(burgers), burgers)

    def test_sorted_by_price(self):
        prices = [p.price_cents for p in self.plans]
        self.assertEqual(prices, sorted(prices))


if __name__ == "__main__":
    unittest.main()
