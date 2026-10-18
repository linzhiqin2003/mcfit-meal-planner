"""命令行：参数换算、无解提示、训练部位缺失、加练、JSON 输出（离线快照）。"""
import contextlib
import io
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from mcdstrip.cli import main  # noqa: E402

DINNER = str(ROOT / "data/fixtures/stores/1450441/2026-10-16T1900")


def run(*args) -> tuple[int, str]:
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        try:
            code = main(["plan", *args, "--offline", DINNER])
        except SystemExit as e:      # argparse 报错
            code = e.code
    return code, out.getvalue()


class CliTest(unittest.TestCase):
    def test_budget_exactly_at_price(self):
        # 19.9 × 100 = 1989.999…，不能截断成 1989 把正好 19.9 元的方案排除
        code, out = run("--kcal-max", "600", "--protein-min", "20", "--budget", "19.9", "--format", "json")
        self.assertEqual(code, 0, out)
        prices = [p["price_yuan"] for p in json.loads(out)["plans"]]
        self.assertTrue(all(x <= 19.9 for x in prices))

    def test_zero_budget_is_a_constraint(self):
        code, out = run("--kcal-max", "600", "--protein-min", "20", "--budget", "0")
        self.assertEqual(code, 1)
        self.assertIn("预算", out)

    def test_invalid_numbers_rejected(self):
        self.assertNotEqual(run("--kcal-max", "400", "--top", "0")[0], 0)
        self.assertNotEqual(run("--kcal-max", "-1")[0], 0)

    def test_missing_body_part_is_explained_quickly(self):
        # 快照门店没有里脊：直接说明，而不是退化成穷举
        code, out = run("--kcal-max", "800", "--protein-min", "30", "--train", "练背")
        self.assertEqual(code, 1)
        self.assertIn("没有「练背」的餐品", out)

    def test_infeasible_names_the_blocker(self):
        code, out = run("--kcal-max", "400", "--protein-min", "30", "--carb-max", "1")
        self.assertEqual(code, 1)
        self.assertIn("碳水上限", out)

    def test_top_count_respected(self):
        code, out = run("--kcal-max", "400", "--protein-min", "30", "--top", "5", "--format", "json")
        self.assertEqual(code, 0)
        plans = json.loads(out)["plans"]
        self.assertEqual(len(plans), 5)
        self.assertEqual([p["price_yuan"] for p in plans], sorted(p["price_yuan"] for p in plans))

    def test_json_items_and_card(self):
        code, out = run("--kcal-max", "500", "--protein-min", "30", "--train", "练腿", "--format", "json", "--top", "1")
        d = json.loads(out)
        self.assertTrue(d["ok"])
        p = d["plans"][0]
        self.assertIn("今日训练：练腿", p["card"])
        self.assertTrue(p["calculate_price_items"])
        self.assertEqual(d["order_args"]["storeCode"], "1450441")

    def test_bonus_is_whole_eat_and_within_cap(self):
        code, out = run("--kcal-max", "600", "--protein-min", "30", "--style", "gym", "--top", "3")
        for block in out.split("—— 方案")[1:]:
            if "上上强度" in block:
                line = next(x for x in block.splitlines() if "上上强度" in x)
                self.assertNotRegex(line, r"黑巧|奶铁|咖啡|新地|麦旋风|派")   # 加练得是训练动作，不是饮料甜品
                self.assertNotIn("只吃馅", line)
                self.assertNotIn("整份吃", line)
                extra = int(line.split("+")[1].split(" ")[0])
                total = int(block.split("训练量：")[1].split(" ")[0])
                self.assertLessEqual(total + extra, 600 * 1.25)


if __name__ == "__main__":
    unittest.main()
