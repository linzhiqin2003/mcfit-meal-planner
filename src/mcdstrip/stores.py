"""门店：按城市 + 地点关键词搜索附近门店，解析营业时间与可预约餐段。

query-nearby-stores 的可预约时段是一段文字，例如
    "宵夜(00:00至04:45,22:14至23:59)，早餐(05:14至10:15)，午餐(10:44至14:15)"
餐段之间有空档（如 10:15–10:44），空档里查菜单会返回 600057，需要换一个预约时间。
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

log = logging.getLogger(__name__)

_PERIOD = re.compile(r"([^，,()（）]+)[(（]([^)）]+)[)）]")
_RANGE = re.compile(r"(\d{1,2}:\d{2})\s*至\s*(\d{1,2}:\d{2})")


@dataclass(frozen=True)
class Period:
    name: str      # 早餐 / 午餐 / 下午茶 / 夜市 / 宵夜
    start: str     # HH:MM
    end: str       # HH:MM

    def contains(self, hhmm: str) -> bool:
        return self.start <= hhmm <= self.end


@dataclass(frozen=True)
class ReservationDay:
    date: str
    today: bool
    periods: tuple[Period, ...]


@dataclass(frozen=True)
class Store:
    code: str
    name: str
    address: str
    distance_m: int
    open_now: bool
    hours: tuple[str, str]
    days: tuple[ReservationDay, ...] = field(default=())

    def period_at(self, date: str, hhmm: str) -> Period | None:
        for d in self.days:
            if d.date == date:
                return next((p for p in d.periods if p.contains(hhmm)), None)
        return None

    def next_orderable(self, date: str, hhmm: str) -> tuple[str, str, Period] | None:
        """当前时刻之后最早能点餐的（日期, 时刻, 餐段）；当前就在餐段内时返回当前时刻。"""
        for d in self.days:
            if d.date < date:
                continue
            for p in sorted(d.periods, key=lambda p: p.start):
                if d.date == date and p.end < hhmm:
                    continue
                at = hhmm if d.date == date and p.start <= hhmm else p.start
                return d.date, at, p
        return None


def parse_periods(text: str) -> tuple[Period, ...]:
    out = []
    for name, body in _PERIOD.findall(text or ""):
        for start, end in _RANGE.findall(body):
            out.append(Period(name.strip(), start.zfill(5), end.zfill(5)))
    return tuple(sorted(out, key=lambda p: p.start))


def parse_store(raw: dict) -> Store:
    days = tuple(ReservationDay(d.get("date", ""), bool(d.get("today")), parse_periods(d.get("reservationOptionText", "")))
                 for d in raw.get("reservationTimeOptions") or [])
    return Store(
        code=str(raw["storeCode"]),
        name=raw.get("storeName", ""),
        address=raw.get("address", ""),
        distance_m=int(raw.get("distance") or 0),
        open_now=bool(raw.get("businessStatus")),
        hours=(raw.get("businessStartTime", ""), raw.get("businessEndTime", "")),
        days=days,
    )


def parse_stores(data: list[dict]) -> list[Store]:
    return sorted((parse_store(s) for s in data or []), key=lambda s: s.distance_m)


def search(m, city: str, keyword: str, be_type: int = 1) -> list[Store]:
    """按城市 + 地点关键词找附近门店，按距离排序。地点搜不到时 MCP 返回 600014，原样抛出 McdBusinessError。"""
    data = m.data("query-nearby-stores", searchType=2, city=city, keyword=keyword, beType=be_type)
    stores = parse_stores(data)
    log.info("门店搜索 %s %s：%d 家，最近 %s", city, keyword, len(stores), stores[0].name if stores else "无")
    return stores


def server_now(m) -> tuple[str, str]:
    """麦当劳服务器时间（北京时间）：(YYYY-MM-DD, HH:MM)。本机可能不在东八区，不用本地时钟。"""
    d = m.data("now-time-info")
    date, _, time = d["formatted"].partition(" ")
    return date, time[:5]
