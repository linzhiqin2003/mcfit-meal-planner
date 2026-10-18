# 接下来的 TODO（2026-10-15 起，截止 10/25 23:59）

来源：我的待办，加上一次独立的提交前审计（干净克隆、临时 HOME、无 Token 复现）。工时为估计。

## 已完成

- [x] 安装后的 Skill 每次运行都会失败，因为 `install.py` 漏装了配料名文件。现在安装时带上全部参考数据和一份门店快照，没有 Token 也能演示。新增安装后测试（d92743f）
- [x] 缺 Token、Token 失效、接口业务错误、网络异常原来一律提示「网络异常」，现在分开提示；`stores` 子命令不再直接打出错误堆栈
- [x] 中文 Windows（GBK）下读文件和输出会崩：文件读写统一 UTF-8，输出强制 UTF-8，JSON 用 ASCII 转义
- [x] （原 P0-1）安装和 MCP 配置文档按 macOS / Windows 分开写：`install.py` 不带参数时自动装进已有的 WorkBuddy 和 Claude Code，装完按系统给出 Token 设置命令；Claude Code 用 `claude mcp add --transport http`（手写 JSON 写 `"http"`）；WorkBuddy 写明把 `${MCD_MCP_TOKEN}` 换成 Token 原文；缺 Token 的报错按系统给出命令（Windows 用 PowerShell 的 `SetEnvironmentVariable`，不用 setx，因为它会截断超过 1024 字符的值；macOS 按 zsh / bash 写对应的配置文件），并提醒从新终端重开客户端；Codex 二审 9 条意见已全部处理（自查漏报 setx / JSON 写法的 Token、中文用户名和 JSON 转义路径；测试依赖本机 SHELL；核价脚本部分失败仍报成功；README 里 Token「不写进任何文件」的说法不准确）；最低版本降到 Python 3.9（macOS 自带版本，实测全部测试通过），CI 加 windows-latest、macos-latest 和 3.9
- [x] （原 P0-2）已跟踪文件里的 5 处本机绝对路径改成相对路径或文字说明（`docs/research` 4 处、`assets/3d/BRIEF.md` 1 处）；新增 `scripts/check_publish.py` 推送前自查本机路径和 Token，`test_publish` 守着已跟踪的文件
- [x] （原 P0-3）改掉不准确的说法：拆分误差按实测改为「中位约 ±13 大卡，九成在 ±30 以内」（544 种吃法统计）；README 主例子注明高达吉士双牛堡是估算（约 ±27 大卡），并给出只用官方数据的方案（¥28.8）；「每份配方都多轮核查」改为「33 份里 32 份经过一轮独立核查」；「详情写在本地日志」改为「加 -v 输出到终端，不写文件」；CHANGELOG 旧条目里的测试数是当时的记录，保留不改，新条目写现在的数字

## P0 发布前必须做

| # | 事项 | 谁 | 工时 |
|---|---|---|---|
| 3a | **补核价证据**：设置好 Token 后运行 `python3 scripts/price_check_record.py`，生成 `docs/research/price_check_<日期>.json`（不含 Token），MCP_INTEGRATION 的 9/9 改为引用这份记录 | 需要你的 Token | 0.2h |
| ~~3b~~ | ~~推送前清理~~：已完成（10/18）。`assets/3d` 和 `videos/` 不入库，`main` 是单次提交，`master` 留作本地完整历史 | — | — |
| ~~4~~ | ~~建公开仓库~~：已完成（10/18 18:45 创建）。未登录可读到 4 个必需文件，参赛声明与官方逐字节一致；CI 五个环境通过（修了 Windows 下测试的编码问题）；Pages 已部署 linzhiqin2003.github.io/maimen-gym | — | — |
| 5 | **发报名 Issue**：正文 4 行、不空行、不用 Markdown。项目名建议写「麦门健身房 maimen-gym」，因为 ᗰ 这种符号有被格式校验拒绝的风险 | 你拍板时间 | 0.2h |
| 6 | 实际使用验收：在 WorkBuddy 和 Claude Code 里各装一遍，用真实 Token 从对话一路走到核价；**Windows 还没在真机上装过**（WorkBuddy 的技能目录按 `%USERPROFILE%\.workbuddy\skills` 推断），推送后先看 CI 的 Windows 结果，有条件再找一台 Windows 实装；**macOS 上从程序坞打开的 WorkBuddy 能不能读到 `~/.zshrc` 里的 Token 也没实测**（README 给了 `launchctl setenv` 兜底），验收时顺带确认 | 需要你的 WorkBuddy | 1h |

## P1 拉 Star 的门面（建议 10/16–10/20 完成）

| # | 事项 | 工时 |
|---|---|---|
| 7 | **Portal**：从 4 版 mockup 里选一版，做成可交互的 GitHub Pages 页面（预先算好一批「热量 × 蛋白质 × 部位」组合的结果，不需要 Token） | 4–6h |
| 8 | 可分享的训练卡图片：`--format png`，用无头 Chrome 出图（本机 Pillow 会卡死，不能用），智能体回复时附上图片 | 3–4h |
| 9 | README 首屏重写：训练卡图片，加一句和同类作品的区别，再加不需要 Token、30 秒能试的命令和徽章；配好仓库简介、标签、社交预览图（已报名的 615 个作品里有 102 个做健身或蛋白质，必须一眼看出我们的「拆着吃」和开放数据集） | 1.5h |
| 10 | 演示 GIF 或 30 秒短片 | 2h |
| 11 | 第一次实时查询至少要 14 秒（约 119 个餐品详情），期间没有任何提示：~~SKILL.md 让智能体先告诉用户要等一会儿~~（已加），脚本在 stderr 输出进度 | 0.3h |
| 12 | ~~支持 Python 3.9，CI 加 3.9 和 windows-latest；README 里改写成 `python3`~~（已随 P0-1 完成） | — |
| 13 | 打一个 zip 发到 GitHub Release，方便在 WorkBuddy 直接上传 Skill 文件夹 | 0.5h |
| 14 | 估算品排第一的问题：同价时优先官方营养表里有的餐品，卡片上的「估算」标注再醒目一些 | 1h |
| 15 | 「麦乐鸡是鸡胸肉」补上出处，找不到就换个说法 | 0.3h |
| 16 | 官方营养表刷新命令（实时调用 `list-nutrition-foods`），输出里注明数据日期 | 1h |
| 17 | 发布前做一次整体二审（Codex 独立审查） | 并行 |

## P2 有余力再做

- 中文社区传播：小红书、即刻、V2EX、掘金，配演示 GIF。**不参加互赞群**，规则把操纵 Star 列为取消资格
- 支持麦乐送（外送）；早餐卡提示：经常吃早餐的人带卡更省
- 还有 15 个新品没有营养数据（早安营养卷等），补配方
- 800 大卡以上的查询要 6–15 秒，可以缓存选项来提速
- `workbuddy.md`：只有真在 WorkBuddy 里开发、使用过才导出，不补假的

参考水位（10/15 21:00 排行榜）：进前 100 要 9 个 Star，第 3 名是 244 个。
