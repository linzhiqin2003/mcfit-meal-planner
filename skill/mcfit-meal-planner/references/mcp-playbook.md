# 麦当劳 MCP 调用手册（本 Skill 用到的部分）

服务地址 `https://mcp.mcd.cn`（Streamable HTTP），请求头 `Authorization: Bearer <Token>`。Token 在 [open.mcd.cn/mcp](https://open.mcd.cn/mcp) 申请。

所有业务错误都返回 HTTP 200，看返回里的 `code`：200 才是成功。

## 脚本自动调用的（只读和核价）

| 工具 | 用途 | 关键参数 |
|---|---|---|
| `query-nearby-stores` | 按城市和地点找门店 | `searchType=2`、`city`、`keyword`、`beType=1` |
| `now-time-info` | 麦当劳服务器时间，判断餐段 | 无 |
| `query-meals` | 门店当前（或预约时间）的菜单和价格 | `storeCode`、`orderType=1`、`beType=1`、`reservationDate`（可选） |
| `query-meal-detail` | 餐品可去的配料、套餐每组的可选项和份数 | 同上加 `code` |
| `list-nutrition-foods` | 官方营养表 | 无 |
| `calculate-price` | 核价，返回 `takeWayList`（堂食、外带） | 同上加 `items` |

## 由你调用的（必须用户确认）

| 工具 | 什么时候 | 参数 |
|---|---|---|
| `create-order` | 用户明确说「下单」之后 | `order_args` + `items` + `takeWayCode`（来自 `calculate-price` 的 `takeWayList`） |
| `query-order` | 用户问订单状态 | `orderId` |

`items` 直接用脚本输出的 `calculate_price_items`。它的格式：

- 单品：`{"productCode", "quantity", "modification"?}`；
- 套餐：`{"productCode", "quantity", "roundList": [{"round", "comboItemList": [{"code", "quantity", "modification"?}]}]}`。每组要选够规定份数（如「主食任意选」2 份）；
- 去配料：`modification.values` 要把这一组配料**全部**传上，保留的传 `selectedKey`、数量 1，去掉的传 `unselectedKey`、数量 0。漏传的配料会被静默恢复成默认。

## 常见错误码

| code | 含义 | 怎么办 |
|---|---|---|
| 600057 | 门店临时停业，或正处在餐段切换的空档 | 脚本会自动换下一家或预约下一餐段；手动调用时换门店或加 `reservationDate` |
| 600014 | 地点搜不到 | 请用户换个地点关键词，例如地铁站或商场名 |
| 600012 | 优惠券用错了编码 | 本 Skill 不处理优惠券 |

## 价格的坑

菜单里标着「随单购麦金卡优惠」「随单购早餐卡优惠」的商品，`currentPrice` 要连同会员卡一起买才有。不带卡算价按 `originalPrice` 收，带卡会多一张卡的钱（麦金卡体验卡 ¥9.9、6 折满分早餐卡 ¥11.9）。脚本按原价算，不替用户买卡。
