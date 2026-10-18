"""小规模稠密线性代数（纯标准库）：Cholesky 分解、对称正定求逆、非负最小二乘（Lawson–Hanson）。

配料库的规模是几十个未知数、上百个方程，纯 Python 足够快，也避免引入 numpy 依赖。
"""
from __future__ import annotations

import math

Matrix = list[list[float]]
Vector = list[float]


def transpose(a: Matrix) -> Matrix:
    return [list(col) for col in zip(*a)] if a else []


def matmul(a: Matrix, b: Matrix) -> Matrix:
    bt = transpose(b)
    return [[sum(x * y for x, y in zip(row, col)) for col in bt] for row in a]


def matvec(a: Matrix, v: Vector) -> Vector:
    return [sum(x * y for x, y in zip(row, v)) for row in a]


def cholesky(a: Matrix) -> Matrix:
    """返回下三角 L，使 L·Lᵀ = a。a 必须对称正定，否则抛 ValueError。"""
    n = len(a)
    L = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1):
            s = a[i][j] - sum(L[i][k] * L[j][k] for k in range(j))
            if i == j:
                if s <= 0:
                    raise ValueError(f"矩阵不是正定的（第 {i} 个主元 {s:.3g}）")
                L[i][i] = math.sqrt(s)
            else:
                L[i][j] = s / L[j][j]
    return L


def chol_solve(L: Matrix, b: Vector) -> Vector:
    n = len(L)
    y = [0.0] * n
    for i in range(n):
        y[i] = (b[i] - sum(L[i][k] * y[k] for k in range(i))) / L[i][i]
    x = [0.0] * n
    for i in reversed(range(n)):
        x[i] = (y[i] - sum(L[k][i] * x[k] for k in range(i + 1, n))) / L[i][i]
    return x


def spd_inverse(a: Matrix) -> Matrix:
    L = cholesky(a)
    n = len(a)
    cols = [chol_solve(L, [1.0 if r == c else 0.0 for r in range(n)]) for c in range(n)]
    return transpose(cols)


def lstsq_spd(a: Matrix, b: Vector) -> Vector:
    """最小二乘 min ||a·x − b||，通过正规方程（aᵀa 需正定）。"""
    at = transpose(a)
    return chol_solve(cholesky(matmul(at, a)), matvec(at, b))


def nnls(a: Matrix, b: Vector, max_iter: int | None = None, tol: float = 1e-10) -> Vector:
    """非负最小二乘 min ||a·x − b|| s.t. x ≥ 0（Lawson–Hanson 主动集算法）。

    数值保护：新加入的变量如果解出来不为正（列尺度悬殊时，正的最优值可能小到 tol 以内），
    就把它退回并在本轮跳过，换下一个候选；否则回退步长的分母为负，算法会崩溃或空转。"""
    m, n = len(a), len(a[0])
    at = transpose(a)
    x = [0.0] * n
    passive: set[int] = set()
    blocked: set[int] = set()
    max_iter = max_iter or 3 * n + 30

    def grad(xv: Vector) -> Vector:
        r = [bi - ri for bi, ri in zip(b, matvec(a, xv))]
        return matvec(at, r)

    for _ in range(max_iter):
        w = grad(x)
        cand = [j for j in range(n) if j not in passive and j not in blocked and w[j] > tol]
        if not cand:
            break
        j_new = max(cand, key=lambda j: w[j])
        passive.add(j_new)
        first = True
        while passive:
            idx = sorted(passive)
            z = dict(zip(idx, lstsq_spd([[row[j] for j in idx] for row in a], b)))
            if first and z[j_new] <= tol:
                passive.discard(j_new)
                blocked.add(j_new)
                break
            first = False
            if all(v > tol for v in z.values()):
                x = [0.0] * n
                for j, v in z.items():
                    x[j] = v
                blocked.clear()
                break
            # 回退：沿 x→z 方向走到第一个变量触零。此处每个 z≤tol 的变量都有 x>tol（新变量已在上面排除）
            alpha = min(x[j] / (x[j] - v) for j, v in z.items() if v <= tol)
            for j, v in z.items():
                x[j] = x[j] + alpha * (v - x[j])
            for j in list(passive):
                if x[j] <= tol:
                    x[j] = 0.0
                    passive.discard(j)
            blocked.clear()
    return x
