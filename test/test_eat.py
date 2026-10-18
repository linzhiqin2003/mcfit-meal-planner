"""单样餐品查吃法（gym.py eat）：名字匹配、几种吃法的数字、只能整份吃、套餐和查不到时的说明。"""
import contextlib
import io
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from mcdstrip.cli import main  # noqa: E402
from mcdstrip.lookup import _in_order, resolve  # noqa: E402


def eat(*args) -> tuple[int, dict]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        code = main(["eat", *args, "--format", "json"])
    return code, json.loads(out.getvalue())


def option(d: dict, short: str) -> dict:
    return next(o for o in d["options"] if o["short"] == short)


class EatTest(unittest.TestCase):
    def test_double_cheeseburger_ladder(self):
        code, d = eat("双层吉士汉堡")
        self.assertEqual(code, 0, d)
        self.assertEqual(d["whole_source"], "官方营养表")
        self.assertEqual(option(d, "整份吃")["this_meal"]["kcal"], 429)       # 官方营养表原值
        both = option(d, "去吉士 + 只吃馅")
        self.assertAlmostEqual(both["this_meal"]["kcal"], 182, delta=5)
        self.assertAlmostEqual(both["next_meal"]["kcal"], 157, delta=5)
        # 只吃馅：这一顿 + 留到下一顿 = 整份
        split = option(d, "只吃馅")
        self.assertEqual(split["this_meal"]["kcal"] + split["next_meal"]["kcal"], 429)
        self.assertIn("面包 157 大卡留到下一顿", d["card"])
        self.assertTrue(any("酱和菜" in x for x in d["footnotes"]))

    def test_short_names_resolve(self):
        self.assertEqual(eat("双吉")[1]["name"], "双层吉士汉堡")
        self.assertEqual(eat("麦辣鸡腿堡")[1]["name"], "麦辣鸡腿汉堡")       # 少一个字
        # 按块数换算，不能被字形相近的「麦乐鸡5块」顶替
        code, d = eat("麦乐鸡10块")
        self.assertEqual(d["name"], "麦乐鸡10块")
        five = eat("麦乐鸡5块")[1]["options"][0]["this_meal"]["kcal"]
        self.assertAlmostEqual(d["options"][0]["this_meal"]["kcal"], 2 * five, delta=1)   # 各自四舍五入

    def test_breakfast_item_has_removable_parts(self):
        # 自带快照里只有早餐那份菜单有麦满分的可去配料
        code, d = eat("猪柳蛋麦满分")
        self.assertEqual(code, 0, d)
        self.assertIn("去吉士", [o["short"] for o in d["options"]])

    def test_whole_only(self):
        code, d = eat("纯牛奶（盒装）")
        self.assertEqual(code, 0, d)
        self.assertEqual(len(d["options"]), 1)
        self.assertIsNone(d["options"][0]["next_meal"])
        self.assertIn("只能整份吃", d["card"])

    def test_estimated_item_says_so(self):
        code, d = eat("高达吉士双牛堡")
        self.assertEqual(code, 0, d)
        self.assertEqual(d["whole_source"], "配料库估算")
        self.assertTrue(any("不在官方营养表里" in x for x in d["footnotes"]))

    def test_ambiguous_and_unknown(self):
        code, d = eat("鸡翅")
        self.assertEqual(code, 1)
        self.assertFalse(d["ok"])
        self.assertEqual(set(d["candidates"]), {"麦辣鸡翅-2块", "麦辣鸡翅-4块"})
        code, d = eat("麦辣鸡翅4块套餐")
        self.assertEqual(code, 1)
        self.assertIn("套餐", d["error"])
        code, d = eat("螺蛳粉")
        self.assertEqual((code, d["candidates"]), (1, []))

    def test_resolve_order(self):
        names = {"双层吉士汉堡", "吉士汉堡包", "麦香鸡"}
        self.assertEqual(resolve("吉士汉堡包", names), ["吉士汉堡包"])           # 精确优先于包含
        self.assertEqual(resolve("吉士", names), ["吉士汉堡包", "双层吉士汉堡"])  # 包含：短名在前
        self.assertEqual(resolve("双吉", names), ["双层吉士汉堡"])               # 按顺序含有
        self.assertTrue(_in_order("双吉", "双层吉士汉堡"))
        self.assertFalse(_in_order("吉双", "双层吉士汉堡"))


if __name__ == "__main__":
    unittest.main()
