"""约束求解：在热量上限、蛋白质下限等约束下，找出最便宜的点法组合。

输入是一组「选项」（Option）：一个可购买的商品配置（单品或套餐的某种选法）加上一种吃法
（整份、下单去配料、到手自拆）。每个选项有价格、今晚吃进去的营养、留到下一顿的营养。

算法：选项按价格升序做分支定界深度优先搜索，允许同一选项重复（有上限），用三种下界剪枝：
  1. 价格：已选价格加上当前选项价格超过第 k 名，后面的选项更贵，直接停止；
  2. 蛋白质所需花费：还差的蛋白质 ÷ 剩余选项里最高的「每元蛋白」，得到最少还要花的钱；
  3. 蛋白质所需热量：还差的蛋白质 ÷ 剩余选项里最高的「每大卡蛋白」，超过剩余热量额度即不可行。
返回前 k 个互不相同的组合（按价格，其次蛋白质多、热量低）。
"""
from __future__ import annotations

import bisect
import logging
from dataclasses import dataclass, field
from operator import le

from .meal import meal_target, role_vec
from .nutrition import Nutrition

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Item:
    """选项里的一样餐品（单品就是它自己，套餐是每组选中的那一样）。"""
    name: str
    how: str                      # 吃法：「整份吃」「下单去吉士」「到手只吃馅，面包留到下一顿」等
    tonight: Nutrition
    single: bool = False          # 单点（不是套餐里带的）


@dataclass(frozen=True)
class Option:
    id: str                       # 唯一标识，例如 "9900013304|双层吉士汉堡+无糖可口可乐中杯|split"
    label: str                    # 给人看的描述
    price_cents: int
    tonight: Nutrition            # 今晚吃进去的
    leftover: Nutrition = Nutrition()   # 留到下一顿的
    tags: frozenset[str] = frozenset()
    payload: tuple = ()           # 构造算价参数用的不可变描述，由 pricing 解释
    tag_protein: tuple = ()       # 按标签拆分的蛋白质，如 (("练胸", 9.0),)；套餐按每一样餐品分别计算
    footnotes: tuple[str, ...] = ()   # 需要向用户说明的事项（如营养为估算）
    items: tuple[Item, ...] = ()      # 逐样餐品明细，供展示与方案去重


@dataclass(frozen=True)
class Constraints:
    kcal_max: float
    protein_min: float = 0.0
    carb_max: float | None = None
    fat_max: float | None = None
    sodium_max: float | None = None
    budget_cents: int | None = None
    max_items: int = 4
    max_copies: int = 2
    require_tags: frozenset[str] = frozenset()   # 每个组合至少包含一个带这些标签之一的选项（如「练腿」）
    tag_protein_share: float = 0.0               # 带标签选项贡献的蛋白质至少占这么多（如练胸日 0.5：主要靠鸡胸）
    meal: tuple = ()                             # 一餐的结构，如 (("burger", 1), ("drink", 1), ("side", 1))：恰好这么多（meal.parse_meal）


@dataclass(order=True)
class Plan:
    sort_key: tuple
    options: tuple[Option, ...] = field(compare=False)

    @property
    def price_cents(self) -> int:
        return sum(o.price_cents for o in self.options)

    @property
    def tonight(self) -> Nutrition:
        total = Nutrition()
        for o in self.options:
            total = total + o.tonight
        return total

    @property
    def leftover(self) -> Nutrition:
        total = Nutrition()
        for o in self.options:
            total = total + o.leftover
        return total

    @property
    def footnotes(self) -> list[str]:
        return list(dict.fromkeys(f for o in self.options for f in o.footnotes))

    def counts(self) -> list[tuple[Option, int]]:
        out: dict[str, list] = {}
        for o in self.options:
            out.setdefault(o.id, [o, 0])[1] += 1
        return [(o, n) for o, n in out.values()]


def _within(c: Constraints, n: Nutrition, price: int) -> bool:
    if n.kcal > c.kcal_max + 1e-9:
        return False
    if c.carb_max is not None and n.carb > c.carb_max + 1e-9:
        return False
    if c.fat_max is not None and n.fat > c.fat_max + 1e-9:
        return False
    if c.sodium_max is not None and n.sodium > c.sodium_max + 1e-9:
        return False
    if c.budget_cents is not None and price > c.budget_cents:
        return False
    return True


