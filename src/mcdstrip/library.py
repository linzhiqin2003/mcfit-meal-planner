"""配料级营养库：由官方整份数据和配方，反推每个配料的营养。

模型（对每种营养素分别求解）：
    官方值 y_p = Σ_c 份数 A_pc · 配料 x_c + 取整误差
    先验    x_c ~ 参考值 μ_c ± σ_c（美国官网配料数据；没有参考值的配料用很宽的弱先验）
求解带非负约束的加权最小二乘：
    min Σ_p ((y_p − A_p·x)/σ_y)² + Σ_c ((x_c − μ_c)/σ_c)²,  x ≥ 0
后验标准差取 (AᵀWA + Λ)⁻¹ 的对角线（不考虑非负约束的近似）。
可辨识度 = 后验标准差 / 先验标准差：越小说明越由官方数据决定，越大说明越依赖先验。
残差异常（|残差| > 3σ_y）的餐品，说明配方可能写错。
"""
from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass, field
from pathlib import Path

from .linalg import matmul, matvec, nnls, spd_inverse, transpose
from .nutrition import NUTRIENTS, Nutrition

log = logging.getLogger(__name__)

# 官方值是整数：取整误差标准差约 0.29；再给配方与批次差异留余量
OBS_SD = {"kcal": 2.0, "protein": 0.6, "fat": 0.6, "carb": 0.6, "sodium": 6.0, "calcium": 6.0}
# 没有参考值的配料：弱先验（均值取 0，标准差很宽），只为让方程可解
WEAK_PRIOR_SD = {"kcal": 400.0, "protein": 40.0, "fat": 40.0, "carb": 60.0, "sodium": 1500.0, "calcium": 400.0}
# 拆分可信度：热量标准差不超过 max(绝对值, 相对值 × 热量) 才拿来给吃法建议
RELIABLE_SD_ABS = 15.0
RELIABLE_SD_REL = 0.4


def is_reliable(value: Nutrition, sd: Nutrition) -> bool:
    return sd.kcal <= max(RELIABLE_SD_ABS, RELIABLE_SD_REL * value.kcal)


@dataclass
class Prior:
    mean: Nutrition
    sd: Nutrition
    source: str = ""


@dataclass
class ComponentEstimate:
    id: str
    name: str
    value: Nutrition
    sd: Nutrition
    identifiability: float      # 热量维度的后验/先验标准差比，0 = 完全由官方数据确定，1 = 完全依赖先验
    prior_source: str = ""

    @property
    def basis(self) -> str:
        if not is_reliable(self.value, self.sd):
            return "拆分不确定"
        if self.identifiability < 0.3:
            return "官方数据确定"
        if self.identifiability < 0.8:
            return "官方数据与参考值共同确定"
        return "主要依赖参考值"


@dataclass
class ProductFit:
    product: str
    official: Nutrition
    predicted: Nutrition
    residual: Nutrition
    z: dict[str, float] = field(default_factory=dict)

    @property
    def max_z(self) -> float:
        return max(abs(v) for v in self.z.values()) if self.z else 0.0


