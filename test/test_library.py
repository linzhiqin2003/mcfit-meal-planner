import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from mcdstrip.library import Prior, build_library, deletion_diagnostics, fit_chi2, load_priors  # noqa: E402
from mcdstrip.nutrition import NUTRIENTS, Nutrition, parse_table  # noqa: E402

TRUE = {
    "bun": Nutrition(150, 5, 2, 28, 220, 40),
    "patty": Nutrition(90, 8, 6, 0, 160, 20),
    "cheese": Nutrition(46, 3, 4, 1, 180, 85),
    "sauce": Nutrition(12, 0, 0, 3, 90, 2),
}
RECIPES = {
    "单层": {"bun": 1, "patty": 1, "sauce": 1},
    "单层芝士": {"bun": 1, "patty": 1, "cheese": 1, "sauce": 1},
    "双层芝士": {"bun": 1, "patty": 2, "cheese": 2, "sauce": 1},
    "三层芝士": {"bun": 1, "patty": 3, "cheese": 3, "sauce": 1},
    "无酱双层": {"bun": 1, "patty": 2, "cheese": 2},
}


def official_from(recipes):
    out = {}
    for p, r in recipes.items():
        total = Nutrition()
        for c, n in r.items():
            total = total + TRUE[c].scale(n)
        out[p] = total.rounded()
    return out


def loose_priors(scale=1.3):
    # 先验故意偏离真值 30%，检验官方数据能把估计拉回真值
    return {c: Prior(v.scale(scale), Nutrition.from_vec(max(abs(x) * 0.4, 5) for x in v.vec())) for c, v in TRUE.items()}


class LibraryTest(unittest.TestCase):
    def test_recovers_identified_components(self):
        lib = build_library(official_from(RECIPES), RECIPES, loose_priors())
        for c in ("patty", "cheese"):
            est = lib.components[c].value
            for k, (a, b) in enumerate(zip(est.vec(), TRUE[c].vec())):
                self.assertAlmostEqual(a, b, delta=2.5, msg=f"{c}.{NUTRIENTS[k]}")
        self.assertLess(lib.components["patty"].identifiability, 0.3)

    def test_whole_products_fit(self):
        lib = build_library(official_from(RECIPES), RECIPES, loose_priors())
        self.assertFalse(lib.suspicious(), [f.product for f in lib.suspicious()])

    def test_wrong_recipe_is_flagged(self):
        off = official_from(RECIPES)
        wrong = dict(RECIPES)
        wrong["三层芝士"] = {"bun": 1, "patty": 3, "cheese": 1, "sauce": 1}   # 少写两片芝士
        lib = build_library(off, wrong, loose_priors())
        self.assertIn("三层芝士", [f.product for f in lib.suspicious()])

    def test_deletion_diagnostics_pinpoint_wrong_recipe(self):
        off = official_from(RECIPES)
        for culprit in ("三层芝士", "单层芝士"):
            wrong = dict(RECIPES)
            r = dict(wrong[culprit]); r["cheese"] = r["cheese"] + 1          # 多写一片芝士
            wrong[culprit] = r
            ranked = deletion_diagnostics(off, wrong, loose_priors())
            self.assertEqual(ranked[0].product, culprit, [(d.product, round(d.chi2_rest, 1)) for d in ranked[:3]])
            self.assertLess(ranked[0].chi2_rest, ranked[1].chi2_rest / 5)

    def test_correct_recipes_fit_without_outliers(self):
        lib = build_library(official_from(RECIPES), RECIPES, loose_priors())
        self.assertLess(fit_chi2(lib), 3.0 * len(RECIPES))

    def test_no_negative_components(self):
        lib = build_library(official_from(RECIPES), RECIPES, loose_priors(0.5))
        for c in lib.components.values():
            self.assertTrue(all(x >= 0 for x in c.value.vec()), c.id)

    def test_prediction_for_unlisted_product(self):
        recipes = dict(RECIPES)
        recipes["四层芝士"] = {"bun": 1, "patty": 4, "cheese": 4, "sauce": 1}
        off = official_from(RECIPES)                     # 四层芝士不在官方表里
        lib = build_library(off, recipes, loose_priors())
        pred, sd = lib.predict("四层芝士")
        truth = official_from({"x": recipes["四层芝士"]})["x"]
        self.assertAlmostEqual(pred.kcal, truth.kcal, delta=3 * max(sd.kcal, 2))


class PriorLoadingTest(unittest.TestCase):
    def test_missing_nutrient_is_unknown_not_zero(self):
        import tempfile
        from mcdstrip.library import WEAK_PRIOR_SD
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "p.json"
            f.write_text(json.dumps({"x": {"mean": {"kcal": 100}, "rel_sd": 0.3},
                                     "y": {"mean": {"kcal": 100}, "sd": {"kcal": 10}}}))
            pr = load_priors(f)
        for cid in ("x", "y"):
            self.assertEqual(pr[cid].mean.calcium, 0.0)
            self.assertEqual(pr[cid].sd.calcium, WEAK_PRIOR_SD["calcium"], cid)
        self.assertAlmostEqual(pr["x"].sd.kcal, 30.0)
        self.assertEqual(pr["y"].sd.kcal, 10.0)


class RealDataTest(unittest.TestCase):
    """用官方营养表和草稿配方跑一遍：双层吉士汉堡的拆分必须守恒。"""

    def test_draft_recipes_on_official_table(self):
        tab = parse_table((ROOT / "data/fixtures/nutrition_raw.txt").read_text())
        recipes = json.loads((ROOT / "data/reference/recipes_draft.json").read_text())
        lib = build_library(tab, recipes, load_priors(ROOT / "data/reference/priors_us.json"))
        self.assertFalse(lib.suspicious())
        patty = lib.components["patty.beef_small"].value
        self.assertAlmostEqual(patty.kcal, 89, delta=3)
        self.assertAlmostEqual(patty.carb, 0, delta=1)
        # 钙由官方数据直接确定：吉士汉堡包 − 汉堡包 = 144 − 61 = 83
        self.assertAlmostEqual(lib.components["cheese.american"].value.calcium, 83, delta=2)


if __name__ == "__main__":
    unittest.main()
