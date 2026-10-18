"""「装」页散点图的数据（scripts/build_site_ingredients.py）：和配料库一一对应、每项都有分组，站点里的文件是最新的。"""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_site_ingredients as bi  # noqa: E402


class SiteIngredientsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lib = json.loads((ROOT / "data/ingredient_library.json").read_text(encoding="utf-8"))
        cls.data = bi.build(cls.lib)

    def test_one_item_per_component(self):
        self.assertEqual(sorted(i["id"] for i in self.data["items"]), sorted(self.lib["components"]))

    def test_values_match_library(self):
        for i in self.data["items"]:
            c = self.lib["components"][i["id"]]
            self.assertAlmostEqual(i["kcal"], c["value"]["kcal"], delta=0.06)
            self.assertAlmostEqual(i["sd"], c["sd"]["kcal"], delta=0.06)
            self.assertAlmostEqual(i["protein"], c["value"]["protein"], delta=0.06)

    def test_groups_cover_the_three_annotated_clusters(self):
        g = {i["id"]: i["group"] for i in self.data["items"]}
        self.assertEqual(g["patty.beef_small"], "meat")
        self.assertEqual(g["egg.round"], "meat")
        self.assertEqual(g["bun.regular"], "bread")
        self.assertEqual(g["sauce.ketchup"], "sauce")
        self.assertEqual(g["cheese.american"], "other")
        # 页面上的手写批注「酱：几乎只有热量」「面包：留到明早」「肉和蛋：蛋白主力」要和数据一致
        prot = lambda grp: [i["protein"] for i in self.data["items"] if i["group"] == grp]
        self.assertLess(max(prot("sauce")), 1.0)
        self.assertGreater(min(prot("meat")), max(prot("sauce")))

    def test_unknown_prefix_is_an_error(self):
        with self.assertRaises(ValueError):
            bi.group_of("noodle.ramen")

    def test_site_file_is_up_to_date(self):
        on_disk = json.loads((ROOT / "site/data/ingredients.json").read_text(encoding="utf-8"))
        self.assertEqual(on_disk, self.data, "site/data/ingredients.json 过期了，请运行 scripts/build_site_ingredients.py")


if __name__ == "__main__":
    unittest.main()
