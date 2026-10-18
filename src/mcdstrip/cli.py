"""命令行入口。

    mcdstrip library                         # 构建配料库并打印
    mcdstrip plan --kcal-max 400 --protein-min 30 --offline data/fixtures/stores/1450441/2026-10-16T1900
    MCD_MCP_TOKEN=... mcdstrip stores --city 上海 --near 人民广场
    MCD_MCP_TOKEN=... mcdstrip plan --kcal-max 400 --protein-min 30 --city 上海 --near 人民广场 --style gym --train 练腿
    MCD_MCP_TOKEN=... mcdstrip plan --kcal-max 400 --protein-min 30 --store 1450441 --verify
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from .catalog import Builder, load_fixture, load_live
from .library import build_library, load_priors, load_recipes
from .nutrition import parse_table
from .meal import MEALS, burgers_of, healthy, parse_meal
from .render import TRAIN_RULES, plan_signature, render_gym, render_plain
from .solver import Constraints, solve

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
log = logging.getLogger("mcdstrip")


def _recipes_path() -> Path:
    final = DATA / "reference" / "recipes.json"
    return final if final.exists() else DATA / "reference" / "recipes_draft.json"


CACHE = Path.home() / ".cache" / "mcdstrip"


def _library(table, raw: str, recipes_path: Path, priors_path: Path):
    """配料库求解约需数秒；按输入文件和求解代码的内容哈希缓存，任何一样变了都会重算。"""
    import hashlib
    import pickle
    from . import library, linalg
    names_path = DATA / "reference" / "component_names.json"
    h = hashlib.sha256(raw.encode())
    for f in (recipes_path, priors_path, names_path, Path(library.__file__), Path(linalg.__file__)):
        h.update(f.read_bytes())
    path = CACHE / f"library-{h.hexdigest()[:16]}.pkl"
    try:
        lib = pickle.loads(path.read_bytes())
        log.debug("配料库读缓存 %s", path)
        return lib
    except FileNotFoundError:
        pass
    except Exception as e:  # 缓存损坏或版本不兼容：重算即可
        log.warning("配料库缓存不可用，重新求解：%s", e)
    book = load_recipes(recipes_path)
    lib = build_library(table, book.recipes, load_priors(priors_path), names=json.loads(names_path.read_text(encoding="utf-8")),
                        fit_exclude=book.fit_exclude, obs_sd=book.obs_sd, uncertain=book.uncertain)
    try:
        CACHE.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(pickle.dumps(lib))
        tmp.replace(path)
    except OSError as e:
        log.warning("配料库缓存写入失败：%s", e)
    return lib


def load_core(nutrition_raw: Path | None = None):
    raw = (nutrition_raw or DATA / "fixtures" / "nutrition_raw.txt").read_text(encoding="utf-8")
    table = parse_table(raw)
    lib = _library(table, raw, _recipes_path(), DATA / "reference" / "priors_us.json")
    modmap = json.loads((DATA / "reference" / "modifier_map.json").read_text(encoding="utf-8"))
    return table, lib, modmap


def cmd_library(a) -> int:
    _, lib, _ = load_core()
    print(f"{'配料':<20}{'大卡':>8}{'±':>6}{'蛋白':>7}{'脂肪':>7}{'碳水':>7}{'钠':>8}{'钙':>7}  依据")
    for c in sorted(lib.components.values(), key=lambda c: c.id):
        v = c.value
        print(f"{c.id:<20}{v.kcal:>8.1f}{c.sd.kcal:>6.1f}{v.protein:>7.1f}{v.fat:>7.1f}{v.carb:>7.1f}{v.sodium:>8.1f}{v.calcium:>7.1f}  {c.basis}")
    bad = lib.suspicious()
    print(f"\n拟合 {len(lib.fits)} 款餐品，残差异常 {len(bad)} 款" + ("：" + "、".join(f"{f.product}({f.max_z:.1f})" for f in bad) if bad else ""))
    if a.out:
        Path(a.out).write_text(json.dumps(lib.to_json(), ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"已写入 {a.out}")
    return 0


def friendly_error(e: Exception) -> str:
    """给用户看的错误：按原因分开说清楚，不暴露堆栈和内部细节（详情用 -v 看日志）。"""
    from .mcp import McdAuthError, McdBusinessError, McdMcpError, token_setup_hint
    if isinstance(e, McdAuthError):
        if "缺少" in str(e):
            return f"还没有设置麦当劳 MCP Token：在 open.mcd.cn/mcp 申请后，{token_setup_hint()}。"
        return f"麦当劳 MCP Token 无效或已过期：请到 open.mcd.cn/mcp 重新获取，{token_setup_hint()}。"
    if isinstance(e, McdBusinessError):
        return f"麦当劳接口返回：{e.message}"
    if isinstance(e, McdMcpError):
        return "网络异常或麦当劳接口暂时不可用，请稍后重试。"
    return "运行出错了。请加上 -v 重新运行查看详情，或把输出反馈到项目的 GitHub Issue。"


def cmd_stores(a) -> int:
    from .mcp import McdMcp
    from .stores import search, server_now
    try:
        m = McdMcp()
        stores = search(m, a.city, a.near)
        date, now = server_now(m)
    except Exception as e:
        log.debug("stores 失败", exc_info=True)
        print(friendly_error(e))
        return 3
    for s in stores:
        p = s.period_at(date, now)
        state = f"{p.name}供应中" if s.open_now and p else ("营业中，现在是餐段空档" if s.open_now else "暂停营业")
        print(f"{s.code}  {s.name}  {s.distance_m} 米  {s.hours[0]}–{s.hours[1]}  {state}")
    return 0


def _pick_store(m, city: str, near: str, reservation: str | None, tries: int = 3):
    """选最近的、现在（或指定时间）能点餐的门店。餐段空档自动预约下一餐段的开始时间。"""
    from .mcp import McdBusinessError
    from .stores import search, server_now
    stores = search(m, city, near)
    date, now = server_now(m)
    for s in [s for s in stores if s.open_now][:tries]:
        res = reservation
        if not res and s.period_at(date, now) is None:
            nxt = s.next_orderable(date, now)
            if nxt is None:
                continue
            res = f"{nxt[0]} {nxt[1]}"
        try:
            cat = load_live(m, s.code, res)
        except McdBusinessError as e:
            if str(e.code) == "600057":   # 门店临时停业或餐段切换
                log.info("%s 暂时点不了（%s），换下一家", s.name, e.message)
                continue
            raise
        cat.slot = res or f"{date} {now}"
        cat.store_name = f"{s.name}（{s.address}，约 {s.distance_m} 米）"
        return cat
    return None


class UserError(Exception):
    """给用户看的错误（不含内部细节）。"""


def _load_catalog(a):
    if a.offline:
        return load_fixture(Path(a.offline)), None
    from .mcp import McdMcp
    m = McdMcp()
    if a.near:
        if not a.city:
            raise UserError("用 --near 时请同时给出 --city，例如 --city 上海 --near 人民广场")
        cat = _pick_store(m, a.city, a.near, a.reservation)
        if cat is None:
            raise UserError("附近的门店现在都点不了餐，可以换个地点，或用 --reservation 预约其他时间。")
    else:
        cat = load_live(m, a.store, a.reservation)
        if not a.reservation:
            from .stores import server_now
            cat.slot = " ".join(server_now(m))
    return cat, m


def _burger_signature(p) -> tuple:
    """「多样」：同一种汉堡（不论去不去配料）只留最便宜的一套。"""
    return burgers_of([it.name for o in p.options for it in o.items])


def _plan(a, cat):
    """求解；该部位的餐品蛋白密度不够时（如麦乐鸡裹粉油炸），放宽为「至少包含一样」，并如实说明。"""
    table, lib, modmap = load_core()
    builder = Builder(table, lib, modmap, TRAIN_RULES)
    share = 0.5 if a.train else 0.0
    # 「加练」最多到上限的 125%，展开选项时按这个放宽
    options = builder.options(cat, allow_split=not a.no_split, kcal_max=a.kcal_max * 1.25, share=share)
    if a.healthy:
        before = len(options)
        options = [o for o in options if all(healthy(it.name) for it in o.items)]
        log.info("健康配餐：选项 %d → %d（小食只要苹果片、玉米杯，饮料只要无糖的，汉堡只要牛肉堡和板烧）", before, len(options))
    tags = frozenset({a.train}) if a.train else frozenset()
    c = Constraints(kcal_max=a.kcal_max, protein_min=a.protein_min, carb_max=a.carb_max, fat_max=a.fat_max,
                    sodium_max=a.sodium_max, budget_cents=round(a.budget * 100) if a.budget is not None else None,
                    max_items=a.max_items, require_tags=tags, tag_protein_share=share,
                    meal=parse_meal(a.meal) if a.meal else ())
    # 指定了一餐的结构时，几套方案用不同的汉堡（多样）；否则按「实质相同」去重
    distinct = _burger_signature if a.meal else plan_signature
    if tags and not any(o.tags & tags for o in options):
        part_food = {"练腿": "鸡腿、琵琶腿", "练胸": "麦乐鸡、鸡块、鸡柳", "练背": "里脊", "练手臂": "鸡翅"}[a.train]
        raise UserError(f"这家店现在没有「{a.train}」的餐品（{part_food}），换个部位或换家店试试。")
    plans = solve(options, c, top_k=a.top, distinct_key=distinct)
    notice = None
    if not plans and tags:
        from dataclasses import replace
        c = replace(c, tag_protein_share=0.0)
        plans = solve(options, c, top_k=a.top, distinct_key=distinct)
        if plans:
            notice = f"只靠「{a.train}」的餐品凑不够这么多蛋白质（热量会超），下面的方案以它为辅、其他餐品补蛋白。"
    if not plans:
        raise UserError(_why_infeasible(a, options, c))
    return plans, options, c, notice, builder


def _why_infeasible(a, options, c: Constraints) -> str:
    """逐个放宽可选条件重解，告诉用户是哪个条件卡住了。"""
    from dataclasses import replace
    tries = [("预算", c.budget_cents is not None, dict(budget_cents=None)),
             ("碳水上限", c.carb_max is not None, dict(carb_max=None)),
             ("脂肪上限", c.fat_max is not None, dict(fat_max=None)),
             ("钠上限", c.sodium_max is not None, dict(sodium_max=None)),
             ("最多几样", c.max_items < 6, dict(max_items=6))]
    blockers = [name for name, active, change in tries
                if active and solve(options, replace(c, **change), top_k=1)]
    if blockers:
        return f"在这些条件下找不到方案，卡住的是：{'、'.join(blockers)}。放宽其中一项就有解。"
    hint = "可以放宽热量上限或降低蛋白质目标"
    if a.no_split:
        hint += "，或去掉 --no-split 允许到手只吃馅"
    return f"在这些条件下找不到方案。{hint}。"


def cmd_plan(a) -> int:
    try:
        cat, m = _load_catalog(a)
        plans, options, c, notice, builder = _plan(a, cat)
        extras = _extras(builder, cat, plans, c)
        checks = {}
        if a.verify:
            from .mcp import McdMcp
            from .pricing import verify
            m = m or McdMcp()
            for i, p in enumerate(plans):
                checks[i] = verify(m, cat, p, reservation=cat.reservation)
    except UserError as e:
        return _fail(a, str(e), 1)
    except Exception as e:   # Token、网络、接口、程序错误：分开给友好提示，详情用 -v 看
        log.debug("plan 失败", exc_info=True)
        return _fail(a, friendly_error(e), 3)
    bonuses = [_bonus(options, p, c, a.train) for p in plans]
    if a.format == "json":
        # JSON 一律 ASCII 转义：智能体在中文 Windows 上用管道读取时不会因 GBK 解码出错
        print(json.dumps(_plans_json(a, cat, plans, bonuses, checks, notice, extras), ensure_ascii=True, indent=1))
        return 0
    if cat.store_name:
        print(f"门店：{cat.store_name}" + (f"，预约 {cat.reservation}" if cat.reservation and not a.reservation else ""))
    if notice:
        print(f"提示：{notice}")
    for i, p in enumerate(plans):
        print(f"\n—— 方案 {i + 1} ——")
        if a.style == "gym":
            print(render_gym(p, a.train, bonuses[i], cat.slot, checks.get(i), extras[i]))
        else:
            print(render_plain(p, checks.get(i), cat.slot))
    return 0


def _fail(a, message: str, code: int) -> int:
    if getattr(a, "format", "text") == "json":
        print(json.dumps({"ok": False, "error": message}, ensure_ascii=True))
    else:
        print(message)
    return code


def _nut(n) -> dict:
    return {"kcal": round(n.kcal), "protein_g": round(n.protein, 1), "carb_g": round(n.carb, 1),
            "fat_g": round(n.fat, 1), "sodium_mg": round(n.sodium)}


def _extras(builder, cat, plans, c: Constraints) -> list[dict]:
    """每个方案的差异化信息：方案里汉堡的几种吃法（最多两样）、门店官方「N 大卡套餐」的对比（各方案共用）。"""
    from .compare import eat_ladder, official_sets
    from .render import _is_light
    official = official_sets(builder, cat, c)
    out = []
    for p in plans:
        ladders, seen = [], set()
        for o, _ in p.counts():
            for it in o.items:
                if _is_light(it) or it.name in seen:
                    continue
                rungs = eat_ladder(builder, cat, it.name, it.how)
                if len(rungs) >= 2:
                    seen.add(it.name)
                    ladders.append((it.name, rungs))
        out.append({"ladders": ladders[:2], "official": official, "constraints": c})
    return out


def _plans_json(a, cat, plans, bonuses, checks, notice, extras=None) -> dict:
    """给智能体用的结构化结果：可直接作为 calculate-price / create-order 的 items。"""
    from .pricing import items_for
    from .render import MEAL_WORDS, meal_of
    now_word, next_word = MEAL_WORDS[meal_of(cat.slot)]
    out = []
    for i, p in enumerate(plans):
        chk = checks.get(i)
        out.append({
            "rank": i + 1,
            "price_yuan": p.price_cents / 100,
            "price_check": None if chk is None else {"ok": chk.ok, "actual_yuan": None if chk.actual_cents is None
                                                     else chk.actual_cents / 100, "message": chk.message},
            "this_meal": _nut(p.tonight),
            "next_meal": _nut(p.leftover) if p.leftover.kcal > 0 else None,
            "order_lines": [f"{n} × {o.label.replace('（整份吃）', '')}" for o, n in p.counts()],
            "how_to_eat": [{"name": it.name, "how": it.how} for o, n in p.counts() for it in o.items
                           if it.how != "整份吃"],
            "footnotes": p.footnotes,
            "card": render_gym(p, a.train, bonuses[i], cat.slot, chk, extras[i] if extras else None),
            "eat_options": [{"name": name, "options": [{"how": r.how, "this_meal": _nut(r.tonight),
                                                         "next_meal": _nut(r.leftover) if r.leftover.kcal > 0 else None,
                                                         "chosen": r.chosen} for r in rungs]}
                            for name, rungs in (extras[i]["ladders"] if extras else [])],
            "calculate_price_items": items_for(p, cat),
        })
    return {
        "ok": True,
        "store": {"code": cat.store_code, "name": cat.store_name or None, "reservation": cat.reservation},
        "meal_words": {"this": now_word, "next": next_word},
        "order_args": {"storeCode": cat.store_code, "orderType": 1, "beType": 1,
                       **({"reservationDate": cat.reservation} if cat.reservation else {})},
        "notice": notice,
        "official_sets": [{"name": x.name, "category": x.category, "price_yuan": x.price_cents / 100,
                           "whole": _nut(x.whole), "lowest": _nut(x.lowest), "lowest_hows": list(x.lowest_hows),
                           "meets_target_whole": x.fits_whole} for x in (extras[0]["official"] if extras else [])],
        "plans": out,
    }


def _bonus(options, plan, c: Constraints, part: str | None):
    """「加练」：在热量上限的 125% 以内，再单点一样整份吃的训练动作（带部位标签的鸡肉类，指定部位时只看该部位），
    蛋白质最多、其次最便宜。只考虑整份吃：建议里不写吃法时，用户会按整份吃。已经点到份数上限的不再建议。
    不建议饮料和甜品：「加练」得是一个动作。"""
    t = plan.tonight
    have = {o.id: n for o, n in plan.counts()}
    cands = [o for o in options if o.payload and o.payload[0] == "single" and not o.payload[2] and not o.payload[3]
             and o.tonight.protein >= 8 and t.kcal + o.tonight.kcal <= c.kcal_max * 1.25
             and have.get(o.id, 0) < c.max_copies and (part in o.tags if part else bool(o.tags))]
    return max(cands, key=lambda o: (o.tonight.protein, -o.price_cents), default=None)


def _positive(kind):
    def parse(v: str):
        x = kind(v)
        if x <= 0:
            raise argparse.ArgumentTypeError(f"必须是正数：{v}")
        return x
    return parse


def _non_negative(v: str) -> float:
    x = float(v)
    if x < 0:
        raise argparse.ArgumentTypeError(f"不能是负数：{v}")
    return x


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="mcdstrip", description="麦麦健身餐规划师（Gyᗰ 麦门健身房）：健身人群的麦当劳点餐求解器")
    ap.add_argument("-v", "--verbose", action="store_true")
    sub = ap.add_subparsers(dest="cmd", required=True)
    lib = sub.add_parser("library", help="构建并打印配料库")
    lib.add_argument("--out")
    st = sub.add_parser("stores", help="按城市和地点搜索附近门店（需要 MCD_MCP_TOKEN）")
    st.add_argument("--city", required=True)
    st.add_argument("--near", required=True, help="地点关键词，如 人民广场")
    pl = sub.add_parser("plan", help="按约束求最优点法")
    pl.add_argument("--kcal-max", type=_positive(float), required=True)
    pl.add_argument("--protein-min", type=_non_negative, default=0)
    pl.add_argument("--carb-max", type=_non_negative)
    pl.add_argument("--fat-max", type=_non_negative)
    pl.add_argument("--sodium-max", type=_non_negative)
    pl.add_argument("--budget", type=_non_negative, help="预算上限（元）")
    pl.add_argument("--max-items", type=_positive(int), default=4)
    pl.add_argument("--no-split", action="store_true", help="不考虑到手自拆")
    pl.add_argument("--train", choices=sorted({t for _, t in TRAIN_RULES}), help="今日训练部位")
    pl.add_argument("--style", choices=["plain", "gym"], default="plain")
    pl.add_argument("--format", choices=["text", "json"], default="text", help="json 供智能体调用：含算价参数与训练卡文字")
    pl.add_argument("--top", type=_positive(int), default=3)
    pl.add_argument("--meal", choices=MEALS, help="一餐的结构：每套方案恰好一个汉堡 + 一份小食 + 一杯饮料等；几套方案用不同的汉堡")
    pl.add_argument("--healthy", action="store_true", help="健康配餐：小食只要苹果片、玉米杯，饮料只要无糖的，汉堡只要牛肉堡和板烧")
    src = pl.add_mutually_exclusive_group(required=True)
    src.add_argument("--offline", help="门店快照目录")
    src.add_argument("--store", help="门店编码（实时查询，需要 MCD_MCP_TOKEN）")
    src.add_argument("--near", help="地点关键词，自动选最近的能点餐门店（配合 --city，需要 MCD_MCP_TOKEN）")
    pl.add_argument("--city", help="城市，配合 --near 使用")
    pl.add_argument("--reservation", help="预约时间 YYYY-MM-DD HH:MM")
    pl.add_argument("--verify", action="store_true", help="用算价接口核对价格（需要 Token）")
    a = ap.parse_args(argv)
    # 中文 Windows 的控制台和管道默认是 GBK，编不进 ᗰ 和 emoji：统一输出 UTF-8
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.WARNING, format="%(levelname)s %(name)s %(message)s")
    return {"library": cmd_library, "stores": cmd_stores, "plan": cmd_plan}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
