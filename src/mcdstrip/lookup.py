"""单样餐品的几种吃法（gym.py eat）：用户只问「双层吉士汉堡去吉士、只吃馅多少热量」时用，不用配餐，也不需要 Token。

名字先按营养表、配方和门店菜单里的名字精确匹配（归一化后），再找包含关系、按顺序含有这几个字（「双吉」→ 双层吉士汉堡），
最后按字形相近；不唯一时返回候选，让智能体问用户是哪一个。
可去的配料来自门店菜单（单点详情或套餐选项）：没给门店时用安装时带上的门店快照（晚餐、早餐各一份），
各快照合在一起查，早餐才有的麦满分也查得到。营养与求解器同源（compare.eat_ladder）。
"""
from __future__ import annotations

import difflib
import logging
from dataclasses import dataclass, field
from pathlib import Path

from .catalog import Builder, Catalog, estimate_note, load_fixture
from .compare import Rung, eat_ladder
from .nutrition import normalize

log = logging.getLogger(__name__)

MAX_CANDIDATES = 8


@dataclass
class EatLookup:
    name: str                          # 匹配到的餐品（归一化后的营养表名）
    rungs: list[Rung]                  # 全部吃法，按这一顿的热量从高到低；只能整份吃时只有一档
    estimated: bool                    # 不在官方营养表里，整份营养也是配料库估算的
    footnotes: list[str] = field(default_factory=list)


class NotFound(Exception):
    def __init__(self, message: str, candidates: list[str]):
        super().__init__(message)
        self.candidates = candidates


def snapshots(data: Path) -> list[Path]:
    """数据目录里的全部门店快照（每个时段一个目录，含 menu.json）。"""
    return sorted(p.parent for p in (data / "fixtures" / "stores").glob("*/*/menu.json"))


def merged_catalog(cats: list[Catalog]) -> Catalog:
    """把几份菜单合成一份，只用来查可去配料（compare 按名字取配料最多的一处）。"""
    products = {f"{i}/{code}": p for i, c in enumerate(cats) for code, p in c.products.items()}
    return Catalog(products, store_code="")


def load_catalogs(dirs: list[Path]) -> list[Catalog]:
    cats = [load_fixture(d) for d in dirs]
    log.debug("查可去配料用了 %d 份门店快照：%s", len(cats), ", ".join(f"{d.parent.name}/{d.name}" for d in dirs))
    return cats


def known_names(builder: Builder, cat: Catalog) -> set[str]:
    """营养表、配方里的餐品，加上菜单上的单品和套餐选项（归一化后的名字）。"""
    names = set(builder.official) | set(builder.lib.recipes if builder.lib else ())
    for p in cat.products.values():
        names.add(normalize(p.name))
        if p.detail_name:
            names.add(normalize(p.detail_name))
        for r in p.rounds:
            names.update(normalize(ch.name) for ch in r.choices)
    return names


def _in_order(q: str, name: str) -> bool:
    """name 按顺序含有 q 的每个字：「双吉」→「双层吉士汉堡」。"""
    it = iter(name)
    return all(ch in it for ch in q)


def resolve(query: str, names: set[str], fuzzy: bool = True) -> list[str]:
    """按匹配强弱依次尝试，命中就返回（短名在前）：精确 → 包含 → 按顺序含有 → 字形相近（fuzzy 时）。"""
    q = normalize(query.strip())
    if q in names:
        return [q]
    for match in (lambda n: q in n, lambda n: _in_order(q, n)):
        hits = sorted((n for n in names if match(n)), key=lambda n: (len(n), n))
        if hits:
            return hits
    return difflib.get_close_matches(q, sorted(names), n=MAX_CANDIDATES, cutoff=0.5) if fuzzy else []


def _pick(builder: Builder, cat: Catalog, query: str) -> str:
    """先在算得出营养的餐品里找；是套餐或算不准的餐品时说清楚原因；都不像时给几个字形相近的候选。"""
    q = normalize(query.strip())
    if builder.base_nutrition(q) is not None:        # 含按块数换算的（麦乐鸡10块 = 2 × 5块）
        return q
    names = known_names(builder, cat)
    computable = {n for n in names if builder.base_nutrition(n) is not None}
    hits = [] if q in names else resolve(query, computable, fuzzy=False)
    if len(hits) == 1:
        return hits[0]
    if hits:
        shown = hits[:MAX_CANDIDATES]
        raise NotFound(f"「{query}」对应好几样餐品，请确认是哪一个：{'、'.join(shown)}。", shown)
    others = resolve(query, names - computable, fuzzy=False)[:MAX_CANDIDATES]
    if others:
        raise NotFound(f"{'、'.join(others)}：是套餐，或不在官方营养表里、按配方也估不准，算不了吃法。"
                       f"套餐请分别查里面的单品。", [])
    close = resolve(query, computable)
    if close:
        raise NotFound(f"没找到「{query}」，是不是这几样：{'、'.join(close)}？", close)
    raise NotFound(f"营养表和菜单里都没有「{query}」，换个说法试试（用菜单上的全名最准）。", [])


def lookup(builder: Builder, cat: Catalog, query: str) -> EatLookup:
    name = _pick(builder, cat, query)
    rungs = eat_ladder(builder, cat, name, max_rungs=99)
    plans = builder.eat_plans(name, (), allow_split=False)
    if not rungs:       # 没有可去的配料，也没有面包可留：只能整份吃
        rungs = [Rung(p.note, p.tonight, p.leftover) for p in plans[:1]]
    estimated = bool(plans) and plans[0].estimate_sd > 0
    notes = list(estimate_note(name, plans[0])) if estimated else []
    if any(r.leftover.kcal > 0 for r in rungs):
        notes.append("「面包留到下一顿」的热量包括夹在面包上的酱和菜（下单去掉的除外）。")
    log.info("吃法查询：%s → %s，%d 种吃法", query, name, len(rungs))
    return EatLookup(name, rungs, estimated, notes)
