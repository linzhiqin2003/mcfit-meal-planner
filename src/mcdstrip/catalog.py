"""门店商品目录：菜单 + 餐品详情 → 可购买的配置 → 求解器选项。

一个「选项」= 一种购买配置（单品，或套餐每一组选够规定份数，如「主食任意选」选 2 个）× 主食的一种吃法：
  - 整份；
  - 下单去配料（官方特制，写进 modification，价格不变）；
  - 到手自拆：只吃馅（肉饼、芝士等），面包和酱料留到下一顿。
营养以官方整份数值为锚点：变体 = 官方整份 − 去掉的配料（来自配料库），保证整份吃法与官方完全一致。
"""
from __future__ import annotations

import itertools
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from .library import Library
from .nutrition import Nutrition, negligible, normalize, pieces
from .solver import Item, Option

log = logging.getLogger(__name__)

# 到手自拆时留下的部分：面包、酱料、蔬菜
LEFTOVER_PREFIXES = ("bun.", "sauce.", "veg.", "butter")
# 下单时值得去掉的配料：去掉后热量至少少这么多才生成单独的吃法
MEANINGFUL_KCAL = 25.0
# 不在营养表里、只能由配料库预测的餐品：预测的热量标准差超过这个比例就不推荐
PREDICT_MAX_REL_SD = 0.12


@dataclass(frozen=True)
class Modifier:
    name: str
    code: str
    selected_key: str
    unselected_key: str
    default_qty: int


@dataclass(frozen=True)
class Choice:
    code: str
    name: str
    diff_cents: int
    support_modify: bool
    modifiers: tuple[Modifier, ...]
    max_quantity: int = -1             # 同一组里这一项最多选几份，-1 为不限


@dataclass(frozen=True)
class Round:
    id: int
    name: str
    choices: tuple[Choice, ...]
    quantity: int = 1                  # 这一组要选几份（「堡堡随心拼」主食 2、小食 3、饮料 2）


@dataclass
class Product:
    code: str
    name: str
    price_cents: int
    modifiers: tuple[Modifier, ...] = ()
    rounds: tuple[Round, ...] = ()
    detail_name: str = ""              # 详情里的名称，常比菜单名更具体（麦咖啡™美式 → 麦咖啡™冰美式中杯）

    @property
    def is_combo(self) -> bool:
        return bool(self.rounds)


@dataclass(frozen=True)
class EatPlan:
    """一份主食的吃法。"""
    removed: tuple[str, ...]          # 下单去掉的配料（官方配料名）
    split: bool                        # 是否到手自拆（只吃馅）
    tonight: Nutrition
    leftover: Nutrition
    note: str
    estimate_sd: float = 0.0           # 不在官方营养表里时，配料库预测的热量标准差；官方数据为 0


@dataclass
class Catalog:
    products: dict[str, Product]
    store_code: str
    slot: str = ""
    unknown_nutrition: set[str] = field(default_factory=set)
    store_name: str = ""
    reservation: str | None = None     # 拉菜单时用的预约时间（算价、下单要用同一个）
    categories: dict[str, list[str]] = field(default_factory=dict)   # 菜单分类名（去掉空白）→ 餐品编码，如「500大卡套餐」


def _cents(v) -> int:
    return int(round(float(v) * 100))


def parse_diff(s: str | None) -> int:
    """「+ ¥1」「- ¥1」「+ ¥0.5」→ 分。"""
    if not s:
        return 0
    m = re.match(r"\s*([+-])\s*¥?\s*([\d.]+)", s)
    if not m:
        raise ValueError(f"无法解析差价：{s!r}")
    v = _cents(m.group(2))
    return -v if m.group(1) == "-" else v


def _modifiers(detail: dict) -> tuple[Modifier, ...]:
    out = []
    for it in (detail.get("modification") or {}).get("items") or []:
        for v in it.get("values") or []:
            out.append(Modifier(v["name"], v["code"], v.get("selectedKey", ""), v.get("unselectedKey", ""),
                                int(v.get("selectedQuantity") or 0)))
    return tuple(out)


