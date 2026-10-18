"""给项目主页预先算好一批方案：热量上限 × 蛋白质下限 × 训练部位，全部用门店快照离线求解，不需要 Token。

    python3 scripts/build_site_data.py [--jobs 6]

输出 site/data/plans.json：
  {"store": {...}, "snapshot": "...", "grid": {"kcal": [...], "protein": [...], "train": [...]},
   "plans": {"500|30|练腿": {"ok": true, "plans": [ {price, this_meal, next_meal, rows, order_lines, tip}, ... ]}, ...}}
rows 是训练卡上的「动作」行（名称、每组、组数、吃法），从 render_gym 的卡片文字解析出来，去掉了 emoji。
每个组合单独起一个子进程跑 `mcdstrip plan --format json`，进程池并行；失败的组合记下错误、不中断整体。
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / "data/fixtures/stores/1450441/2026-10-16T1900"
OUT = ROOT / "site/data/plans.json"
KCAL = [400, 500, 600, 700, 800]
PROTEIN = [20, 30, 40]
TRAIN = ["", "练腿", "练胸", "练背", "练手臂"]       # "" = 不限部位
log = logging.getLogger("site-data")

ROW = re.compile(r"^\W*(?P<name>[^：\n]+)：(?P<per>[^，]+)，共 (?P<sets>\d+) 组(?:（(?P<how>.+)）)?$")


def run_one(kcal: int, protein: int, train: str) -> tuple[str, dict]:
    key = f"{kcal}|{protein}|{train}"
    args = [sys.executable, "-c", "import sys; from mcdstrip.cli import main; sys.exit(main(sys.argv[1:]))",
            "plan", "--kcal-max", str(kcal), "--protein-min", str(protein), "--style", "gym", "--format", "json",
            "--top", "3", "--offline", str(SNAPSHOT)]
    if train:
        args += ["--train", train]
    t0 = time.time()
    r = subprocess.run(args, capture_output=True, text=True, timeout=300,
                       env={**os.environ, "PYTHONPATH": str(ROOT / "src")})
    try:
        d = json.loads(r.stdout)
    except json.JSONDecodeError:
        log.warning("%s 出错（%.1fs）：%s", key, time.time() - t0, r.stderr.strip()[-300:])
        return key, {"ok": False, "error": "solver_failed"}
    if not d.get("ok"):   # 无解是正常结果（例如这家店没有里脊），把给用户看的说明存下来
        log.info("%s 无解（%.1fs）：%s", key, time.time() - t0, d.get("error"))
        return key, {"ok": False, "message": d.get("error")}
    log.info("%s → %s 个方案（%.1fs）", key, len(d.get("plans") or []), time.time() - t0)
    return key, compact(d)


def parse_rows(card: str) -> tuple[list[dict], str | None]:
    rows, tip = [], None
    for line in card.splitlines():
        line = line.strip()
        if line.startswith("动作要领："):
            tip = line.split("：", 1)[1]
            continue
        m = ROW.match(line)
        if m:
            rows.append({"name": m["name"].strip(), "per_set": m["per"].strip(), "sets": int(m["sets"]),
                         "how": (m["how"] or "").strip()})
    return rows, tip


def compact(d: dict) -> dict:
    out = {"ok": bool(d.get("ok")), "notice": d.get("notice"), "plans": []}
    for p in d.get("plans") or []:
        rows, tip = parse_rows(p.get("card", ""))
        out["plans"].append({
            "price": p["price_yuan"], "this_meal": p["this_meal"], "next_meal": p.get("next_meal"),
            "rows": rows, "tip": tip, "order_lines": p.get("order_lines", []),
            "estimated": bool(p.get("footnotes")), "footnotes": p.get("footnotes", []),
        })
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=6)
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    meta = json.loads((SNAPSHOT / "meta.json").read_text(encoding="utf-8")) if (SNAPSHOT / "meta.json").exists() else {}
    combos = [(k, p, t) for k in KCAL for p in PROTEIN for t in TRAIN]
    plans: dict[str, dict] = {}
    t0 = time.time()
    with ThreadPoolExecutor(a.jobs) as ex:
        futs = [ex.submit(run_one, *c) for c in combos]
        for f in as_completed(futs):
            k, v = f.result()
            plans[k] = v
    ok = sum(1 for v in plans.values() if v.get("ok") and v.get("plans"))
    log.info("完成 %d 组，有方案 %d 组，用时 %.0fs", len(plans), ok, time.time() - t0)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"snapshot": SNAPSHOT.name, "store": meta.get("store") or meta,
                               "grid": {"kcal": KCAL, "protein": PROTEIN, "train": TRAIN},
                               "plans": dict(sorted(plans.items()))}, ensure_ascii=False, separators=(",", ":")),
                   encoding="utf-8")
    log.info("写入 %s（%.0f KB）", OUT, OUT.stat().st_size / 1024)


if __name__ == "__main__":
    main()
