"""一餐的结构（如「汉堡 + 小食 + 饮料」）与健康配餐。

用户常这样点：一个汉堡、一份小食、一杯饮料。--meal 让每套方案恰好由这几类各一份组成（套餐里带的和单点的都算）；
--healthy 只用少油炸、无糖的东西：小食苹果片 / 玉米杯，饮料无糖可乐 / 锡兰红茶 / 纯牛奶 / 美式 / 纯悦，
汉堡只用牛肉堡和板烧（不油炸）。默认仍是价格优先，两项都是可选的。

餐品分类只看名字：先判汉堡（「堡」「巨无霸」「麦香鸡」「麦香鱼」「卷」），再判饮料，再判小食；都不是的（玩具等）记作 other，
不计入结构。新菜单出现没见过的名字时落到 other，不会被误当成某一类。
"""
from __future__ import annotations

from collections import Counter

BURGER_KEYS = ("堡", "巨无霸", "麦香鸡", "麦香鱼", "多笋卷", "麦满分")
DRINK_KEYS = ("可乐", "雪碧", "芬达", "怡泉", "纯悦", "红茶", "奶茶", "咖啡", "美式", "奶铁", "拿铁", "卡布奇诺",
              "黑巧", "牛奶", "燕麦奶", "果汁", "苹果汁", "橙橙", "柠柠", "鲜萃冰咖", "豆浆")
SIDE_KEYS = ("薯条", "薯饼", "扭扭薯", "玉米杯", "苹果片", "麦乐鸡", "鸡翅", "V翅", "鸡柳", "鸡块", "鸡球", "脆汁鸡",
             "肉骨鸡", "鸡排", "芝士条", "派", "新地", "麦旋风", "冰淇淋", "鸡架")

HEALTHY_BURGER = ("牛", "巨无霸", "吉士汉堡", "汉堡包", "板烧")
HEALTHY_SIDE = ("苹果片", "玉米杯")
HEALTHY_DRINK = ("无糖可口可乐", "无糖可乐", "锡兰红茶", "纯牛奶", "美式", "纯悦")
UNSWEETENED_MILK = ("牛奶",)          # 套餐里写作「牛奶」的就是纯牛奶；「抹茶牛奶」等调味奶不算

ROLE_NAMES = {"汉堡": "burger", "小食": "side", "饮料": "drink"}
MEALS = ("汉堡+小食+饮料", "汉堡+饮料", "汉堡+小食")


def role(name: str) -> str:
    """burger / drink / side / other。"""
    if any(k in name for k in BURGER_KEYS):
        return "burger"
    if any(k in name for k in DRINK_KEYS):
        return "drink"
    if any(k in name for k in SIDE_KEYS):
        return "side"
    return "other"


def healthy(name: str) -> bool:
    r = role(name)
    if r == "burger":
        return any(k in name for k in HEALTHY_BURGER)
    if r == "side":
        return any(k in name for k in HEALTHY_SIDE)
    if r == "drink":
        return any(k in name for k in HEALTHY_DRINK) or name in UNSWEETENED_MILK
    return True


def parse_meal(text: str) -> tuple[tuple[str, int], ...]:
    """「汉堡+小食+饮料」→ (("burger", 1), ("drink", 1), ("side", 1))，按角色名排序，作为约束里的不可变值。"""
    c = Counter()
    for part in text.split("+"):
        part = part.strip()
        if part not in ROLE_NAMES:
            raise ValueError(f"不认识的餐品类别：{part}（可用：汉堡、小食、饮料）")
        c[ROLE_NAMES[part]] += 1
    return tuple(sorted(c.items()))


def role_vec(names) -> tuple[int, int, int]:
    """(汉堡数, 小食数, 饮料数)。"""
    c = Counter(role(n) for n in names)
    return c["burger"], c["side"], c["drink"]


def meal_target(meal: tuple[tuple[str, int], ...]) -> tuple[int, int, int]:
    d = dict(meal)
    return d.get("burger", 0), d.get("side", 0), d.get("drink", 0)


def burgers_of(names) -> tuple[str, ...]:
    return tuple(sorted(n for n in names if role(n) == "burger"))