def option_roles(o: Option) -> tuple[int, int, int]:
    """选项里（汉堡, 小食, 饮料）各几样；套餐按里面的每一样餐品算。"""
    return role_vec([it.name for it in o.items] or [o.label])


def is_minimal(sel: tuple[Option, ...], c: Constraints) -> bool:
    """最小性：去掉任何一项后都不再满足蛋白质目标、标签要求或部位占比，否则说明这一项是多余的。
    去掉一项只会让热量、碳水、脂肪、钠、价格变少，上限类约束不会因此被违反，所以只需检查下限类条件。"""
    if len(sel) == 1:
        return True
    target = meal_target(c.meal) if c.meal else None
    total = sum(o.tonight.protein for o in sel)
    share = c.tag_protein_share if c.require_tags else 0.0
    tagged = sum(v for o in sel for tag, v in o.tag_protein if tag in c.require_tags) if share > 0 else 0.0
    for i, o in enumerate(sel):
        rest = sel[:i] + sel[i + 1:]
        if target is not None and tuple(map(sum, zip(*(option_roles(x) for x in rest)))) != target:
            continue                                   # 去掉它就凑不齐这一餐的结构（如饮料），不算多余
        rest_total = total - o.tonight.protein
        if rest_total < c.protein_min - 1e-9:
            continue
        if c.require_tags and not any(x.tags & c.require_tags for x in rest):
            continue
        if share > 0:
            rest_tagged = tagged - sum(v for tag, v in o.tag_protein if tag in c.require_tags)
            if rest_total <= 0 or rest_tagged / rest_total < share - 1e-9:
                continue
        return False
    return True


def _dom_vec(o: Option, c: Constraints | None = None) -> tuple:
    """越小越好的向量：价格、−蛋白、热量、碳水、脂肪、钠、留存热量（与排序一致：同价同营养时留存越清淡越好）、−各部位蛋白；
    有部位占比要求时再加 −(部位蛋白 − 占比 × 总蛋白)：蛋白更多但部位占比更低的选项不能算支配者。"""
    t = o.tonight
    v = (o.price_cents, -t.protein, t.kcal, t.carb, t.fat, t.sodium, o.leftover.kcal) + tuple(-x for _, x in o.tag_protein)
    if c is not None and c.require_tags and c.tag_protein_share > 0:
        tagged = sum(x for tag, x in o.tag_protein if tag in c.require_tags)
        v += (-(tagged - c.tag_protein_share * t.protein),)
    return v


def dominated_filter(options: list[Option], c: Constraints | None = None) -> list[Option]:
    """去掉被支配的选项：存在另一个同标签的选项价格不高、蛋白不少、热量/碳水/脂肪/钠都不多、留存不少、
    各部位蛋白也不少（否则替换后可能达不到部位占比）。被支配的选项不可能出现在「最便宜」的最优解里。

    算法是「排序 + 天际线」：同组内按向量字典序排好，支配者一定排在被支配者前面；只和已保留的比。

    份数上限：方案里同一选项最多 max_copies 份，支配者用满了就不能再顶替。所以一个选项要被至少
    need 个不同的已保留选项支配才删，need 取「其余位置都占满支配者份数时仍有一个支配者有空位」的最小值。"""
    max_items = c.max_items if c is not None else 4
    max_copies = c.max_copies if c is not None else 2
    need = (max_items - 1) // max(max_copies, 1) + 1
    groups: dict[tuple, list[Option]] = {}
    meal = bool(c is not None and c.meal)
    for o in options:
        # 有一餐结构要求时，类别不同的选项不能互相替代（便宜的饮料顶替不了汉堡）
        key = (o.tags, tuple(t for t, _ in o.tag_protein)) + ((option_roles(o),) if meal else ())
        groups.setdefault(key, []).append(o)
    keep: list[Option] = []
    for group in groups.values():
        sky: list[tuple[tuple, Option]] = []
        for v, o in sorted(((_dom_vec(o, c), o) for o in group), key=lambda x: (x[0], x[1].id)):
            hits = 0
            for sv, _ in sky:
                if all(map(le, sv, v)):
                    hits += 1
                    if hits >= need:
                        break
            if hits < need:
                sky.append((v, o))
        keep.extend(o for _, o in sky)
    log.debug("支配过滤：%d → %d", len(options), len(keep))
    return keep


