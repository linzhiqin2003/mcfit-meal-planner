"""输出层：训练清单、加练建议、方案去重、核价展示。"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from mcdstrip.nutrition import Nutrition  # noqa: E402
from mcdstrip.pricing import PriceCheck  # noqa: E402
from mcdstrip.render import distinct, plan_signature, render_gym, render_plain  # noqa: E402
from mcdstrip.solver import Item, Option, Plan  # noqa: E402

N = Nutrition


def combo(oid, price, *items, leftover=N()):
    tonight = N()
    for it in items:
        tonight = tonight + it.tonight
    return Option(oid, f"套餐：{' + '.join(it.name for it in items)}", price, tonight, leftover,
                  payload=("combo", oid, ()), items=items)


def single(oid, name, price, n, how="整份吃", tags=frozenset()):
    return Option(oid, f"{name}（{how}）", price, n, payload=("single", oid, (), how != "整份吃"), tags=tags,
                  items=(Item(name, how, n, single=True),))


NUGGETS = Item("麦乐鸡5块", "整份吃", N(kcal=213, protein=12))
COKE = Item("无糖可口可乐中杯", "整份吃", N(kcal=0, carb=1, sodium=35))
TEA = Item("锡兰红茶", "整份吃", N(kcal=2, calcium=5))
SOY = Item("优品豆浆小杯", "整份吃", N(kcal=90, protein=6))


class TrainListTest(unittest.TestCase):
    def test_protein_drinks_listed_light_drinks_hidden(self):
        # 套餐里的豆浆有 6 克蛋白，不列出来用户照清单点就不够蛋白；无糖可乐不列
        p = Plan((0,), (combo("a", 1500, NUGGETS, SOY), combo("b", 1500, NUGGETS, COKE)))
        card = render_gym(p)
        self.assertIn("优品豆浆小杯", card.split("怎么下单")[0])
        self.assertNotIn("无糖可口可乐", card.split("怎么下单")[0])

    def test_water_in_combo_hidden(self):
        # 套餐里的矿泉水（纯悦）名字不像饮料，但近零热量，也不该算成一组训练动作
        water = Item("纯悦", "整份吃", N())
        card = render_gym(Plan((0,), (combo("c", 1400, NUGGETS, water),)))
        self.assertNotIn("纯悦：", card)

    def test_alias_names_merge_into_sets(self):
        # 单点「麦乐鸡」与套餐里的「麦乐鸡5块」是同一样，合成「共 2 组」
        p = Plan((0,), (single("s", "麦乐鸡", 1300, N(kcal=213, protein=12)), combo("c", 1400, NUGGETS, COKE)))
        card = render_gym(p)
        self.assertIn("麦乐鸡5块：5 块一组，共 2 组", card)
        self.assertNotIn("麦乐鸡：", card)

    def test_order_lines_present(self):
        p = Plan((0,), (combo("c", 1400, NUGGETS, COKE),))
        self.assertIn("怎么下单：", render_gym(p))
        self.assertIn("1 × 套餐：麦乐鸡5块 + 无糖可口可乐中杯", render_gym(p))

    def test_bonus_shows_name_without_whole_eat_note(self):
        p = Plan((0,), (combo("c", 1400, NUGGETS, COKE),))
        bonus = single("b", "麦辣鸡腿汉堡", 2000, N(kcal=485, protein=24), tags=frozenset({"练腿"}))
        card = render_gym(p, bonus)
        self.assertIn("再加一个🍔麦辣鸡腿汉堡上上强度", card)
        self.assertNotIn("整份吃", card)

    def test_no_body_parts_in_card(self):
        # 卡片不再讲训练部位（练腿、练胸……），鸡肉类用鸡腿图标、汉堡用汉堡图标
        p = Plan((0,), (single("s", "麦麦脆汁鸡-琵琶腿", 1300, N(kcal=230, protein=20)), combo("c", 1400, NUGGETS, COKE)))
        bonus = single("b", "麦辣鸡腿汉堡", 2000, N(kcal=485, protein=24), tags=frozenset({"练腿"}))
        card = render_gym(p, bonus)
        self.assertNotRegex(card, r"练腿|练胸|练背|练手臂|🦵|💪|🏋|🦾")
        self.assertIn("🍗麦麦脆汁鸡-琵琶腿：1 个一组", card)


class SignatureTest(unittest.TestCase):
    def test_zero_cal_drinks_are_interchangeable(self):
        a = Plan((0,), (combo("a", 1400, NUGGETS, COKE),))
        b = Plan((1,), (combo("b", 1400, NUGGETS, TEA),))
        self.assertEqual(plan_signature(a), plan_signature(b))
        self.assertEqual(len(distinct([a, b], k=3)), 1)

    def test_drinks_with_calories_are_not(self):
        a = Plan((0,), (combo("a", 1400, NUGGETS, COKE),))
        b = Plan((1,), (combo("b", 1400, NUGGETS, SOY),))
        self.assertNotEqual(plan_signature(a), plan_signature(b))

    def test_sauce_on_saved_bun_merges(self):
        # 只吃馅时去不去面包上的酱只影响下一顿：这一顿相同就是同一种方案
        filling = N(kcal=180, protein=16, carb=2, fat=13)
        a = Plan((0,), (combo("a", 1400, Item("麦香鸡", "到手只吃馅，面包留到下一顿", filling), COKE, leftover=N(kcal=210)),))
        b = Plan((1,), (combo("b", 1400, Item("麦香鸡", "下单去麦香鸡酱，到手只吃馅，面包留到下一顿", filling), COKE,
                              leftover=N(kcal=140)),))
        self.assertEqual(plan_signature(a), plan_signature(b))


class PriceTextTest(unittest.TestCase):
    def setUp(self):
        self.p = Plan((0,), (combo("c", 2980, NUGGETS, COKE),))

    def test_match(self):
        self.assertIn("价格：¥29.8（已核价）", render_plain(self.p, PriceCheck(2980, 2980, 200, "ok")))

    def test_mismatch_shows_actual(self):
        text = render_plain(self.p, PriceCheck(2980, 3980, 200, "ok"))
        self.assertIn("¥39.8", text)
        self.assertIn("以核价为准", text)
        self.assertIn("¥39.8", render_gym(self.p, price_checked=PriceCheck(2980, 3980, 200, "ok")))

    def test_failed_check(self):
        self.assertIn("核价失败", render_plain(self.p, PriceCheck(2980, None, 600057, "停业")))

    def test_unchecked(self):
        self.assertIn("价格：¥29.8\n", render_plain(self.p) + "\n")


if __name__ == "__main__":
    unittest.main()
