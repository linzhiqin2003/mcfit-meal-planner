import itertools
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from mcdstrip import linalg as la  # noqa: E402


class LinalgTest(unittest.TestCase):
    def test_cholesky_roundtrip(self):
        a = [[4.0, 2.0, 0.6], [2.0, 5.0, 1.0], [0.6, 1.0, 3.0]]
        L = la.cholesky(a)
        back = la.matmul(L, la.transpose(L))
        for r1, r2 in zip(a, back):
            for x, y in zip(r1, r2):
                self.assertAlmostEqual(x, y, places=9)

    def test_spd_inverse(self):
        a = [[4.0, 1.0], [1.0, 3.0]]
        inv = la.spd_inverse(a)
        ident = la.matmul(a, inv)
        self.assertAlmostEqual(ident[0][0], 1.0)
        self.assertAlmostEqual(ident[0][1], 0.0)

    def test_not_positive_definite(self):
        with self.assertRaises(ValueError):
            la.cholesky([[1.0, 2.0], [2.0, 1.0]])

    def test_nnls_matches_unconstrained_when_positive(self):
        a = [[1.0, 0.0], [0.0, 1.0], [1.0, 1.0]]
        b = [1.0, 2.0, 3.0]
        x = la.nnls(a, b)
        self.assertAlmostEqual(x[0], 1.0, places=6)
        self.assertAlmostEqual(x[1], 2.0, places=6)

    def test_nnls_clamps_negative(self):
        a = [[1.0, 1.0], [1.0, 1.0], [0.0, 1.0]]
        b = [1.0, 1.0, -5.0]   # 无约束解第二个分量为负
        x = la.nnls(a, b)
        self.assertGreaterEqual(min(x), 0.0)
        self.assertAlmostEqual(x[1], 0.0, places=6)
        self.assertAlmostEqual(x[0], 1.0, places=6)

    def test_nnls_tiny_positive_optimum_does_not_crash(self):
        # 审查发现：新变量的最优值落在 (0, tol] 时，回退步长的候选集为空导致 min() 崩溃
        x = la.nnls([[2.0], [1.0]], [1e-10, 0.0])
        self.assertAlmostEqual(x[0], 0.0, places=9)
        x = la.nnls([[1000.0]], [1e-8])
        self.assertAlmostEqual(x[0], 0.0, places=9)
        x = la.nnls([[1.0, 0.0], [0.0, 1e6], [0.0, 0.0]], [3.0, 1e-4, 0.0])
        self.assertAlmostEqual(x[0], 3.0, places=9)
        self.assertLess(abs(x[1]), 1e-9)

    def test_nnls_ill_scaled_fuzz(self):
        import random
        rng = random.Random(7)
        for _ in range(300):
            n = rng.randint(1, 4)
            scale = [10 ** rng.uniform(-3, 6) for _ in range(n)]
            a = [[rng.gauss(0, 1) * scale[j] for j in range(n)] for _ in range(n + 2)]
            b = [rng.gauss(0, 1e-6) for _ in range(n + 2)]
            x = la.nnls(a, b)
            self.assertTrue(all(v >= 0 for v in x))

    def test_nnls_against_brute_force(self):
        """随机小问题：与枚举所有主动集的暴力解比较目标值。"""
        rnd = random.Random(7)
        for _ in range(30):
            m, n = 6, 3
            a = [[rnd.uniform(-1, 2) for _ in range(n)] for _ in range(m)]
            b = [rnd.uniform(-2, 3) for _ in range(m)]
            x = la.nnls(a, b)
            obj = lambda v: sum((bi - ri) ** 2 for bi, ri in zip(b, la.matvec(a, v)))
            best = obj([0.0] * n)
            for k in range(1, n + 1):
                for idx in itertools.combinations(range(n), k):
                    sub = [[row[j] for j in idx] for row in a]
                    try:
                        z = la.lstsq_spd(sub, b)
                    except ValueError:
                        continue
                    if min(z) < 0:
                        continue
                    v = [0.0] * n
                    for j, val in zip(idx, z):
                        v[j] = val
                    best = min(best, obj(v))
            self.assertLessEqual(obj(x), best + 1e-6)


if __name__ == "__main__":
    unittest.main()
