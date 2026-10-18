"""官方营养表（list-nutrition-foods）解析与餐品名称归一。

接口返回一段紧凑表格文本：首行形如 `[160]{productName,nutritionDescription,energyKj,...}:`，
其后每行一个餐品、逗号分隔。数值是整数（或空），单位：能量 kcal/kJ，蛋白质/脂肪/碳水 g，钠/钙 mg。
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

log = logging.getLogger(__name__)

NUTRIENTS = ("kcal", "protein", "fat", "carb", "sodium", "calcium")
_FIELD = {"energyKcal": "kcal", "protein": "protein", "fat": "fat", "carbohydrate": "carb",
          "sodium": "sodium", "calcium": "calcium"}


@dataclass(frozen=True)
class Nutrition:
    kcal: float = 0.0
    protein: float = 0.0
    fat: float = 0.0
    carb: float = 0.0
    sodium: float = 0.0
    calcium: float = 0.0

    def vec(self) -> tuple[float, ...]:
        return tuple(getattr(self, k) for k in NUTRIENTS)

    @classmethod
    def from_vec(cls, v) -> "Nutrition":
        return cls(*[float(x) for x in v])

    # 加减在求解和选项展开里会被调用几十万次，逐字段写开比经由 vec() 快约 5 倍
    def __add__(self, o: "Nutrition") -> "Nutrition":
        return Nutrition(self.kcal + o.kcal, self.protein + o.protein, self.fat + o.fat, self.carb + o.carb,
                         self.sodium + o.sodium, self.calcium + o.calcium)

    def __sub__(self, o: "Nutrition") -> "Nutrition":
        return Nutrition(self.kcal - o.kcal, self.protein - o.protein, self.fat - o.fat, self.carb - o.carb,
                         self.sodium - o.sodium, self.calcium - o.calcium)

    def scale(self, k: float) -> "Nutrition":
        return Nutrition.from_vec(a * k for a in self.vec())

    def clamped(self) -> "Nutrition":
        """负值截为 0：官方整份减去配料估计值时，小营养素（钠、钙）可能出现 −1 这类误差。"""
        return Nutrition(*(max(0.0, x) for x in self.vec()))

    def rounded(self) -> "Nutrition":
        return Nutrition.from_vec(round(a) for a in self.vec())


ZERO = Nutrition()
LIGHT_KCAL = 20.0


def negligible(n: Nutrition) -> bool:
    """近零热量、几乎无蛋白（无糖可乐、红茶、美式）：这类饮品彼此可互换，不必区分。"""
    return n.kcal < LIGHT_KCAL and n.protein < 1


def parse_table(raw: str) -> dict[str, Nutrition]:
    """解析紧凑表格文本。重复的餐品名保留第一条并记录日志（官方表里确有重复条目）。"""
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    m = re.search(r"\{(.+?)\}", lines[0])
    if not m:
        raise ValueError("营养表首行格式不符合预期")
    header = m.group(1).split(",")
    out: dict[str, Nutrition] = {}
    for ln in lines[1:]:
        cells = ln.split(",")
        if len(cells) != len(header):
            log.warning("营养表行列数不符，跳过：%s", ln[:60])
            continue
        row = dict(zip(header, cells))
        name = row["productName"].strip()
        vals = {}
        for src, dst in _FIELD.items():
            v = row.get(src, "").strip()
            vals[dst] = float(v) if v not in ("", "null") else 0.0
        if name in out:
            if out[name] != Nutrition(**vals):
                log.info("营养表重复条目且数值不同，保留第一条：%s", name)
            continue
        out[name] = Nutrition(**vals)
    return out


_ALIASES = {
    "薯条": "中薯条",          # 菜单单点「薯条」默认中份
    "麦乐鸡": "麦乐鸡5块",
    "鱼排堡": "儿童鱼排堡",                     # 开心乐园餐里的 504642，营养表按「儿童鱼排堡」列
    "原味双层深海鳕鱼堡": "双层深海鳕鱼堡",      # 520312 原味款就是营养表里的默认款
    "纯牛奶(盒装)": "纯牛奶（盒装）",
    "麦辣鸡翅": "麦辣鸡翅-2块",
    "可乐": "可乐中杯",
    "纯牛奶": "纯牛奶（盒装）",
    "100%苹果汁（盒装）": "100%苹果汁",
    "苹果片一袋（60g）": "苹果片",
}
# 菜单和套餐选项的写法五花八门，先按规则改写成营养表的写法，再查别名
_RULES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"^麦咖啡™?"), ""),                          # 麦咖啡™冰美式中杯 → 冰美式中杯
    (re.compile(r"^(\d+)块(麦乐鸡)$"), r"\2\1块"),            # 5块麦乐鸡 → 麦乐鸡5块
    (re.compile(r"^(麦乐鸡)-(\d+块)$"), r"\1\2"),              # 麦乐鸡-5块 → 麦乐鸡5块
    (re.compile(r"^(麦辣鸡翅)(\d+块)$"), r"\1-\2"),            # 麦辣鸡翅2块 → 麦辣鸡翅-2块
    (re.compile(r"^可口可乐（([小中大])杯）$"), r"可乐\1杯"),     # 可口可乐（小杯）→ 可乐小杯
    (re.compile(r"^(雪碧)（([小中大])杯）$"), r"\1\2杯"),
]
_PIECES = re.compile(r"^(.+?)-?(\d+)(块|根|只)$")


def normalize(name: str) -> str:
    """菜单名 → 营养表名的归一：统一全半角括号与空格，按规则改写，再查别名表。"""
    n = name.replace("(", "（").replace(")", "）").replace(" ", "").strip()
    if name in _ALIASES:
        return _ALIASES[name]
    for pat, repl in _RULES:
        n = pat.sub(repl, n)
    return _ALIASES.get(n, n)


def pieces(name: str) -> tuple[str, int, str] | None:
    """「麦辣鸡翅-4块」→ (麦辣鸡翅, 4, 块)，用于按块数从同名餐品换算营养。"""
    m = _PIECES.match(name)
    return (m.group(1), int(m.group(2)), m.group(3)) if m else None
