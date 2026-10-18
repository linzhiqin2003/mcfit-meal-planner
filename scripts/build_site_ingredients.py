"""给项目主页「装」页的配料散点图准备数据：44 种配料的热量（含误差）和蛋白质，按「肉和蛋 / 面包 / 酱 / 其他」分组。

    python3 scripts/build_site_ingredients.py

输入 data/ingredient_library.json（配料库求解结果，components 里每项有 value 和 sd）。
输出 site/data/ingredients.json：{"about": ..., "groups": {...}, "items": [{id, name, group, kcal, sd, protein}, ...]}
分组按配料 id 的前缀定（GROUPS）；没列到的前缀会报错，免得新配料静默掉进「其他」。
培根单列「其他」：库里是培根蔬萃里的 1 片（25 大卡），和酱挤在同一个角落，圈进肉里会把肉那一圈拉到原点。
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data/ingredient_library.json"
OUT = ROOT / "site/data/ingredients.json"
log = logging.getLogger("site-ingredients")

GROUPS = {
    "meat": ("肉和蛋", ("patty.", "chicken.", "fish.", "egg.", "ham.", "pork.", "sausage.")),
    "bread": ("面包", ("bun.", "wrap.")),
    "sauce": ("酱", ("sauce.", "butter")),
    "other": ("其他", ("cheese.", "veg.", "bacon")),
}


def group_of(cid: str) -> str:
    for g, (_, prefixes) in GROUPS.items():
        if any(cid == p or cid.startswith(p) for p in prefixes):
            return g
    raise ValueError(f"配料 {cid} 没有分组，请在 GROUPS 里补上它的前缀")


def build(lib: dict) -> dict:
    items = []
    for cid, c in sorted(lib["components"].items()):
        v, sd = c["value"], c["sd"]
        items.append({"id": cid, "name": c["name"], "group": group_of(cid), "kcal": round(v["kcal"], 1),
                      "sd": round(sd["kcal"], 1), "protein": round(v["protein"], 1)})
    return {"about": "配料库估计值（data/ingredient_library.json）：kcal 为热量估计、sd 为热量的后验标准差、protein 为蛋白质克数",
            "groups": {g: name for g, (name, _) in GROUPS.items()}, "items": items}


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    data = build(json.loads(SRC.read_text(encoding="utf-8")))
    OUT.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    counts = {g: sum(1 for i in data["items"] if i["group"] == g) for g in GROUPS}
    log.info("%s：%d 种配料 %s，%d 字节", OUT.relative_to(ROOT), len(data["items"]), counts, OUT.stat().st_size)


if __name__ == "__main__":
    main()