@dataclass
class Library:
    components: dict[str, ComponentEstimate]
    fits: dict[str, ProductFit]
    recipes: dict[str, dict[str, float]]
    dof: float = 0.0        # 有效自由度：观测数 − 帽子矩阵的迹（先验让参数「半自由」，不能直接用观测数减参数数）
    # 每种营养素的后验协方差（按 order 排列）。同一份官方总数钉住的配料之间强负相关，
    # 组合的标准差必须用 cᵀΣc，按独立相加会高估 10–20 倍（例：汉堡包 22 → 2 大卡）
    cov: dict[str, list[list[float]]] = field(default_factory=dict)
    order: list[str] = field(default_factory=list)
    uncertain: dict[str, dict[str, float]] = field(default_factory=dict)   # 见 RecipeBook.uncertain

    def nutrition_of(self, parts: dict[str, float]) -> tuple[Nutrition, Nutrition]:
        """一组配料（id → 份数）的营养与标准差（用后验协方差合成；没有协方差时按独立近似）。"""
        total = Nutrition()
        for cid, n in parts.items():
            total = total + self.components[cid].value.scale(n)
        if self.cov:
            pos = {c: i for i, c in enumerate(self.order)}
            items = [(pos[c], n) for c, n in parts.items()]
            var = [sum(ni * nj * self.cov[nut][i][j] for i, ni in items for j, nj in items) for nut in NUTRIENTS]
        else:
            var = [0.0] * len(NUTRIENTS)
            for cid, n in parts.items():
                for i, s in enumerate(self.components[cid].sd.vec()):
                    var[i] += (n * s) ** 2
        return total, Nutrition.from_vec(math.sqrt(max(v, 0.0)) for v in var)

    def reliable(self, parts: dict[str, float]) -> bool:
        return is_reliable(*self.nutrition_of(parts))

    def predict(self, product: str) -> tuple[Nutrition, Nutrition]:
        """按配方预测整份营养。配方里「可能还有」的配料不计入均值，按半份计入标准差。"""
        value, sd = self.nutrition_of(self.recipes[product])
        extra = self.uncertain.get(product)
        if extra:
            add, _ = self.nutrition_of({c: q / 2 for c, q in extra.items()})
            sd = Nutrition.from_vec(math.hypot(a, b) for a, b in zip(sd.vec(), add.vec()))
        return value, sd

    def suspicious(self, threshold: float = 3.0) -> list[ProductFit]:
        return sorted((f for f in self.fits.values() if f.max_z > threshold), key=lambda f: -f.max_z)

    def to_json(self) -> dict:
        used: dict[str, list[str]] = {}
        for prod, parts in self.recipes.items():
            for cid, n in parts.items():
                used.setdefault(cid, []).append(prod if n == 1 else f"{prod} ×{n:g}")
        return {
            "about": "麦麦健身餐规划师 配料级营养库：由麦当劳中国官方整份营养与配方联合求解（非负贝叶斯最小二乘），"
                     "参考美国麦当劳官网与 USDA 配料数据。value 为估计值，sd 为后验标准差；单位 kcal、g、mg。",
            "units": {"kcal": "大卡", "protein": "g", "fat": "g", "carb": "g", "sodium": "mg", "calcium": "mg"},
            "effective_dof": round(self.dof, 1),
            "components": {cid: {"name": c.name, "basis": c.basis, "identifiability": round(c.identifiability, 3),
                                 "used_in": used.get(cid, []),
                                 "value": dict(zip(NUTRIENTS, (round(v, 1) for v in c.value.vec()))),
                                 "sd": dict(zip(NUTRIENTS, (round(v, 1) for v in c.sd.vec()))),
                                 "prior_source": c.prior_source}
                           for cid, c in self.components.items()},
            "fits": {p: {"max_z": round(f.max_z, 2), "residual": dict(zip(NUTRIENTS, (round(v, 1) for v in f.residual.vec())))}
                     for p, f in self.fits.items()},
        }


@dataclass
class RecipeBook:
    """配方文件 recipes.json：餐品 → {配料: 份数}，外加以下划线开头的说明项。"""
    recipes: dict[str, dict[str, float]]
    fit_exclude: frozenset[str] = frozenset()                                 # 官方数值不自洽：只预测不拟合
    obs_sd: dict[str, dict[str, float]] = field(default_factory=dict)        # 个别餐品个别营养素放宽观测误差
    uncertain: dict[str, dict[str, float]] = field(default_factory=dict)     # 可能还有、但无法确认的配料（最多几份）


def load_recipes(path: Path) -> RecipeBook:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return RecipeBook({k: v for k, v in raw.items() if not k.startswith("_")},
                      frozenset(raw.get("_fit_exclude", [])), raw.get("_obs_sd", {}), raw.get("_uncertain", {}))


def build_library(official: dict[str, Nutrition], recipes: dict[str, dict[str, float]], priors: dict[str, Prior],
                  names: dict[str, str] | None = None, fit_exclude: set[str] | frozenset[str] = frozenset(),
                  obs_sd: dict[str, dict[str, float]] | None = None,
                  uncertain: dict[str, dict[str, float]] | None = None) -> Library:
    """official：营养表（餐品 → 营养）；recipes：配方（餐品 → {配料: 份数}）。
    不在营养表里、或列在 fit_exclude 里（官方数值不自洽）的餐品不参与拟合，只用于预测。
    obs_sd 可以给个别餐品放宽观测误差（如麦辣鸡腿汉堡的钙异常），默认用 OBS_SD。"""
    names = names or {}
    obs_sd = obs_sd or {}
    if fit_exclude:
        official = {k: v for k, v in official.items() if k not in fit_exclude}
    comps = sorted({c for r in recipes.values() for c in r})
    unknown = [c for c in comps if c not in priors]
    if unknown:
        log.info("以下配料没有参考值，使用弱先验：%s", unknown)
    fitted = [p for p in recipes if p in official]
    if not fitted:
        raise ValueError("配方里没有任何餐品出现在官方营养表中")
    log.info("配料库求解：%d 个配料，%d 款有官方数据的餐品", len(comps), len(fitted))
    A = [[recipes[p].get(c, 0.0) for c in comps] for p in fitted]

    est_vals = {c: [0.0] * len(NUTRIENTS) for c in comps}
    est_sds = {c: [0.0] * len(NUTRIENTS) for c in comps}
    ident = {c: 1.0 for c in comps}
    dof = 0.0
    covs: dict[str, list[list[float]]] = {}
    for k, nut in enumerate(NUTRIENTS):
        sys_ = [obs_sd.get(p, {}).get(nut, OBS_SD[nut]) for p in fitted]
        mu = [priors[c].mean.vec()[k] if c in priors else 0.0 for c in comps]
        sc = [max(priors[c].sd.vec()[k], 1e-6) if c in priors else WEAK_PRIOR_SD[nut] for c in comps]
        # 增广系统：观测行按 1/σ_y 加权，先验行按 1/σ_c 加权
        rows = [[a / sy for a in row] for row, sy in zip(A, sys_)]
        rhs = [official[p].vec()[k] / sy for p, sy in zip(fitted, sys_)]
        for j, c in enumerate(comps):
            prow = [0.0] * len(comps)
            prow[j] = 1.0 / sc[j]
            rows.append(prow)
            rhs.append(mu[j] / sc[j])
        x = nnls(rows, rhs)
        cov = spd_inverse(matmul(transpose(rows), rows))
        covs[nut] = cov
        hat_trace = sum(sum(a * cv for a, cv in zip(row, matvec(cov, row))) for row in rows[:len(fitted)])
        dof += len(fitted) - hat_trace
        for j, c in enumerate(comps):
            est_vals[c][k] = x[j]
            est_sds[c][k] = math.sqrt(max(cov[j][j], 0.0))
            if nut == "kcal":
                ident[c] = est_sds[c][k] / sc[j]

    components = {c: ComponentEstimate(c, names.get(c, c), Nutrition.from_vec(est_vals[c]), Nutrition.from_vec(est_sds[c]),
                                       ident[c], priors[c].source if c in priors else "")
                  for c in comps}
    lib = Library(components, {}, recipes, dof, covs, comps, uncertain or {})
    for p in fitted:
        pred, _ = lib.predict(p)
        res = official[p] - pred
        z = {n: r / obs_sd.get(p, {}).get(n, OBS_SD[n]) for n, r in zip(NUTRIENTS, res.vec())}
        lib.fits[p] = ProductFit(p, official[p], pred, res, z)
    bad = lib.suspicious()
    if bad:
        log.warning("残差异常的餐品（配方可能有误）：%s", [(f.product, round(f.max_z, 1)) for f in bad])
    return lib


