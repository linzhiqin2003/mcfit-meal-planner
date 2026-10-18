"""配料库拟合报告：联合求解 + 删除诊断，输出 Markdown，供人工审核配方。

用法：python3 scripts/fit_report.py [配方 JSON] [先验 JSON] > docs/research/fit_report.md
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from mcdstrip.library import build_library, deletion_diagnostics, fit_chi2, load_priors, load_recipes  # noqa: E402
from mcdstrip.nutrition import parse_table  # noqa: E402


def main() -> None:
    recipes_path = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data/reference/recipes.json"
    priors_path = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "data/reference/priors_us.json"
    table = parse_table((ROOT / "data/fixtures/nutrition_raw.txt").read_text(encoding="utf-8"))
    book = load_recipes(recipes_path)
    recipes, exclude = book.recipes, book.fit_exclude
    priors = load_priors(priors_path)
    import json
    names = json.loads((ROOT / "data/reference/component_names.json").read_text(encoding="utf-8"))
    lib = build_library(table, recipes, priors, names=names, fit_exclude=exclude, obs_sd=book.obs_sd,
                        uncertain=book.uncertain)
    fitted = [p for p in recipes if p in table and p not in exclude]
    print(f"# 配料库拟合报告\n\n配方 {len(recipes)} 款（其中 {len(fitted)} 款有官方营养），配料 {len(lib.components)} 个，"
          f"总拟合误差 χ² = {fit_chi2(lib):.1f}，有效自由度 {lib.dof:.1f}（χ² 明显大于自由度说明有配方或数据不对）。\n")
    print("## 配料\n\n| 配料 | id | 大卡 | ± | 蛋白 | 脂肪 | 碳水 | 钠 | 钙 | 依据 |\n|---|---|---|---|---|---|---|---|---|---|")
    for c in sorted(lib.components.values(), key=lambda c: c.id):
        v = c.value
        print(f"| {c.name} | {c.id} | {v.kcal:.0f} | {c.sd.kcal:.0f} | {v.protein:.1f} | {v.fat:.1f} | {v.carb:.1f} | {v.sodium:.0f} | {v.calcium:.0f} | {c.basis} |")
    print("\n## 餐品拟合（按最大 z 降序）\n\n| 餐品 | 最大 z | 残差（大卡/蛋白/脂肪/碳水/钠/钙） |\n|---|---|---|")
    for f in sorted(lib.fits.values(), key=lambda f: -f.max_z):
        print(f"| {f.product} | {f.max_z:.1f} | " + " / ".join(f"{x:+.0f}" for x in f.residual.vec()) + " |")
    print("\n## 删除诊断（拿掉后其余餐品拟合误差，越小越可疑）\n\n| 餐品 | 拿掉后其余 χ² | 预测偏差 z |\n|---|---|---|")
    for d in deletion_diagnostics(table, recipes, priors, exclude, book.obs_sd)[:12]:
        print(f"| {d.product} | {d.chi2_rest:.1f} | {d.z_pred:.1f} |")
    if exclude:
        print("\n## 排除在拟合之外的餐品（官方数值与同系列不自洽）\n\n| 餐品 | 官方大卡 | 配料库预测 | ± | z |\n|---|---|---|---|---|")
        for p in sorted(exclude & set(table)):
            n, sd = lib.predict(p)
            z = (table[p].kcal - n.kcal) / max(sd.kcal, 1e-9)
            print(f"| {p} | {table[p].kcal:.0f} | {n.kcal:.0f} | {sd.kcal:.0f} | {z:+.1f} |")
    preds = [p for p in recipes if p not in table]
    if preds:
        print("\n## 不在营养表里的餐品（由配料库预测）\n\n| 餐品 | 大卡 | ± | 蛋白 | 碳水 |\n|---|---|---|---|---|")
        for p in preds:
            n, sd = lib.predict(p)
            print(f"| {p} | {n.kcal:.0f} | {sd.kcal:.0f} | {n.protein:.1f} | {n.carb:.1f} |")


if __name__ == "__main__":
    main()
