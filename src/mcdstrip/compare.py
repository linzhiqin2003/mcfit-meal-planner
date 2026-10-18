"""差异化信息：官方菜单给不了的「可能性」。

麦当劳 App 自己有「500 大卡套餐」这类固定组合，只能整份吃。这里给出它给不了的两样：

1. 同一份餐品的几种吃法（eat_ladder）：整份 / 下单去配料（去酱、去芝士）/ 到手只吃馅、面包留到下一顿（分餐），
   以及它们的组合，各自这一顿吃进去多少、留到下一顿多少。营养与求解器同源（Builder.eat_plans）。
2. 门店的官方「N 大卡套餐」（official_sets）：整份吃的营养、能否满足用户的目标，以及每一样都按最低热量的
   吃法拆开后能降到多少。套餐的组成按每组第一个选项（菜单上的默认项）计算。
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from .catalog import Builder, Catalog, Choice, Modifier
from .nutrition import Nutrition, negligible, normalize
from .solver import Constraints

log = logging.getLogger(__name__)

KCAL_SET = re.compile(r"(\d+)\s*大卡")


@dataclass(frozen=True)
class Rung:
    """一种吃法。"""
    how: str                      # 「整份吃」「下单去麦香鸡酱」「到手只吃馅，面包留到下一顿」……
    tonight: Nutrition
    leftover: Nutrition
    chosen: bool = False          # 这次方案用的就是这种


@dataclass(frozen=True)
class OfficialSet:
    name: str
    category: str                 # 「500大卡套餐」
    price_cents: int
    whole: Nutrition              # 整份吃
    lowest: Nutrition             # 每一样都按热量最低的吃法
    lowest_leftover: Nutrition
    lowest_hows: tuple[str, ...]  # 最低热量吃法里非「整份吃」的那几样，如「麦香鱼：下单去麦香鱼酱，到手只吃馅」
    fits_whole: bool              # 整份吃就满足用户的热量上限和蛋白质下限


def _modifiers_for(cat: Catalog, name: str) -> tuple[Modifier, ...]:
    """找到这样餐品可去的配料：单点的看自身，套餐里的看那一组选项；取配料最多的一处（有的套餐不让改）。"""
    n = normalize(name)
    best: tuple[Modifier, ...] = ()
    for p in cat.products.values():
        if not p.is_combo:
            if normalize(p.name) == n or normalize(p.detail_name or "") == n:
                if len(p.modifiers) > len(best):
                    best = p.modifiers
            continue
        for r in p.rounds:
            for ch in r.choices:
                if normalize(ch.name) == n and ch.support_modify and len(ch.modifiers) > len(best):
                    best = ch.modifiers
    return best


def eat_ladder(builder: Builder, cat: Catalog, name: str, chosen_how: str = "", max_rungs: int = 5) -> list[Rung]:
    """一样餐品的全部吃法，按这一顿的热量从高到低。只有一种吃法（整份吃）时返回空列表。"""
    plans = builder.eat_plans(name, _modifiers_for(cat, name), allow_split=True)
    if len(plans) < 2:
        return []
    seen, out = set(), []
    # 这一顿吃进去的一样就算同一档（只吃馅时去不去酱只影响留下的面包），留下得少的那个在前、优先保留
    for ep in sorted(plans, key=lambda e: (-round(e.tonight.kcal), e.leftover.kcal, e.note)):
        key = (round(ep.tonight.kcal), round(ep.tonight.protein))
        if key in seen:
            continue
        seen.add(key)
        out.append(Rung(ep.note, ep.tonight, ep.leftover, chosen=ep.note == chosen_how))
    if chosen_how and not any(r.chosen for r in out):
        # 被合并掉的那个恰好是方案用的：换成方案那一种，标成本方案
        for i, r in enumerate(out):
            ep = next((e for e in plans if e.note == chosen_how and round(e.tonight.kcal) == round(r.tonight.kcal)), None)
            if ep is not None:
                out[i] = Rung(ep.note, ep.tonight, ep.leftover, True)
                break
    if len(out) > max_rungs:
        # 太多档（巨无霸有 8 种）：保留整份、本方案、热量最低的一档，其余按热量均匀挑
        keep = {0, len(out) - 1} | {i for i, r in enumerate(out) if r.chosen}
        rest = [i for i in range(len(out)) if i not in keep]
        step = max(1, len(rest) // max(1, max_rungs - len(keep)))
        keep |= set(rest[::step][:max(0, max_rungs - len(keep))])
        out = [r for i, r in enumerate(out) if i in keep]
    return out


def _default_choice(choices: tuple[Choice, ...]) -> Choice:
    return choices[0]


def official_sets(builder: Builder, cat: Catalog, c: Constraints) -> list[OfficialSet]:
    """门店菜单里「N 大卡套餐」分类下的套餐。营养算不出来的套餐跳过（记日志）。"""
    out = []
    for cname, codes in cat.categories.items():
        if not KCAL_SET.search(cname):
            continue
        for code in codes:
            p = cat.products.get(code)
            if p is None or not p.is_combo:
                continue
            whole, low, low_left, hows, ok = Nutrition(), Nutrition(), Nutrition(), [], True
            for r in p.rounds:
                ch = _default_choice(r.choices)
                plans = builder.eat_plans(ch.name, ch.modifiers if ch.support_modify else (), allow_split=True)
                if not plans:
                    log.info("官方套餐 %s：%s 缺营养数据，跳过", p.name, ch.name)
                    ok = False
                    break
                best = min(plans, key=lambda e: (e.tonight.kcal, -e.tonight.protein))
                for _ in range(r.quantity):
                    whole = whole + plans[0].tonight
                    low, low_left = low + best.tonight, low_left + best.leftover
                if best.note != "整份吃" and not negligible(plans[0].tonight - best.tonight):
                    hows.append(f"{normalize(ch.name)}：{best.note}")
            if not ok:
                continue
            fits = whole.kcal <= c.kcal_max + 1e-9 and whole.protein >= c.protein_min - 1e-9
            out.append(OfficialSet(p.name, re.sub(r"\s+", "", cname), p.price_cents, whole, low, low_left,
                                   tuple(hows), fits))
    return out