def solve(options: list[Option], c: Constraints, top_k: int = 5, prune_dominated: bool = True,
          distinct_key=None) -> list[Plan]:
    """按价格（其次蛋白多、热量少、留存清淡）返回前 top_k 个方案。
    给了 distinct_key（方案 → 可哈希的「实质」）时，实质相同的方案只留最好的一个，前 k 名按去重后计；
    这样第 k 名的价格能更早收紧，剪枝效果远好于先多求再去重。"""
    # 先按上限类约束筛（与支配无关：支配者在每个上限维度都不更大，筛掉被支配者不会误删支配者），再做支配过滤
    neg = [o.id for o in options if min(o.tonight.vec()) < 0]
    if neg:   # 搜索的剪枝依赖「多加一样只会更多」，负营养会让它漏掉可行解
        raise ValueError(f"选项营养不能为负：{neg[:3]}")
    opts = [o for o in options if o.price_cents > 0 and _within(c, o.tonight, o.price_cents)]
    target = meal_target(c.meal) if c.meal else None
    if target is not None:   # 单个选项就超出结构的（如两个汉堡的套餐）用不上
        opts = [o for o in opts if all(a <= b for a, b in zip(option_roles(o), target))]
    if prune_dominated:
        opts = dominated_filter(opts, c)
    opts.sort(key=lambda o: (o.price_cents, -o.tonight.protein, o.id))
    n = len(opts)
    if not n:
        return []
    # 热路径用元组运算：(热量, 蛋白, 碳水, 脂肪, 钠)
    vec = [(o.tonight.kcal, o.tonight.protein, o.tonight.carb, o.tonight.fat, o.tonight.sodium) for o in opts]
    price_of = [o.price_cents for o in opts]
    inf = float("inf")
    carb_max = c.carb_max if c.carb_max is not None else inf
    fat_max = c.fat_max if c.fat_max is not None else inf
    sodium_max = c.sodium_max if c.sodium_max is not None else inf
    budget = c.budget_cents if c.budget_cents is not None else inf
    share = c.tag_protein_share if c.require_tags else 0.0
    tag_v = [sum(x for tag, x in o.tag_protein if tag in c.require_tags) for o in opts]
    is_tagged = [bool(o.tags & c.require_tags) for o in opts]
    roles_of = [option_roles(o) for o in opts] if target is not None else None
    roles_now = [0, 0, 0]
    tagged_after = [False] * (n + 1)      # 下标 i 及之后还有没有带要求标签的选项
    for i in reversed(range(n)):
        tagged_after[i] = tagged_after[i + 1] or is_tagged[i]

    def suffix_best(num: list[float], den: list[float]) -> list[float]:
        out = [0.0] * (n + 1)
        for i in reversed(range(n)):
            ratio = num[i] / den[i] if den[i] > 0 else (inf if num[i] > 0 else 0.0)
            out[i] = max(out[i + 1], ratio)
        return out

    # 后缀最优比率，用于下界：每分钱蛋白、每大卡蛋白；有部位占比要求时，部位蛋白同样处理
    kcal_of = [v[0] for v in vec]
    best_ppy = suffix_best([v[1] for v in vec], [float(x) for x in price_of])
    best_ppk = suffix_best([v[1] for v in vec], kcal_of)
    best_tpy = suffix_best(tag_v, [float(x) for x in price_of])
    best_tpk = suffix_best(tag_v, kcal_of)

    best: list[Plan] = []           # 前 k 名，按 sort_key 升序
    best_sig: dict = {}             # distinct_key → 当前保留的方案
    seen: set[tuple] = set()
    visited = 0

    bound = inf    # 当前第 k 名的价格；找到更好的方案后收紧

    def record(chosen: list[int]) -> None:
        nonlocal bound
        key = tuple(sorted(chosen))
        if key in seen:
            return
        seen.add(key)
        sel = tuple(opts[i] for i in key)
        if target is not None and tuple(roles_now) != target:
            return
        if c.require_tags and not any(o.tags & c.require_tags for o in sel):
            return
        if not is_minimal(sel, c):
            return
        if c.require_tags and c.tag_protein_share > 0:
            tagged = sum(v for o in sel for tag, v in o.tag_protein if tag in c.require_tags)
            total = sum(o.tonight.protein for o in sel)
            if total <= 0 or tagged / total < c.tag_protein_share - 1e-9:
                return
        plan = Plan((0,), sel)
        t = plan.tonight
        # 同价同营养时，留到下一顿的越清淡越好
        plan.sort_key = (plan.price_cents, -round(t.protein, 3), round(t.kcal, 3), round(plan.leftover.kcal, 3), key)
        if distinct_key is not None:
            sig = distinct_key(plan)
            old = best_sig.get(sig)
            if old is not None:
                if plan.sort_key >= old.sort_key:
                    return
                best.remove(old)
            best_sig[sig] = plan
        if len(best) < top_k or plan.sort_key < best[-1].sort_key:
            bisect.insort(best, plan)
            for dropped in best[top_k:]:
                if distinct_key is not None and best_sig.get(distinct_key(dropped)) is dropped:
                    del best_sig[distinct_key(dropped)]
            del best[top_k:]
            if len(best) >= top_k:
                bound = best[-1].price_cents
        elif distinct_key is not None:
            del best_sig[sig]

    eps = 1e-9

    def short_of(need: float, i: int, new_price: int, nk: float, ppy: list[float], ppk: list[float]) -> bool:
        """还差 need 克时，用 i 之后性价比最高、热量效率最高的选项都补不上 → 剪枝。"""
        if need <= eps:
            return False
        if ppy[i] <= 0 or new_price + need / ppy[i] > bound + eps:
            return True
        return ppk[i] <= 0 or need / ppk[i] > c.kcal_max - nk + eps

    kcal_max, protein_min, max_items, max_copies = c.kcal_max, c.protein_min, c.max_items, c.max_copies

    def dfs(start: int, chosen: list[int], price: int, kcal: float, protein: float, carb: float, fat: float,
            sodium: float, tagged: float, copies: list[int], has_tag: bool) -> None:
        nonlocal visited
        visited += 1
        if protein >= protein_min - eps and chosen:
            record(chosen)
        depth = len(chosen) + 1
        if depth > max_items:
            return
        need_tag_item = bool(c.require_tags) and not has_tag
        if need_tag_item and not tagged_after[start]:
            return                                     # 还没有带标签的餐品，后面也没有了
        for i in range(start, n):
            new_price = price + price_of[i]
            if new_price > bound:
                break                                  # 选项按价格升序，后面更贵
            if need_tag_item and depth >= max_items and not is_tagged[i]:
                continue                               # 最后一个位置必须留给带标签的餐品
            if copies[i] >= max_copies:
                continue
            if roles_of is not None and any(roles_now[k] + roles_of[i][k] > target[k] for k in range(3)):
                continue                               # 超出这一餐的结构（如第二个汉堡）
            v = vec[i]
            nk, npr, nc, nf, ns = kcal + v[0], protein + v[1], carb + v[2], fat + v[3], sodium + v[4]
            if (nk > kcal_max + eps or nc > carb_max + eps or nf > fat_max + eps or ns > sodium_max + eps
                    or new_price > budget):
                continue
            need = protein_min - npr
            nt = tagged + tag_v[i]
            # 部位占比：最终部位蛋白 ≥ 占比 × 最终总蛋白 ≥ 占比 × max(目标, 当前总蛋白)
            need_tag = share * max(protein_min, npr) - nt if share > 0 else 0.0
            if need > eps or need_tag > eps:
                if depth >= max_items:
                    continue
                if short_of(need, i, new_price, nk, best_ppy, best_ppk):
                    continue
                if short_of(need_tag, i, new_price, nk, best_tpy, best_tpk):
                    continue
            copies[i] += 1
            chosen.append(i)
            if roles_of is not None:
                for k in range(3):
                    roles_now[k] += roles_of[i][k]
            dfs(i, chosen, new_price, nk, npr, nc, nf, ns, nt, copies, has_tag or is_tagged[i])
            if roles_of is not None:
                for k in range(3):
                    roles_now[k] -= roles_of[i][k]
            chosen.pop()
            copies[i] -= 1

    dfs(0, [], 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, [0] * n, False)
    log.info("求解：%d 个选项，搜索 %d 个节点，得到 %d 个方案", n, visited, len(best))
    return best
