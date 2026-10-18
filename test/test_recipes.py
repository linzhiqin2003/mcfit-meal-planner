"""正式配方（recipes.json）上的端到端检查：拆分可信度、估算标注、餐段用语。"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from mcdstrip.catalog import Builder, Modifier, load_fixture  # noqa: E402
from mcdstrip.library import build_library, is_reliable, load_priors, load_recipes  # noqa: E402
from mcdstrip.nutrition import NUTRIENTS, Nutrition, normalize, parse_table  # noqa: E402
from mcdstrip.render import TRAIN_RULES, distinct, meal_of, render_gym, render_plain  # noqa: E402
from mcdstrip.solver import Constraints, solve  # noqa: E402

REF = ROOT / "data/reference"
STORES = ROOT / "data/fixtures/stores/1450441"


class RecipesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tab = parse_table((ROOT / "data/fixtures/nutrition_raw.txt").read_text())
        book = load_recipes(REF / "recipes.json")
        cls.recipes, cls.exclude = book.recipes, book.fit_exclude
        cls.lib = build_library(cls.tab, cls.recipes, load_priors(REF / "priors_us.json"), fit_exclude=cls.exclude,
                                obs_sd=book.obs_sd, uncertain=book.uncertain)
        cls.modmap = json.loads((REF / "modifier_map.json").read_text())
        cls.builder = Builder(cls.tab, cls.lib, cls.modmap, TRAIN_RULES)

    def test_every_menu_modifier_maps_into_its_recipe(self):
        # 菜单上可去的配料必须能在该餐品的配方里找到，否则「去酱」会被静默忽略
        drink_like = {"标准", "去冰", "多冰", "少冰", "奶油球", "白砂糖", "换燕麦奶", "不加", "加",
                      "标准（推荐）", "少糖", "不另外加糖"}
        for d in sorted(STORES.iterdir()):
            cat = load_fixture(d)
            for p in cat.products.values():
                items = [(p.name, p.modifiers)] + [(c.name, c.modifiers) for r in p.rounds for c in r.choices]
                for name, mods in items:
                    rec = self.recipes.get(normalize(name))
                    if rec is None:
                        continue
                    for m in mods:
                        if m.name in drink_like:
                            continue
                        self.assertIn(m.name, self.modmap, f"{name} 的「{m.name}」没有对应配料")
                        self.assertIn(self.modmap[m.name], rec, f"{name} 的配方里没有「{m.name}」")

    def test_fit_is_consistent(self):
        self.assertEqual(self.lib.suspicious(), [])
        n_obs = sum(1 for p in self.recipes if p in self.tab and p not in self.exclude) * len(NUTRIENTS)
        self.assertGreater(self.lib.dof, 0)
        self.assertLess(self.lib.dof, n_obs)

    def test_prediction_sd_uses_covariance(self):
        # 有官方数据的餐品，配料库预测的标准差应接近观测误差（约 2 大卡），而不是按独立相加的 20+ 大卡
        for p in ("汉堡包", "吉士汉堡包", "巨无霸", "原味板烧鸡腿麦满分"):
            _, sd = self.lib.predict(p)
            self.assertLess(sd.kcal, 3.0, p)

    def test_excluded_products_are_not_fitted(self):
        for p in self.exclude:
            self.assertNotIn(p, self.lib.fits)

    def test_removable_parts_have_references(self):
        # 能「去掉」或「留到下一顿」的配料都要有参考值，不能靠弱先验平分
        removable = set(self.modmap.values())
        leftover = {c for r in self.recipes.values() for c in r if c.startswith(("bun.", "sauce.", "veg.", "butter"))}
        for cid in (removable | leftover) & set(self.lib.components):
            self.assertTrue(self.lib.components[cid].prior_source, f"{cid} 没有参考值")

    def test_reliability_rule(self):
        self.assertTrue(is_reliable(Nutrition(kcal=100), Nutrition(kcal=15)))
        self.assertTrue(is_reliable(Nutrition(kcal=100), Nutrition(kcal=40)))
        self.assertFalse(is_reliable(Nutrition(kcal=100), Nutrition(kcal=41)))
        self.assertTrue(is_reliable(Nutrition(kcal=5), Nutrition(kcal=15)))

    def test_unreliable_removal_is_not_offered(self):
        # 红油麻香酱只有参考值、拆不准（约 55±31 大卡），不应给出「去红油麻香酱」的吃法
        self.assertFalse(self.lib.reliable({"sauce.hongyou_mala": 1.0}))
        mods = (Modifier("红油麻香酱", "x", "s", "u", 1),)
        plans = self.builder.eat_plans("酥酥多笋卷", mods, allow_split=False)
        self.assertEqual([p.removed for p in plans], [()])

    def test_sausage_single_pins_mustard_mayo(self):
        # 官方单品「德式图林根香肠」钉住香肠后，不素之霸的芥末沙拉酱变得可拆，可以出「去芥末沙拉酱」
        self.assertAlmostEqual(self.lib.components["sausage.thuringer"].value.kcal, 87, delta=3)
        self.assertTrue(self.lib.reliable({"sauce.mustard_mayo": 1.0}))
        mods = (Modifier("芥末沙拉酱", "x", "s", "u", 1),)
        plans = self.builder.eat_plans("不素之霸双层牛堡", mods, allow_split=False)
        self.assertIn(("芥末沙拉酱",), [p.removed for p in plans])

    def test_predicted_product_is_marked(self):
        # 高达吉士双牛堡不在营养表里：可以推荐，但必须标注为估算
        self.assertNotIn("高达吉士双牛堡", self.tab)
        plans = self.builder.eat_plans("高达吉士双牛堡", (), allow_split=False)
        self.assertGreater(plans[0].estimate_sd, 0)
        cat = load_fixture(STORES / "2026-10-16T1900")
        opts = self.builder.options(cat, kcal_max=800)
        marked = [o for o in opts if "高达吉士双牛堡" in o.label]
        self.assertTrue(marked)
        self.assertTrue(all(any("估算" in f for f in o.footnotes) for o in marked))
        plain = [o for o in opts if "双层吉士汉堡" in o.label and "高达" not in o.label]
        self.assertTrue(all(not o.footnotes for o in plain))

    def test_too_uncertain_prediction_is_not_recommended(self):
        # 龙焰系没有官方营养，配料库预测误差超过 12%，不进入推荐
        value, sd = self.lib.predict("龙焰鸡腿堡")
        self.assertGreater(sd.kcal, 0.12 * value.kcal)
        self.assertIsNone(self.builder.base_nutrition("龙焰鸡腿堡"))

    def test_sauce_on_saved_bun_does_not_make_a_new_plan(self):
        # 只吃馅时，面包上的酱去不去只影响下一顿；这顿吃进去一样的两套方案应合并为一套
        cat = load_fixture(STORES / "2026-10-16T1900")
        opts = self.builder.options(cat, kcal_max=500)
        plans = solve(opts, Constraints(kcal_max=500, protein_min=35), top_k=20)
        shown = distinct(plans, k=10)
        keys = [(p.price_cents, round(p.tonight.kcal), round(p.tonight.protein),
                 tuple(sorted(o.label.split("（")[0] for o in p.options))) for p in shown]
        self.assertEqual(len(keys), len(set(keys)))

    def test_distinct_topk_matches_dedupe_after_solve(self):
        # 求解时直接按「实质」去重取前 k，应与「多求一些再去重」的结果一致
        from mcdstrip.render import plan_signature
        cat = load_fixture(STORES / "2026-10-16T1900")
        opts = self.builder.options(cat, kcal_max=600)
        for c in (Constraints(kcal_max=400, protein_min=30), Constraints(kcal_max=550, protein_min=35),
                  Constraints(kcal_max=500, protein_min=30, require_tags=frozenset({"练腿"}), tag_protein_share=0.5)):
            want = distinct(solve(opts, c, top_k=60), k=3)
            got = solve(opts, c, top_k=3, distinct_key=plan_signature)
            self.assertEqual([p.sort_key for p in got], [p.sort_key for p in want], c)

    def test_meal_words(self):
        self.assertEqual(meal_of("2026-10-17T0730"), "早餐")
        self.assertEqual(meal_of("2026-10-17T1029"), "早餐")
        self.assertEqual(meal_of("2026-10-17 12:00"), "午餐")
        self.assertEqual(meal_of("2026-10-16T1900"), "晚餐")
        self.assertEqual(meal_of("2026-10-16T2230"), "夜宵")

    def test_breakfast_wording(self):
        cat = load_fixture(STORES / "2026-10-17T0730")
        plans = distinct(solve(self.builder.options(cat, kcal_max=350), Constraints(kcal_max=350, protein_min=22), top_k=12), k=3)
        split = next(p for p in plans if p.leftover.kcal > 0)
        text = render_plain(split, slot=cat.slot)
        self.assertIn("这顿早餐吃进去", text)
        self.assertIn("留到午餐", text)
        self.assertNotIn("明早", text)
        gym = render_gym(split, slot=cat.slot)
        self.assertIn("午餐拉伸", gym)
        # 训练清单上列出的餐品，蛋白质加起来要等于训练量（含蛋白的饮料不能藏起来）
        listed = sum(it.tonight.protein for o, n in split.counts() for it in o.items for _ in range(n)
                     if it.name in gym.split("怎么下单")[0])
        self.assertAlmostEqual(listed, split.tonight.protein, delta=0.5)


if __name__ == "__main__":
    unittest.main()