def price_cents(menu_item: dict) -> int:
    """可下单的价格。「随单购麦金卡/早餐卡优惠」的 currentPrice 只有连同会员卡一起买才有，
    不带卡时算价接口按 originalPrice 收（2026-10-15 实测：人气超值四件套不带卡 ¥57，带卡 ¥28 + 体验卡 ¥9.9）。"""
    if "随单购" in (menu_item.get("discountType") or "") and menu_item.get("originalPrice"):
        return _cents(menu_item["originalPrice"])
    return _cents(menu_item["currentPrice"])


def parse_product(code: str, menu_item: dict, detail: dict) -> Product:
    rounds = []
    for r in detail.get("rounds") or []:
        choices = tuple(Choice(c["code"], c["name"], parse_diff(c.get("diffPrice")), bool(c.get("supportModify")),
                               _modifiers(c), int(c.get("maxQuantity") or -1)) for c in r.get("choices") or [])
        rounds.append(Round(int(r["id"]), r["name"], choices, max(1, int(r.get("quantity") or 1))))
    return Product(code, menu_item["name"], price_cents(menu_item), _modifiers(detail), tuple(rounds),
                   detail.get("name") or "")


def catalog_from(menu: dict, details: dict[str, dict], store_code: str, slot: str = "") -> Catalog:
    products = {code: parse_product(code, item, details[code]) for code, item in menu["meals"].items() if code in details}
    missing = len(menu["meals"]) - len(products)
    if missing:
        log.warning("门店 %s：%d 个餐品没有详情，已跳过", store_code, missing)
    categories = {re.sub(r"\s+", "", c.get("name") or ""): [m["code"] for m in c.get("meals") or [] if m.get("code") in products]
                  for c in menu.get("categories") or []}
    return Catalog(products, store_code, slot, categories=categories)


def load_fixture(store_dir: Path) -> Catalog:
    store_dir = store_dir.resolve()          # 「--offline .」时也能取到门店号和时段
    menu = json.loads((store_dir / "menu.json").read_text(encoding="utf-8"))
    details = {}
    for code in menu["meals"]:
        f = store_dir / "details" / f"{code}.json"
        if f.exists():
            details[code] = json.loads(f.read_text(encoding="utf-8"))
    return catalog_from(menu, details, store_dir.parent.name, store_dir.name)


def load_live(m, store_code: str, reservation: str | None = None, order_type: int = 1, be_type: int = 1,
              cache_dir: Path | None = None, detail_ttl_s: int = 6 * 3600) -> Catalog:
    """实时拉取门店菜单（每次都拉，餐段一变菜单就变）；餐品详情（配料、套餐组）按门店和取餐方式缓存，默认 6 小时。"""
    import time
    from concurrent.futures import ThreadPoolExecutor
    base = dict(storeCode=store_code, orderType=order_type, beType=be_type)
    if reservation:
        base["reservationDate"] = reservation
    menu = m.data("query-meals", **base)
    ddir = (cache_dir or Path.home() / ".cache" / "mcdstrip") / store_code / f"o{order_type}b{be_type}" / "details"
    ddir.mkdir(parents=True, exist_ok=True)
    details: dict[str, dict] = {}
    todo = []
    for code in menu["meals"]:
        f = ddir / f"{code}.json"
        if f.exists() and time.time() - f.stat().st_mtime < detail_ttl_s:
            try:
                details[code] = json.loads(f.read_text(encoding="utf-8"))
                continue
            except ValueError:
                log.warning("详情缓存损坏，重新获取：%s", f)
        todo.append(code)

    def one(code: str):
        try:
            return code, m.data("query-meal-detail", **base, code=code)
        except Exception as e:  # 个别餐品详情失败不影响整体
            log.warning("餐品 %s 详情获取失败：%s", code, e)
            return code, None

    with ThreadPoolExecutor(4) as ex:
        for code, d in ex.map(one, todo):
            if d is not None:
                details[code] = d
                (ddir / f"{code}.json").write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    log.info("门店 %s：菜单 %d 项，详情读缓存 %d、新取 %d", store_code, len(menu["meals"]), len(menu["meals"]) - len(todo), len(todo))
    slot = (reservation or "now").replace(" ", "T").replace(":", "")
    cat = catalog_from(menu, details, store_code, slot)
    cat.reservation = reservation
    return cat


