import itertools
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from mcdstrip.nutrition import Nutrition  # noqa: E402
from mcdstrip.solver import Constraints, Option, is_minimal, solve  # noqa: E402


def rand_options(rnd: random.Random, n: int) -> list[Option]:
    """随机选项：含零热量但有蛋白的、带留存的、部位蛋白占比不一的、价格细粒度的。"""
    out = []
    for i in range(n):
        kcal = rnd.choice([0, rnd.randint(30, 600), rnd.randint(30, 600)])
        protein = rnd.choice([0, rnd.randint(0, 35), rnd.randint(1, 35)])
        leg = rnd.random() < 0.35
        out.append(Option(id=f"o{i}", label=f"o{i}", price_cents=rnd.randint(5, 40) * rnd.choice([100, 10]),
                          tonight=Nutrition(kcal=kcal, protein=protein, fat=rnd.randint(0, 30), carb=rnd.randint(0, 60),
                                            sodium=rnd.randint(0, 1200)),
                          leftover=Nutrition(kcal=rnd.choice([0, 0, rnd.randint(50, 300)])),
                          tags=frozenset({"leg"}) if leg else frozenset(),
                          tag_protein=(("leg", float(protein) * rnd.choice([1.0, 0.4, 0.7])),) if leg else ()))
    return out


def brute(options: list[Option], c: Constraints, top_k: int):
    sols = []
    idx = range(len(options))
    for k in range(1, c.max_items + 1):
        for combo in itertools.combinations_with_replacement(idx, k):
            if any(combo.count(i) > c.max_copies for i in set(combo)):
                continue
            sel = [options[i] for i in combo]
            t = Nutrition()
            for o in sel:
                t = t + o.tonight
            price = sum(o.price_cents for o in sel)
            if t.kcal > c.kcal_max or t.protein < c.protein_min:
                continue
            if c.carb_max is not None and t.carb > c.carb_max:
                continue
            if c.fat_max is not None and t.fat > c.fat_max:
                continue
            if c.sodium_max is not None and t.sodium > c.sodium_max:
                continue
            if c.budget_cents is not None and price > c.budget_cents:
                continue
            if c.require_tags and not any(o.tags & c.require_tags for o in sel):
                continue
            if not is_minimal(tuple(sel), c):
                continue
            if c.require_tags and c.tag_protein_share > 0:
                tagged = sum(v for o in sel for tag, v in o.tag_protein if tag in c.require_tags)
                if t.protein <= 0 or tagged / t.protein < c.tag_protein_share:
                    continue
            left = sum(o.leftover.kcal for o in sel)
            sols.append((price, -round(t.protein, 3), round(t.kcal, 3), round(left, 3), tuple(sorted(o.id for o in sel))))
    sols.sort()
    return sols[:top_k]


class SolverTest(unittest.TestCase):
    def check(self, seed: int, prune: bool):
        rnd = random.Random(seed)
        opts = rand_options(rnd, rnd.randint(5, 9))
        c = Constraints(kcal_max=rnd.choice([400, 600, 900]), protein_min=rnd.choice([0, 20, 30, 45]),
                        carb_max=rnd.choice([None, 80]), fat_max=rnd.choice([None, 40]), sodium_max=rnd.choice([None, 1500]),
                        budget_cents=rnd.choice([None, 6000]), max_items=rnd.choice([2, 3, 4]),
                        max_copies=rnd.choice([1, 2, 3]),
                        require_tags=rnd.choice([frozenset(), frozenset({"leg"})]),
                        tag_protein_share=rnd.choice([0.0, 0.5]))
        got = solve(opts, c, top_k=5, prune_dominated=prune)
        want = brute(opts, c, 5)
        got_keys = [(p.price_cents, -round(p.tonight.protein, 3), round(p.tonight.kcal, 3), round(p.leftover.kcal, 3),
                     tuple(sorted(o.id for o in p.options))) for p in got]
        return got_keys, want

    def test_dominated_option_kept_when_dominator_capped(self):
        # 审查用例：b 支配 a，但 b 最多 2 份；唯一最优是 {b, b, a}
        a = Option("a", "a", 1100, Nutrition(kcal=110, protein=9))
        b = Option("b", "b", 1000, Nutrition(kcal=100, protein=10))
        c = Constraints(kcal_max=400, protein_min=29, max_items=3, max_copies=2)
        got = solve([a, b], c, top_k=1)
        self.assertEqual(got[0].price_cents, 3100)

    def test_minimality_respects_tag_share(self):
        # 审查用例：去掉 T2 后蛋白还够，但练腿占比降到 44%，所以 T2 不是多余的
        t1 = Option("t1", "t1", 1000, Nutrition(kcal=100, protein=20), tags=frozenset({"leg"}), tag_protein=(("leg", 20.0),))
        t2 = Option("t2", "t2", 1000, Nutrition(kcal=100, protein=10), tags=frozenset({"leg"}), tag_protein=(("leg", 10.0),))
        u = Option("u", "u", 500, Nutrition(kcal=100, protein=25))
        c = Constraints(kcal_max=400, protein_min=40, max_items=3, max_copies=1,
                        require_tags=frozenset({"leg"}), tag_protein_share=0.5)
        self.assertTrue(is_minimal((t1, t2, u), c))
        got = solve([t1, t2, u], c, top_k=1)
        self.assertEqual(got[0].price_cents, 2500)

    def test_negative_nutrition_rejected(self):
        bad = Option("x", "x", 500, Nutrition(kcal=100, protein=10, sodium=-2))
        with self.assertRaises(ValueError):
            solve([bad], Constraints(kcal_max=400, protein_min=5))

    def test_exact_topk_without_pruning(self):
        for seed in range(400):
            got, want = self.check(seed, prune=False)
            self.assertEqual(got, want, f"seed={seed}")

    def test_optimum_with_dominance_pruning(self):
        # 支配过滤只保证「最便宜的价格」不变（被支配的选项可能出现在次优方案里）
        for seed in range(400):
            got, want = self.check(seed, prune=True)
            self.assertEqual(bool(got), bool(want), f"seed={seed}")
            if want:
                self.assertEqual(got[0][0], want[0][0], f"seed={seed}")
            if want:
                self.assertEqual(got[0][0], want[0][0], f"seed={seed}：最优价格不一致")

    def test_constraints_respected(self):
        rnd = random.Random(99)
        opts = rand_options(rnd, 12)
        c = Constraints(kcal_max=500, protein_min=30, carb_max=60, max_items=4)
        for p in solve(opts, c, top_k=8):
            self.assertLessEqual(p.tonight.kcal, 500)
            self.assertGreaterEqual(p.tonight.protein, 30)
            self.assertLessEqual(p.tonight.carb, 60)

    def test_no_redundant_items(self):
        """方案里不应有可以去掉的多余项（例如为凑数多点一份苹果片）。"""
        rnd = random.Random(5)
        opts = rand_options(rnd, 12)
        c = Constraints(kcal_max=800, protein_min=30, max_items=4)
        for p in solve(opts, c, top_k=10):
            for i, o in enumerate(p.options):
                rest = sum(x.tonight.protein for j, x in enumerate(p.options) if j != i)
                self.assertLess(rest, 30, "存在可去掉仍达标的多余项")

    def test_infeasible_returns_empty(self):
        opts = [Option("a", "a", 1000, Nutrition(kcal=300, protein=5))]
        self.assertEqual(solve(opts, Constraints(kcal_max=400, protein_min=50)), [])


if __name__ == "__main__":
    unittest.main()
