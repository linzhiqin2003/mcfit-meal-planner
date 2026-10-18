"""把求解结果写成给人看的文字：普通版和训练计划版。

文案只改变说法，不改变数量：份数严格来自求解结果，满足用户给的热量和蛋白质目标。
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .meal import role
from .nutrition import Nutrition, negligible, normalize
from .solver import Item, Option, Plan

# 鸡肉的部位标签。Skill 的卡片和话术不再讲训练部位（2026-10-18 用户定）；标签只用于挑「加练」的鸡肉类单品，
# 以及项目主页「练」页按部位生成方案（build_site_data.py 用隐藏参数 --train）
TRAIN_RULES: list[tuple[str, str]] = [
    (r"鸡腿|琵琶腿", "练腿"),
    (r"麦乐鸡|鸡块|鸡柳|鸡胸", "练胸"),
    (r"里脊", "练背"),
    (r"翅", "练手臂"),
]
# 卡片上每样餐品前的图标：按餐品名匹配，先小食饮料，再汉堡，再鸡肉类，都不是就用汉堡
FOOD_ICON = [(r"玉米", "🌽"), (r"苹果", "🍎"), (r"薯", "🍟"), (r"派|新地|麦旋风|圆筒", "🍦"),
             (r"牛奶|豆浆", "🥛"), (r"咖啡|拿铁|美式|奶铁", "☕"), (r"堡|麦满分", "🍔"), (r"鸡|翅", "🍗")]


def food_icon(name: str) -> str:
    return next((ic for pat, ic in FOOD_ICON if re.search(pat, name)), "🍔")


def nut_text(n) -> str:
    return f"{n.kcal:.0f} 大卡 · 蛋白质 {n.protein:.0f} g · 碳水 {n.carb:.0f} g · 脂肪 {n.fat:.0f} g"


def _is_light(it: Item) -> bool:
    """几乎零热量的饮料（无糖可乐、红茶、美式）：彼此可互换，不算不同方案。"""
    return negligible(it.tonight)


def plan_signature(p: Plan) -> tuple:
    """方案的「实质」：价格、这一顿吃进去的营养、以及除近零热量饮料外点了哪些餐品，相同就算同一种方案。
    这样只差零卡饮料（无糖可乐与锡兰红茶差 2 大卡）、或只差「到手只吃馅时要不要去酱」
    （酱在面包上，只影响下一顿）的方案会合并。"""
    names, total = [], Nutrition()
    for o, n in p.counts():
        for it in _items(o):
            if not _is_light(it):
                names += [it.name] * n
                total = total + it.tonight.scale(n)
    return (p.price_cents, tuple(sorted(names)), round(total.kcal), round(total.protein), round(total.carb), round(total.fat))


def distinct(plans: list[Plan], k: int = 3) -> list[Plan]:
    out, seen = [], set()
    for p in plans:
        s = plan_signature(p)
        if s not in seen:
            seen.add(s)
            out.append(p)
        if len(out) >= k:
            break
    return out


# 饮料不算训练动作（注意别用「汁」：麦麦脆汁鸡）
DRINK_PATTERN = r"可乐|雪碧|怡泉|红茶|茶|咖啡|奶铁|拿铁|美式|黑巧|牛奶|豆浆|美汁源|水$"

# 餐段（按麦当劳的早餐 10:30 截止）→（这一顿怎么称呼，下一顿怎么称呼）
MEAL_WORDS = {"早餐": ("这顿早餐", "午餐"), "午餐": ("午餐", "晚餐"), "晚餐": ("今晚", "明早"), "夜宵": ("今晚", "明早")}


def meal_of(slot: str | None = None) -> str:
    """slot 形如 2026-10-17T0730、2026-10-17 07:30 或 now；解析不了时按当前时间。"""
    m = re.search(r"[T ](\d{2}):?(\d{2})", slot or "")
    if m:
        hhmm = int(m.group(1)) * 100 + int(m.group(2))
    else:
        import time
        t = time.localtime()
        hhmm = t.tm_hour * 100 + t.tm_min
    if hhmm < 1030:
        return "早餐"
    if hhmm < 1600:
        return "午餐"
    return "晚餐" if hhmm < 2100 else "夜宵"


def _notes(p: Plan) -> list[str]:
    return [f"注：{x}" for x in p.footnotes]


def _lines(p: Plan) -> list[str]:
    return [f"{n} × {o.label.replace('（整份吃）', '')}" for o, n in p.counts()]


def merged_tips(p: Plan, nxt: str) -> list[str]:
    """同一款汉堡点了两个、一个整份吃一个只吃馅：等于两份馅夹进同一份面包，另一份面包留到下一顿。
    换成这个说法，用户一看就知道怎么吃（「点两个双吉，今晚一份面包夹四块牛肉饼，剩下的面包当明早早餐」）。"""
    whole, split = {}, {}
    for o, n in p.counts():
        for it in _items(o):
            if role(it.name) != "burger":
                continue
            bucket = split if "只吃馅" in it.how else whole
            bucket[normalize(it.name)] = bucket.get(normalize(it.name), 0) + n
    tips = []
    for name in sorted(set(whole) & set(split)):
        k = min(whole[name], split[name])
        meal = "明早当早餐" if nxt == "明早" else f"{nxt}再吃"
        tips.append(f"合并吃：{_cn(2 * k)}个{name}，今晚把{_cn(2 * k)}份馅夹进{_cn(k)}份面包，另外{_cn(k)}份面包留到{meal}")
    return tips


def _cn(n: int) -> str:
    return {1: "一", 2: "两", 3: "三", 4: "四"}.get(n, str(n))


def render_plain(p: Plan, price_checked=None, slot: str | None = None) -> str:
    now, nxt = MEAL_WORDS[meal_of(slot)]
    out = ["推荐点法："] + [f"  {x}" for x in _lines(p)] + merged_tips(p, nxt)
    out.append(f"价格：{_price_text(p, price_checked)}")
    out.append(f"{now}吃进去：{nut_text(p.tonight)}")
    if p.leftover.kcal > 0:
        tip = "面包密封冷藏，第二天加热" if nxt == "明早" else "面包密封放好，下一顿加热"
        out.append(f"留到{nxt}：{nut_text(p.leftover)}（{tip}）")
    return "\n".join(out + _notes(p))


@dataclass
class TrainItem:
    name: str
    per_set: str
    sets: int
    icon: str
    how: str = ""


def _train_items(p: Plan) -> list[TrainItem]:
    items: dict[str, TrainItem] = {}
    for o, n in p.counts():
        for raw_name, how in _main_names(o, with_how=True):
            name = normalize(raw_name)       # 「麦乐鸡」和「麦乐鸡5块」是同一样，合并成一组
            icon = food_icon(name)
            m = re.search(r"(\d+)\s*块", name)
            per_set = f"{m.group(1)} 块一组" if m else "1 个一组"
            key = name + per_set + how
            if key in items:
                items[key].sets += n
            else:
                items[key] = TrainItem(name, per_set, n, icon, how)
    return list(items.values())


def _items(o: Option) -> tuple[Item, ...]:
    return o.items or (Item(o.label, "整份吃", o.tonight, single=o.payload[:1] == ("single",)),)


def _how(note: str) -> str:
    return "" if note in ("", "整份吃") else note.replace("，面包留到下一顿", "").replace("到手只吃馅", "只吃馅")


def _main_names(o: Option, with_how: bool = False) -> list:
    """训练动作：近零热量的东西不列（套餐里带的，以及单点的无糖可乐、红茶、矿泉水）。有热量或蛋白的（牛奶、豆浆）要列，
    否则清单上的蛋白质加起来不够训练量里写的数。"""
    names = []
    for it in _items(o):
        # 零热量的饮料（无糖可乐、红茶、纯悦）单点也不算一个「动作」；「怎么下单」里照样会写
        if negligible(it.tonight) and (not it.single or role(it.name) == "drink"):
            continue
        names.append((it.name, _how(it.how)) if with_how else it.name)
    return names


def _price_text(p: Plan, check) -> str:
    """价格；核价过时以接口为准：一致标「已核价」，不一致给出接口价。"""
    text = f"¥{p.price_cents / 100:.1f}"
    if check is None:
        return text
    if getattr(check, "ok", check is True):
        return text + "（已核价）"
    actual = getattr(check, "actual_cents", None)
    if actual is None:
        return text + "（核价失败，以下单时的价格为准）"
    return f"¥{actual / 100:.1f}（核价结果；预估为 {text}，以核价为准）"


def short_how(how: str) -> str:
    """「下单去麦香鸡酱，到手只吃馅，面包留到下一顿」→「去麦香鸡酱 + 只吃馅」。"""
    s = how.replace("，面包留到下一顿", "").replace("到手只吃馅", "只吃馅").replace("下单去", "去")
    return s.replace("，只吃馅", " + 只吃馅")


def render_ladders(ladders: list, nxt: str) -> list[str]:
    """同一份餐品的几种吃法（compare.eat_ladder 的结果）：官方菜单只给整份，这里把去酱、去芝士、分餐都摆出来。"""
    out = []
    for name, rungs in ladders:
        out.append(f"同一个{normalize(name)}，有这几种练法：")
        for r in rungs:
            line = f"  {short_how(r.how)}：{r.tonight.kcal:.0f} 大卡，蛋白质 {r.tonight.protein:.0f} g"
            if r.leftover.kcal > 0:
                line += f"，面包 {r.leftover.kcal:.0f} 大卡留到{nxt}"
            out.append(line + ("  ← 本方案" if r.chosen else ""))
        out.append("")
    return out


def render_official(sets: list, p: Plan, c, nxt: str) -> list[str]:
    """和门店官方「N 大卡套餐」比（compare.official_sets 的结果）：官方只能整份吃，组合也是固定的。"""
    if not sets:
        return []
    label = re.sub(r"(\d+)大卡", r"\1 大卡", sets[0].category)
    yuan = lambda cents: f"¥{cents / 100:.1f}"
    out = [f"对比麦当劳官方「{label}」（这家店 {len(sets)} 款，只能整份吃）："]
    fits = [x for x in sets if x.fits_whole]
    under = [x for x in sets if x.whole.kcal <= c.kcal_max + 1e-9] or sets
    if c.protein_min > 0:
        top = max(under, key=lambda x: (x.whole.protein, -x.price_cents))
        out.append(f"  蛋白质最高的是{top.name}：{top.whole.kcal:.0f} 大卡，蛋白质 {top.whole.protein:.0f} g，{yuan(top.price_cents)}")
        if not fits:
            out.append(f"  没有一款能到 {c.protein_min:.0f} g 蛋白质；这份训练计划 {yuan(p.price_cents)}，"
                       f"{p.tonight.kcal:.0f} 大卡，蛋白质 {p.tonight.protein:.0f} g")
        else:
            cheap = min(fits, key=lambda x: x.price_cents)
            d = cheap.price_cents - p.price_cents
            out.append(f"  达标的 {len(fits)} 款里最便宜的是{cheap.name}（{yuan(cheap.price_cents)}）；这份训练计划"
                       + (f"便宜 {yuan(d)}" if d > 0 else f"贵 {yuan(-d)}，蛋白质多 {p.tonight.protein - cheap.whole.protein:.0f} g"))
    else:
        cheap = min(under, key=lambda x: x.price_cents)
        d = cheap.price_cents - p.price_cents
        out.append(f"  最便宜的是{cheap.name}：{yuan(cheap.price_cents)}，{cheap.whole.kcal:.0f} 大卡；这份训练计划"
                   + (f"便宜 {yuan(d)}" if d > 0 else f"{yuan(p.price_cents)}"))
    cut = max(sets, key=lambda x: x.whole.kcal - x.lowest.kcal)
    if cut.whole.kcal - cut.lowest.kcal >= 50 and cut.lowest_hows:
        hows = "；".join(short_how(h).replace("：", "", 1) for h in cut.lowest_hows)
        tail = f"（面包 {cut.lowest_leftover.kcal:.0f} 大卡留到{nxt}）" if cut.lowest_leftover.kcal > 0 else ""
        out.append(f"  官方套餐也能拆：{cut.name}里的{hows}，这一顿从 {cut.whole.kcal:.0f} 降到 {cut.lowest.kcal:.0f} 大卡{tail}")
    return out + [""]


def render_gym(p: Plan, bonus: Option | None = None, slot: str | None = None,
               price_checked=None, extras: dict | None = None) -> str:
    _, nxt = MEAL_WORDS[meal_of(slot)]
    out = ["Go to Gym 不如 Go to ᗰ", "今日训练 🍔", ""]
    for it in _train_items(p):
        out.append(f"{it.icon}{it.name}：{it.per_set}，共 {it.sets} 组" + (f"（{it.how}）" if it.how else ""))
    split = [o for o in p.options if o.payload and (o.payload[0] == "single" and o.payload[3] or
                                                     o.payload[0] == "combo" and any(x[3] for x in o.payload[2]))]
    merged = merged_tips(p, nxt)
    if merged:
        out += [f"动作要领：{t.removeprefix('合并吃：')}" for t in merged]
    elif split:
        out.append("动作要领：只吃馅的，面包收进冰箱，明早当早餐" if nxt == "明早" else f"动作要领：只吃馅的，面包收好，{nxt}再吃")
    out.append("")
    out.append(f"训练量：{nut_text(p.tonight)}")
    out.append(f"会员费：{_price_text(p, price_checked)}")
    if p.leftover.kcal > 0:
        out.append(f"{nxt}拉伸：{nut_text(p.leftover)}")
    out += ["", "怎么下单："] + [f"  {x}" for x in _lines(p)]
    if bonus is not None:
        name, how = (_main_names(bonus, with_how=True) or [(_items(bonus)[0].name, "")])[0]
        how = f"（{how}）" if how else ""
        out += ["", f"有余力的朋友，可以再加一个{food_icon(normalize(name))}{normalize(name)}{how}上上强度"
                    f"（+{bonus.tonight.kcal:.0f} 大卡，+{bonus.tonight.protein:.0f} g 蛋白质，+¥{bonus.price_cents / 100:.1f}）"]
    if extras:
        # 官方菜单给不了的：同一个汉堡的几种吃法、和官方「N 大卡套餐」的对比
        more = render_ladders(extras.get("ladders") or [], nxt) + render_official(extras.get("official") or [], p, extras["constraints"], nxt)
        if more:
            out += [""] + more[:-1] if more[-1] == "" else [""] + more
    notes = _notes(p)
    return "\n".join(out + ([""] + notes if notes else []))
