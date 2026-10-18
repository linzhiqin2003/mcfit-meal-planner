"""采集离线快照：官方营养表、工具定义、若干门店若干时段的菜单与全部餐品详情。

快照用于离线开发、单元测试和无 Token 演示。用法：
    MCD_MCP_TOKEN=... python3 scripts/capture_fixtures.py --store 1450441 --store 1450182002 \
        --slot 2026-10-16T12:00 --slot 2026-10-16T19:00
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from mcdstrip.mcp import McdBusinessError, McdMcp  # noqa: E402

log = logging.getLogger("capture")
OUT = ROOT / "data" / "fixtures"


def dump(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def capture_store(m: McdMcp, store: str, slot: str) -> dict:
    rd = slot.replace("T", " ")
    base = dict(storeCode=store, orderType=1, beType=1, reservationDate=rd)
    menu = m.data("query-meals", **base)
    d = OUT / "stores" / store / slot.replace(":", "")
    dump(d / "menu.json", menu)
    codes = list(menu["meals"].keys())

    def one(code: str):
        try:
            return code, m.data("query-meal-detail", **base, code=code), None
        except McdBusinessError as e:
            return code, None, f"{e.code} {e.message}"

    fails = {}
    with ThreadPoolExecutor(4) as ex:
        for code, detail, err in ex.map(one, codes):
            if detail is None:
                fails[code] = err
            else:
                dump(d / "details" / f"{code}.json", detail)
    log.info("门店 %s 时段 %s：菜单 %d，详情成功 %d，失败 %d", store, slot, len(codes), len(codes) - len(fails), len(fails))
    return dict(store=store, slot=slot, items=len(codes), detail_failures=fails)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--store", action="append", required=True)
    ap.add_argument("--slot", action="append", required=True, help="预约时间，格式 YYYY-MM-DDTHH:MM")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    m = McdMcp()
    now = m.data("now-time-info")["formatted"]
    dump(OUT / "tools.json", m.tools())
    raw = m.data("list-nutrition-foods")
    (OUT / "nutrition_raw.txt").write_text(raw, encoding="utf-8")
    stores_meta = {}
    for s in a.store:
        info = None
        stores_meta[s] = [capture_store(m, s, slot) for slot in a.slot]
    dump(OUT / "meta.json", dict(captured_at=now, local_time=datetime.now().isoformat(timespec="seconds"),
                                 calls=m.calls, stores=stores_meta))
    log.info("完成，共调用 %d 次", m.calls)


if __name__ == "__main__":
    main()
