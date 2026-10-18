"""核价记录：三组约束各取前 3 个方案，用 calculate-price 核对预测价，结果存成不含 Token 的 JSON。

用法（需要已设置 MCD_MCP_TOKEN）：
    python3 scripts/price_check_record.py                      # 上海人民广场附近
    python3 scripts/price_check_record.py --city 北京 --near 西单

输出 docs/research/price_check_<日期>.json，并打印「预测价与接口价一致 N/M」。
记录里只有门店、约束、下单明细和两个价格，写盘前确认不含 Token。
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GYM = ROOT / "skill" / "maimen-gym" / "scripts" / "gym.py"
CASES = [
    {"kcal_max": 400, "protein_min": 30, "train": None},
    {"kcal_max": 500, "protein_min": 30, "train": "练腿"},
    {"kcal_max": 650, "protein_min": 40, "train": "练胸"},
]


def _redact(text: str, token: str) -> str:
    return text.replace(token, "***") if token else text


def run_case(case: dict, city: str, near: str, token: str) -> dict:
    """跑一组约束；脚本崩溃、超时、输出不是 JSON 时记为这一组失败（诊断去掉 Token 后保留最后几行）。"""
    args = ["plan", "--kcal-max", str(case["kcal_max"]), "--protein-min", str(case["protein_min"]),
            "--city", city, "--near", near, "--top", "3", "--format", "json", "--verify"]
    if case["train"]:
        args += ["--train", case["train"]]
    try:
        r = subprocess.run([sys.executable, str(GYM), *args], capture_output=True, timeout=900)
        out = json.loads(r.stdout.decode("utf-8"))
    except subprocess.TimeoutExpired:
        return {"args": args, "error": "超过 15 分钟没有结果"}
    except (ValueError, UnicodeDecodeError):
        tail = "\n".join(r.stderr.decode("utf-8", "replace").strip().splitlines()[-5:])
        return {"args": args, "error": f"脚本没有输出 JSON（退出码 {r.returncode}）", "stderr_tail": _redact(tail, token)}
    if not out.get("ok"):
        return {"args": args, "error": out.get("error")}
    return {
        "args": args,
        "store": out.get("store"),
        "plans": [{"rank": p["rank"], "predicted_yuan": p["price_yuan"],
                   "actual_yuan": (p["price_check"] or {}).get("actual_yuan"),
                   "match": bool(p["price_check"] and p["price_check"]["ok"]),
                   "message": (p["price_check"] or {}).get("message"),
                   "order_lines": p["order_lines"], "calculate_price_items": p["calculate_price_items"]}
                  for p in out["plans"]],
    }


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="生成不含 Token 的核价记录")
    ap.add_argument("--city", default="上海")
    ap.add_argument("--near", default="人民广场")
    a = ap.parse_args()
    token = os.environ.get("MCD_MCP_TOKEN")
    if not token:
        print("需要先设置环境变量 MCD_MCP_TOKEN（方法见 README）。", file=sys.stderr)
        return 1
    now = datetime.now()
    cases = [run_case(c, a.city, a.near, token) for c in CASES]
    plans = [p for c in cases for p in c.get("plans", [])]
    matched = sum(p["match"] for p in plans)
    failed = sum("error" in c for c in cases)
    summary = f"预测价与接口价一致 {matched}/{len(plans)}" + (f"；{failed}/{len(cases)} 组约束没跑成" if failed else "")
    record = {"generated_at": now.isoformat(timespec="seconds"), "city": a.city, "near": a.near,
              "summary": summary, "cases": cases}
    text = json.dumps(record, ensure_ascii=False, indent=1)
    if token in text:      # 双保险：记录里绝不能出现 Token
        print("记录里出现了 Token，已放弃写入。", file=sys.stderr)
        return 1
    path = ROOT / "docs" / "research" / f"price_check_{now:%Y-%m-%d}.json"
    path.write_text(text + "\n", encoding="utf-8")
    print(f"{record['summary']}，已写入 {path.relative_to(ROOT)}")
    for c in cases:
        if "error" in c:
            print(f"  {' '.join(c['args'][1:5])}：{c['error']}")
    return 0 if not failed and plans and matched == len(plans) else 2


if __name__ == "__main__":
    sys.exit(main())
