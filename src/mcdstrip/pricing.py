"""算价接口（calculate-price）参数构造与核价。

特制参数的传法（参赛者 mcd-safe-bite 与我们实测一致）：同一组配料要全部传，
保留的传 selectedKey、数量 1；去掉的传 unselectedKey、数量 0。漏传会被静默恢复成默认配置。
"""
from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass

from .catalog import Catalog, Modifier
from .mcp import McdMcp
from .solver import Plan

log = logging.getLogger(__name__)


def modification(modifiers: tuple[Modifier, ...], removed: tuple[str, ...]) -> dict | None:
    if not removed:
        return None
    unknown = set(removed) - {m.name for m in modifiers}
    if unknown:
        raise ValueError(f"这些配料不在可去清单里：{sorted(unknown)}")
    return {"values": [{"code": m.code, "quantity": 0 if m.name in removed else 1,
                        "key": m.unselected_key if m.name in removed else m.selected_key} for m in modifiers]}


def items_for(plan: Plan, cat: Catalog) -> list[dict]:
    """把方案转成 calculate-price / create-order 的 items（相同配置合并数量）。"""
    counts = Counter(o.payload for o in plan.options)
    items = []
    for payload, qty in counts.items():
        kind, code = payload[0], payload[1]
        prod = cat.products[code]
        if kind == "single":
            item = {"productCode": code, "quantity": qty}
            mod = modification(prod.modifiers, payload[2])
            if mod:
                item["modification"] = mod
        else:
            # 每组选够规定份数；同一组里相同配置（同一项、去掉的配料相同）合并成一条并累计数量
            rounds = {r.id: r for r in prod.rounds}
            per_round: dict[int, Counter] = {}
            for rid, ch_code, removed, _split in payload[2]:
                per_round.setdefault(rid, Counter())[(ch_code, removed)] += 1
            round_list = []
            for rid, entries in per_round.items():
                combo_items = []
                for (ch_code, removed), n in entries.items():
                    ch = next(c for c in rounds[rid].choices if c.code == ch_code)
                    entry = {"code": ch_code, "quantity": n}
                    mod = modification(ch.modifiers, removed)
                    if mod:
                        entry["modification"] = mod
                    combo_items.append(entry)
                round_list.append({"round": rid, "comboItemList": combo_items})
            item = {"productCode": code, "quantity": qty, "roundList": round_list}
        items.append(item)
    return items


@dataclass
class PriceCheck:
    predicted_cents: int
    actual_cents: int | None
    code: object
    message: str

    @property
    def ok(self) -> bool:
        return self.actual_cents is not None and self.actual_cents == self.predicted_cents


def verify(m: McdMcp, cat: Catalog, plan: Plan, order_type: int = 1, be_type: int = 1,
           reservation: str | None = None) -> PriceCheck:
    args = dict(storeCode=cat.store_code, orderType=order_type, beType=be_type, items=items_for(plan, cat))
    if reservation:
        args["reservationDate"] = reservation
    sc = m.call("calculate-price", **args)
    data = sc.get("data") or {}
    actual = data.get("price")
    res = PriceCheck(plan.price_cents, int(actual) if actual is not None else None, sc.get("code"), sc.get("message", ""))
    log.info("核价：预测 %s 分，接口 %s 分（%s %s）", res.predicted_cents, res.actual_cents, res.code, res.message)
    return res