@dataclass
class Deletion:
    product: str
    chi2_rest: float        # 拿掉这款后，其余餐品的拟合误差（归一化残差平方和）
    z_pred: float           # 用其余餐品求出的配料预测这款，最大的归一化偏差
    deviation: Nutrition


def deletion_diagnostics(official: dict[str, Nutrition], recipes: dict[str, dict[str, float]],
                         priors: dict[str, Prior], fit_exclude: frozenset[str] = frozenset(),
                         obs_sd: dict[str, dict[str, float]] | None = None) -> list[Deletion]:
    """删除诊断：逐个拿掉一款餐品重新求解。
    如果拿掉的正是配方写错的那一款，其余餐品会拟合得很好（chi2_rest 骤降）；拿掉别的则不会。
    按 chi2_rest 升序返回，排第一的是最可疑的配方。"""
    official = {k: v for k, v in official.items() if k not in fit_exclude}
    fitted = [p for p in recipes if p in official]
    lg = logging.getLogger(__name__)
    lvl = lg.level
    lg.setLevel(logging.ERROR)   # 诊断时不重复打印残差警告
    out = []
    try:
        for p in fitted:
            rest = {k: v for k, v in official.items() if k != p}
            lib = build_library(rest, recipes, priors, obs_sd=obs_sd)
            chi2 = sum(z * z for f in lib.fits.values() for z in f.z.values())
            pred, sd = lib.predict(p)
            dev = official[p] - pred
            osd = (obs_sd or {}).get(p, {})
            zp = max(abs(d) / math.sqrt(osd.get(n, OBS_SD[n]) ** 2 + s ** 2) for d, s, n in zip(dev.vec(), sd.vec(), NUTRIENTS))
            out.append(Deletion(p, chi2, zp, dev))
    finally:
        lg.setLevel(lvl)
    return sorted(out, key=lambda d: d.chi2_rest)


def fit_chi2(lib: Library) -> float:
    return sum(z * z for f in lib.fits.values() for z in f.z.values())


def load_priors(path: Path) -> dict[str, Prior]:
    """先验文件格式：{配料 id: {mean: {kcal..}, sd: {kcal..} 或 rel_sd: 0.25, source: ""}}。
    mean 里没写的营养素视为未知：均值 0、标准差取弱先验，绝不当成「确定为 0」。"""
    raw = json.loads(path.read_text(encoding="utf-8"))
    out = {}
    floor_default = {"kcal": 8, "protein": 1, "fat": 1, "carb": 1.5, "sodium": 30, "calcium": 20}
    for cid, p in raw.items():
        means, sds = [], []
        for k in NUTRIENTS:
            if k not in p["mean"]:
                means.append(0.0)
                sds.append(WEAK_PRIOR_SD[k])
                continue
            m = float(p["mean"][k])
            means.append(m)
            if "sd" in p and k in p["sd"]:
                sds.append(float(p["sd"][k]))
            else:
                rel = float(p.get("rel_sd", 0.3))
                floor = p.get("abs_sd_floor", floor_default)
                sds.append(max(abs(m) * rel, float(floor.get(k, floor_default[k]))))
        out[cid] = Prior(Nutrition.from_vec(means), Nutrition.from_vec(sds), p.get("source", ""))
    return out