class Builder:
    """把目录变成求解器选项。需要官方营养表、配料库，以及「官方配料名 → 配料 id」的映射。"""

    def __init__(self, official: dict[str, Nutrition], library: Library | None, modifier_map: dict[str, str],
                 tag_rules: list[tuple[str, str]] | None = None):
        self.official, self.lib, self.modmap = official, library, modifier_map
        self.tag_rules = tag_rules or []
        # 同一款主食会出现在几十个套餐里，吃法只算一次（Modifier 不可变，可以直接做键）
        self._plans: dict[tuple, list[EatPlan]] = {}
        # 按块数换算：(名称, 单位) → [(块数, 营养表名)]，如 麦辣鸡翅 → [(2, 麦辣鸡翅-2块)]
        self._by_pieces: dict[tuple[str, str], list[tuple[int, str]]] = {}
        for k in official:
            pc = pieces(k)
            if pc:
                self._by_pieces.setdefault((pc[0], pc[2]), []).append((pc[1], k))

    # ---- 营养 ----
    def official_nutrition(self, n: str) -> Nutrition | None:
        """营养表直接查；查不到时按块数从同名餐品换算（麦辣鸡翅4块 = 2 × 麦辣鸡翅-2块）。n 须已归一。"""
        if n in self.official:
            return self.official[n]
        pc = pieces(n)
        if pc and (pc[0], pc[2]) in self._by_pieces:
            count, ref = min(self._by_pieces[(pc[0], pc[2])])
            log.debug("%s 按块数由 %s 换算（×%.2f）", n, ref, pc[1] / count)
            return self.official[ref].scale(pc[1] / count)
        return None

    def nutrition_name(self, p: Product) -> str:
        """单品用哪个名字查营养：详情名常更具体（麦咖啡™美式 → 麦咖啡™冰美式中杯），查得到就用它。"""
        if p.detail_name and p.detail_name != p.name and self.base_nutrition(p.detail_name) is not None:
            return p.detail_name
        return p.name

    def base_nutrition(self, name: str) -> Nutrition | None:
        n = normalize(name)
        known = self.official_nutrition(n)
        if known is not None:
            return known
        if self.lib and n in self.lib.recipes:
            value, sd = self.lib.predict(n)
            if sd.kcal <= PREDICT_MAX_REL_SD * value.kcal:
                return value
            log.info("%s 不在营养表里，配料库预测不够准（%.0f±%.0f 大卡），不推荐", n, value.kcal, sd.kcal)
        return None

    def eat_plans(self, name: str, modifiers: tuple[Modifier, ...], allow_split: bool) -> list[EatPlan]:
        key = (name, tuple(modifiers), allow_split)
        if key not in self._plans:
            self._plans[key] = self._eat_plans(name, modifiers, allow_split)
        return self._plans[key]

    def _eat_plans(self, name: str, modifiers: tuple[Modifier, ...], allow_split: bool) -> list[EatPlan]:
        base = self.base_nutrition(name)
        if base is None:
            return []
        n = normalize(name)
        est = 0.0 if self.official_nutrition(n) is not None else self.lib.predict(n)[1].kcal
        whole = EatPlan((), False, base, Nutrition(), "整份吃", est)
        if not self.lib or n not in self.lib.recipes:
            return [whole]
        recipe = self.lib.recipes[n]
        # 可去且有意义的配料（同名配料可能出现两次，如两片吉士只对应一个开关）
        removable = {}
        for m in modifiers:
            cid = self.modmap.get(m.name)
            if cid and cid in recipe and m.default_qty > 0:
                kcal = self.lib.components[cid].value.kcal * recipe[cid]
                if kcal >= MEANINGFUL_KCAL:
                    removable[m.name] = cid
        plans = []
        names = sorted(removable)
        for k in range(len(names) + 1):
            for subset in itertools.combinations(names, k):
                removed_parts = {removable[x]: recipe[removable[x]] for x in subset}
                if subset and not self.lib.reliable(removed_parts):
                    log.debug("%s：去%s 的营养拆不准，跳过", n, "、".join(subset))
                    continue
                removed, _ = self.lib.nutrition_of(removed_parts)
                eaten = (base - removed).clamped()
                label = "整份吃" if not subset else "下单去" + "、".join(subset)
                plans.append(EatPlan(tuple(subset), False, eaten, Nutrition(), label, est))
                if allow_split:
                    left_parts = {c: q for c, q in recipe.items() if c.startswith(LEFTOVER_PREFIXES) and c not in removed_parts}
                    if any(c.startswith("bun.") for c in left_parts) and self.lib.reliable(left_parts):
                        left, _ = self.lib.nutrition_of(left_parts)
                        plans.append(EatPlan(tuple(subset), True, (eaten - left).clamped(), left,
                                             (label + "，" if subset else "") + "到手只吃馅，面包留到下一顿", est))
        return plans

    # ---- 选项 ----
    def tag_protein(self, parts: list[tuple[str, float]]) -> tuple:
        """parts：[(餐品名, 今晚蛋白质)]，按标签累计每样餐品自己的蛋白质。"""
        acc: dict[str, float] = {}
        for name, protein in parts:
            for pattern, tag in self.tag_rules:
                if re.search(pattern, name):
                    acc[tag] = acc.get(tag, 0.0) + protein
                    break
        return tuple(sorted(acc.items()))

    def tags(self, names: list[str]) -> frozenset[str]:
        out = set()
        for n in names:
            for pattern, tag in self.tag_rules:
                if re.search(pattern, n):
                    out.add(tag)
        return frozenset(out)

    def options(self, cat: Catalog, allow_split: bool = True, kcal_max: float | None = None,
                share: float = 0.0) -> list[Option]:
        """展开门店所有可点的选项。

        套餐每组要选够 quantity 份（可重复选同一项，但不超过该项的 maxQuantity）。给了 kcal_max 时，
        按组逐份展开，这一顿热量已经必然超上限的部分组合不再往下展开（大套餐的组合数可达上万）。
        share 是部位蛋白占比要求：大于 0 时组内剪枝更保守（见 _pareto_choices）。"""
        opts: list[Option] = []
        cap = kcal_max + 1e-9 if kcal_max is not None else float("inf")
        for p in cat.products.values():
            if not p.is_combo:
                name = self.nutrition_name(p)
                for ep in self.eat_plans(name, p.modifiers, allow_split):
                    if ep.tonight.kcal <= cap:
                        opts.append(self._option(p, (), ep, name))
                if self.base_nutrition(name) is None:
                    cat.unknown_nutrition.add(p.name)
                continue
            per_round = []
            for r in p.rounds:
                cands = []
                for ch in r.choices:
                    plans = self.eat_plans(ch.name, ch.modifiers if ch.support_modify else (), allow_split)
                    if not plans:
                        cat.unknown_nutrition.add(ch.name)
                        continue
                    cands.extend((ch, ep) for ep in plans)
                if not cands:
                    break
                limited = r.quantity > 1 and any(ch.max_quantity > 0 for ch, _ in cands)
                per_round.append((r, cands if limited else self._pareto_choices(cands, share)))
            else:
                opts.extend(self._expand_combo(p, per_round, cap))
        log.info("门店 %s：%d 个选项；%d 个餐品缺营养数据被跳过", cat.store_code, len(opts), len(cat.unknown_nutrition))
        return opts

    def _expand_combo(self, p: Product, per_round: list, cap: float) -> list[Option]:
        """逐份展开套餐：同一组的多份按候选下标不降序选（即可重复组合），并遵守每项的数量上限。"""
        slots = [(r, cands) for r, cands in per_round for _ in range(r.quantity)]
        min_rest = [0.0] * (len(slots) + 1)
        for i in reversed(range(len(slots))):
            min_rest[i] = min_rest[i + 1] + min(ep.tonight.kcal for _, ep in slots[i][1])
        out: list[Option] = []
        picked: list[tuple[Round, int]] = []
        used: dict[tuple[int, str], int] = {}

        def expand(i: int, kcal: float) -> None:
            if kcal + min_rest[i] > cap:
                return
            if i == len(slots):
                sel = tuple((r.id, slots_cands[r.id][j][0], slots_cands[r.id][j][1]) for r, j in picked)
                out.append(self._option(p, sel, None, p.name))
                return
            r, cands = slots[i]
            start = picked[-1][1] if picked and picked[-1][0].id == r.id else 0
            for j in range(start, len(cands)):
                ch, ep = cands[j]
                k = (r.id, ch.code)
                if ch.max_quantity > 0 and used.get(k, 0) >= ch.max_quantity:
                    continue
                used[k] = used.get(k, 0) + 1
                picked.append((r, j))
                expand(i + 1, kcal + ep.tonight.kcal)
                picked.pop()
                used[k] -= 1

        slots_cands = {r.id: cands for r, cands in per_round}
        expand(0, 0.0)
        return out

    def _pareto_choices(self, cands: list[tuple[Choice, EatPlan]], share: float = 0.0) -> list[tuple[Choice, EatPlan]]:
        """一组内的可选项去掉被支配者：差价不高、蛋白不少、热量碳水脂肪钠都不多、留存不更多。

        只在训练标签相同的选项之间比较（否则练胸日的麦乐鸡会被别的更「划算」的汉堡删掉）。
        有部位占比要求时，无标签选项的蛋白多反而拉低占比，所以无标签选项只在蛋白相同的情况下比较。"""
        def vec(c: tuple[Choice, EatPlan]) -> tuple:
            ch, ep = c
            t = ep.tonight
            return (ch.diff_cents, -t.protein, t.kcal, t.carb, t.fat, t.sodium, ep.leftover.kcal)

        # 近零热量的饮品只留一个代表（差价最低、其次热量碳水脂肪钠最少），其余对营养几乎没有影响，
        # 却会让套餐组合数成倍增长；展示时提示饮料可换成其他零卡款
        light = [c for c in cands if negligible(c[1].tonight) and not self.tags([c[0].name])]
        if len(light) > 1:
            best = min(light, key=lambda c: (c[0].diff_cents, c[1].tonight.kcal, c[1].tonight.carb, c[1].tonight.fat,
                                              c[1].tonight.sodium, c[0].code))
            cands = [c for c in cands if c is best or c not in light]
        keep = []
        for a in cands:
            va, ta = vec(a), self.tags([a[0].name])
            dominated = False
            for b in cands:
                if b is a or self.tags([b[0].name]) != ta:
                    continue
                vb = vec(b)
                if share > 0 and not ta and vb[1] != va[1]:
                    continue
                if all(x <= y for x, y in zip(vb, va)) and (vb, b[0].code, b[1].note) < (va, a[0].code, a[1].note):
                    dominated = True
                    break
            if not dominated:
                keep.append(a)
        return keep

    def _option(self, p: Product, sel: tuple, ep: EatPlan | None, name: str) -> Option:
        if ep is not None:   # 单品
            price, tonight, left = p.price_cents, ep.tonight, ep.leftover
            label = f"{p.name}（{ep.note}）"
            payload = ("single", p.code, ep.removed, ep.split)
            tag_names = [p.name]
            tp = self.tag_protein([(p.name, ep.tonight.protein)])
            oid = f"{p.code}|{','.join(ep.removed)}|{int(ep.split)}"
            notes = _estimate_note(p.name, ep)
            items = (Item(p.name, ep.note, ep.tonight, single=True),)
        else:
            price = p.price_cents + sum(ch.diff_cents for _, ch, _ in sel)
            tonight, left = Nutrition(), Nutrition()
            parts: dict[str, int] = {}
            for _, ch, e in sel:
                tonight, left = tonight + e.tonight, left + e.leftover
                part = ch.name if e.note == "整份吃" else f"{ch.name}（{e.note}）"
                parts[part] = parts.get(part, 0) + 1
            label = f"{p.name}：" + " + ".join(x if n == 1 else f"{x} ×{n}" for x, n in parts.items())
            payload = ("combo", p.code, tuple((rid, ch.code, e.removed, e.split) for rid, ch, e in sel))
            tag_names = [ch.name for _, ch, _ in sel]
            tp = self.tag_protein([(ch.name, e.tonight.protein) for _, ch, e in sel])
            oid = f"{p.code}|" + "|".join(f"{rid}:{ch.code}:{','.join(e.removed)}:{int(e.split)}" for rid, ch, e in sel)
            notes = tuple(x for _, ch, e in sel for x in _estimate_note(ch.name, e))
            items = tuple(Item(ch.name, e.note, e.tonight) for _, ch, e in sel)
        return Option(oid, label, price, tonight, left, self.tags(tag_names), payload, tp, notes, items)


def _estimate_note(name: str, ep: EatPlan) -> tuple[str, ...]:
    if ep.estimate_sd <= 0:
        return ()
    return (f"{name}不在官方营养表里，营养由配料库估算（约 ±{ep.estimate_sd:.0f} 大卡）",)
