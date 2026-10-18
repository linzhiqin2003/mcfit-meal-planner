"""差异化信息：同一个汉堡的几种吃法、门店官方「500 大卡套餐」对比（离线快照）。"""
import contextlib
import io
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from mcdstrip.catalog import Builder, load_fixture  # noqa: E402
from mcdstrip.cli import load_core, main  # noqa: E402
from mcdstrip.compare import eat_ladder, official_sets  # noqa: E402
from mcdstrip.render import TRAIN_RULES, short_how  # noqa: E402
from mcdstrip.solver import Constraints  # noqa: E402

DINNER = ROOT / "data/fixtures/stores/1450441/2026-10-16T1900"


class CompareTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cat = load_fixture(DINNER)
        table, lib, modmap = load_core()
        cls.b = Builder(table, lib, modmap, TRAIN_RULES)

    def test_menu_categories_kept(self):
        self.assertIn("500大卡套餐", self.cat.categories)
        self.assertEqual(len(self.cat.categories["500大卡套餐"]), 6)

    def test_official_sets_match_app(self):
        # 与麦当劳 App「500 大卡套餐」页标注的热量一致（2026-10-16 截图）
        sets = {x.name: x for x in official_sets(self.b, self.cat, Constraints(kcal_max=500, protein_min=30))}
        expect = {"“苹”水相“鱼”套餐": 412, "酥脆无双套餐": 434, "“辣”么快乐套餐": 394, "牛气满满套餐": 495,
                  "“苹板”支撑Pro套餐": 476}
        for name, kcal in expect.items():
            self.assertAlmostEqual(sets[name].whole.kcal, kcal, delta=3, msg=name)
        # 整份吃没有一款能到 30 g 蛋白质；能拆的套餐拆完热量更低
        self.assertFalse(any(x.fits_whole for x in sets.values()))
        self.assertLess(sets["牛气满满套餐"].lowest.kcal, sets["牛气满满套餐"].whole.kcal - 200)
        self.assertEqual(sets["酥脆无双套餐"].lowest_hows, ())   # 炸鸡和薯条没有可拆的吃法

    def test_ladder_double_cheeseburger(self):
        rungs = eat_ladder(self.b, self.cat, "双层吉士汉堡", "下单去吉士，到手只吃馅，面包留到下一顿")
        self.assertEqual([round(r.tonight.kcal) for r in rungs], [429, 339, 272, 182])
        self.assertEqual(rungs[0].how, "整份吃")
        self.assertTrue(rungs[-1].chosen)
        self.assertEqual(sum(r.chosen for r in rungs), 1)

    def test_ladder_merges_same_meal_and_caps(self):
        # 巨无霸有 8 种吃法：只吃馅时去不去芝士/酱，这一顿一样的合并；最多 5 档，保留整份和最低
        rungs = eat_ladder(self.b, self.cat, "巨无霸")
        self.assertLessEqual(len(rungs), 5)
        self.assertEqual(rungs[0].how, "整份吃")
        kcals = [round(r.tonight.kcal) for r in rungs]
        self.assertEqual(kcals, sorted(kcals, reverse=True))
        self.assertEqual(len(set(kcals)), len(kcals))

    def test_single_way_has_no_ladder(self):
        self.assertEqual(eat_ladder(self.b, self.cat, "麦麦脆汁鸡-琵琶腿"), [])

    def test_short_how(self):
        self.assertEqual(short_how("下单去麦香鸡酱，到手只吃馅，面包留到下一顿"), "去麦香鸡酱 + 只吃馅")
        self.assertEqual(short_how("到手只吃馅，面包留到下一顿"), "只吃馅")
        self.assertEqual(short_how("整份吃"), "整份吃")


class CompareCliTest(unittest.TestCase):
    def run_plan(self, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = main(["plan", *args, "--offline", str(DINNER)])
        return code, out.getvalue()

    def test_card_shows_options_and_official_compare(self):
        code, out = self.run_plan("--kcal-max", "500", "--protein-min", "30", "--train", "练腿", "--style", "gym", "--top", "1")
        self.assertEqual(code, 0)
        self.assertIn("同一个麦香鸡，有这几种练法：", out)
        self.assertIn("← 本方案", out)
        self.assertIn("对比麦当劳官方「500 大卡套餐」", out)
        self.assertIn("没有一款能到 30 g 蛋白质", out)

    def test_json_has_eat_options_and_official_sets(self):
        code, out = self.run_plan("--kcal-max", "500", "--protein-min", "30", "--train", "练腿", "--format", "json", "--top", "1")
        d = json.loads(out)
        self.assertEqual(len(d["official_sets"]), 6)
        opts = d["plans"][0]["eat_options"]
        self.assertTrue(opts and opts[0]["options"])
        self.assertEqual(sum(o["chosen"] for o in opts[0]["options"]), 1)


if __name__ == "__main__":
    unittest.main()
