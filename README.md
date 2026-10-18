# 麦麦健身餐规划师

> Gyᗰ 麦门健身房 · Go to Gym 不如 Go to ᗰ

健身人群的麦当劳点餐 Skill。告诉它这一顿最多吃多少热量、至少要多少蛋白质（还可以说今天练哪里、想要「汉堡 + 小食 + 饮料」、想吃健康点），它在你附近的麦当劳里算出**最便宜的几种点法**，写成训练计划卡。它有三个本事：

- **配料级营养计算**：官方只给整份营养，它算到每一种配料。双层吉士汉堡整份 429 大卡，下单去吉士 339 大卡，到手只吃牛肉饼和吉士 272 大卡；巨无霸下单去巨无霸酱，513 → 395 大卡。
- **分顿吃配餐建议**：点两个双吉、都下单去吉士，今晚两片面包夹四块牛肉饼（522 大卡、蛋白质 38 g），另外两片面包留到明早当早餐（157 大卡）。
- **多样省钱搭配**：比如 500 大卡以内、蛋白质 25 克以上、汉堡 + 小食 + 饮料、健康配餐，它按价格排出几套用不同汉堡的组合，随心配、三件套自动套上，汉堡还能下单去酱：

| 组合 | 价格 | 这一顿 |
|---|---|---|
| 高达吉士双牛堡 + 小杯玉米杯 + 纯悦 | ¥21.4 | 约 434 大卡 · 蛋白质 26 g |
| 双层吉士汉堡 + 苹果片 + 无糖可乐 | ¥21.9 | 461 大卡 · 蛋白质 27 g |
| 吉士汉堡包 + 小杯玉米杯 + 纯牛奶 | ¥26.0 | 476 大卡 · 蛋白质 25 g |
| 培根蔬萃双层牛堡（下单去酱）+ 小杯玉米杯 + 纯悦 | ¥32.5 | 445 大卡 · 蛋白质 26 g |
| 板烧鸡腿堡 + 小杯玉米杯 + 无糖可乐 | ¥34.0 | 444 大卡 · 蛋白质 25 g |
| 巨无霸（下单去酱）+ 小杯玉米杯 + 无糖可乐 | ¥36.0 | 448 大卡 · 蛋白质 29 g |

（示例门店快照上 `plan --kcal-max 500 --protein-min 25 --meal 汉堡+小食+饮料 --healthy --top 6` 的真实输出；高达吉士双牛堡是新品，营养按配料库估算。）其中第二套写成训练计划卡是这样：

```
Go to Gym 不如 Go to ᗰ
今日训练 🍔

🍎苹果片：1 个一组，共 1 组
🍔双层吉士汉堡：1 个一组，共 1 组

训练量：461 大卡 · 蛋白质 27 g · 碳水 39 g · 脂肪 22 g
会员费：¥21.9

怎么下单：
  1 × 苹果片
  1 × 人气经典随心配：双层吉士汉堡 + 无糖可口可乐中杯

同一个双层吉士汉堡，有这几种练法：
  整份吃：429 大卡，蛋白质 27 g  ← 本方案
  去吉士：339 大卡，蛋白质 21 g
  只吃馅：272 大卡，蛋白质 22 g，面包 157 大卡留到明早
  去吉士 + 只吃馅：182 大卡，蛋白质 16 g，面包 157 大卡留到明早
```

## 它解决什么问题

健身的人想吃麦当劳，难点不在「哪个热量低」，而在：

- **官方只给整份营养。** 双层吉士汉堡 429 大卡、31 克碳水，可如果只吃两块肉饼和芝士呢？面包留着当明天早餐呢？没人告诉你。
- **套餐、加价、单点交织在一起。** 同样的东西，单点、套餐、随心配的价格差很多；随单购的标价要连同会员卡一起买才有。
- **约束一多就算不过来。** 400 大卡以内、蛋白质 30 克以上、碳水尽量少、还要便宜，这是一个组合优化问题。

Gyᗰ 的做法：

1. **配料级营养库。** 用 28 款餐品的官方营养和 33 份配方联合求解出每种配料（肉饼、面包、吉士、各种酱）的营养和误差，参考美国麦当劳官网和 USDA 的配料数据。这样「去吉士」「只吃馅」吃进去多少、留下多少，都能算出来。拆不准的吃法不推荐。
2. **约束求解。** 把门店里每个单品、每个套餐的每种选法、每种吃法展开成选项，用分支定界在热量、蛋白质、碳水、脂肪、钠、预算、训练部位的约束下找最便宜的组合。
3. **实时门店与核价。** 按城市和地点找最近的营业门店，拉实时菜单，用 `calculate-price` 核对价格；用户确认后再下单。

同一家店、同样 400 大卡和 30 克蛋白质：整份吃最便宜是 2 份薄皮焦香V翅，¥32.0；允许只吃馅，2 份「人气经典随心配」高达吉士双牛堡就够，¥27.8，这一顿碳水只有 6 克，面包留作明天的早餐。高达吉士双牛堡是新品，不在官方营养表里，这一份按配料库估算（约 ±27 大卡），卡片上会注明；只用官方营养表里有的餐品，最便宜是麦香鸡去酱和双层吉士汉堡各一份、都只吃馅，¥28.8，碳水 16 克。

## 安装

四步，macOS 和 Windows 都一样。需要 Python 3.9 及以上，只用标准库，不用装依赖：

- **macOS**：系统自带的 `python3` 就够。第一次在终端输入 `python3` 时，如果系统提示安装命令行开发者工具，点「安装」即可。
- **Windows**：从 [python.org](https://www.python.org/downloads/) 下载安装，安装时勾选「Add python.exe to PATH」；也可以在终端运行 `winget install Python.Python.3.12`。

先装好 WorkBuddy 或 Claude Code，并至少打开过一次。

### 1. 下载并安装 Skill

macOS（打开「终端」）：

```bash
git clone https://github.com/linzhiqin2003/maimen-gym.git
cd maimen-gym
python3 install.py
```

Windows（打开 PowerShell 或「终端」）：

```powershell
git clone https://github.com/linzhiqin2003/maimen-gym.git
cd maimen-gym
py install.py
```

没有装 git 也行：在本仓库页面点 **Code → Download ZIP**，解压后在解压出来的文件夹里打开终端，再运行最后一行。Windows 上在文件夹空白处右键选「在终端中打开」；macOS 上先在终端输入 `cd `（末尾有空格），再把文件夹拖进终端窗口、按回车。

`install.py` 会自动装进本机已有的客户端：WorkBuddy 装到 `~/.workbuddy/skills/maimen-gym`，Claude Code 装到 `~/.claude/skills/maimen-gym`（Windows 上 `~` 是 `C:\Users\你的用户名`）。只想装其中一个，就加上 `--target workbuddy` 或 `--target claude`。Windows 上没有 `py` 命令时，把 `py` 换成 `python`。

### 2. 申请 Token

打开 [open.mcd.cn/mcp](https://open.mcd.cn/mcp)，用手机号登录后点右上角「控制台」，点「激活」申请麦当劳 MCP Token，复制下来。

### 3. 设置环境变量 MCD_MCP_TOKEN

脚本取菜单、核价时要用。把下面的「你的Token」换成刚复制的 Token。

macOS（终端）：

```bash
echo 'export MCD_MCP_TOKEN="你的Token"' >> ~/.zshrc
```

终端窗口标题里写的是 bash 而不是 zsh 时，把 `~/.zshrc` 换成 `~/.bash_profile`。

Windows（PowerShell）：

```powershell
[Environment]::SetEnvironmentVariable("MCD_MCP_TOKEN", "你的Token", "User")
```

设置完要关掉所有终端窗口，**完全退出再重新打开** WorkBuddy 或 Claude Code，新的环境变量才会生效（macOS 上按 Command+Q 退出，不是只关窗口；Claude Code 要从新开的终端启动）。如果 macOS 上重开 WorkBuddy 后仍提示缺 Token（有的桌面应用从程序坞打开时不读 shell 配置），在终端再运行 `launchctl setenv MCD_MCP_TOKEN "你的Token"`，然后重开 WorkBuddy；这条设置重启电脑后要重新运行一次。

Token 会以明文保存在你自己电脑上：macOS 在上面那个 shell 配置文件里，Windows 在用户环境变量里，连接 MCP 后客户端的配置里也有一份。Skill 的脚本只读取它，不会写进任何文件或日志。不要把这些配置文件发给别人。

### 4. 连接麦当劳 MCP

**WorkBuddy**：左侧边栏「专家·技能·连接器」→「连接器」→ 右上角「自定义连接器」→「配置 MCP」，粘贴 [mcp-config.example.json](mcp-config.example.json) 的内容，把里面的 `${MCD_MCP_TOKEN}` 换成你的 Token（这里要填 Token 原文，WorkBuddy 不会读环境变量），保存后把 mcd-mcp 设为「启用」。

**Claude Code**：在新开的终端窗口里运行一条命令。它读取第 3 步设好的环境变量，把 Token 存进 Claude Code 的用户配置（`~/.claude.json`），之后在任何目录打开 Claude Code 都能用。

macOS：

```bash
claude mcp add --transport http --scope user mcd-mcp https://mcp.mcd.cn --header "Authorization: Bearer $MCD_MCP_TOKEN"
```

Windows（PowerShell）：

```powershell
claude mcp add --transport http --scope user mcd-mcp https://mcp.mcd.cn --header "Authorization: Bearer $env:MCD_MCP_TOKEN"
```

如果要手写 Claude Code 的 JSON 配置，`type` 要写 `"http"`；照抄 WorkBuddy 那份 `"streamablehttp"` 会报错。

装好后不设 Token 也能先试：对智能体说「用离线快照演示一下」，或者直接运行下面「使用」一节里的离线演示命令。

## 使用

直接和智能体说：

- 「今晚练腿，500 大卡以内，蛋白质 30 克，人民广场附近」
- 「减脂期，晚饭想吃麦当劳，40 块以内，碳水别太高」
- 「明早 7 点半在福州路吃早餐，400 大卡，蛋白质 25 克」
- 「练胸日，600 大卡，麦乐鸡管够」

智能体会运行脚本、贴出训练计划卡，等你说「下单」后再通过麦当劳 MCP 下单。

也可以直接用命令行，在仓库目录下运行（Windows 把 `python3` 换成 `py`）：

```bash
# 离线演示（用仓库里的门店快照，不需要 Token）
python3 skill/maimen-gym/scripts/gym.py plan --kcal-max 500 --protein-min 30 --train 练腿 --offline data/fixtures/stores/1450441/2026-10-16T1900 --style gym

# 实时：自动选最近的营业门店，并核价（需要已设置 MCD_MCP_TOKEN）
python3 skill/maimen-gym/scripts/gym.py plan --kcal-max 500 --protein-min 30 --city 上海 --near 人民广场 --train 练腿 --style gym --verify

# 给智能体用的结构化输出：含算价参数、训练卡文字、餐段说法，在上面的命令后加 --format json
```

| 参数 | 含义 |
|---|---|
| `--kcal-max` / `--protein-min` | 这一顿的热量上限、蛋白质下限 |
| `--city` + `--near` / `--store` | 地点或门店编码 |
| `--reservation "2026-10-16 07:30"` | 预约时间 |
| `--train 练腿` | 训练部位（练腿、练胸、练背、练手臂）：至少一半蛋白质来自这个部位 |
| `--budget` / `--carb-max` / `--fat-max` / `--sodium-max` | 预算和其他上限 |
| `--no-split` | 不接受到手自拆 |
| `--meal 汉堡+小食+饮料` | 每套方案恰好一个汉堡、一份小食、一杯饮料（也可 `汉堡+饮料`、`汉堡+小食`）；几套方案用不同的汉堡 |
| `--healthy` | 健康配餐：小食只要苹果片、玉米杯，饮料只要无糖的，汉堡只要牛肉堡和板烧（默认仍价格优先） |
| `--style gym` / `--format json` | 训练计划卡 / 结构化输出 |
| `--verify` | 用算价接口核对价格 |

## 训练部位

| 部位 | 对应餐品 |
|---|---|
| 练腿 🦵 | 鸡腿、琵琶腿：板烧鸡腿堡、麦辣鸡腿汉堡、麦麦脆汁鸡-琵琶腿 |
| 练胸 💪 | 麦乐鸡（麦乐鸡是鸡胸肉）、鸡块、鸡柳 |
| 练背 🏋️ | 里脊：麦麦脆汁鸡-带骨里脊 |
| 练手臂 🦾 | 鸡翅 |

## 营养怎么算

- 整份营养来自麦当劳官方营养表（`list-nutrition-foods`）。
- 去配料、只吃馅 = 官方整份 − 去掉的部分，配料营养来自配料库。
- 配料库：33 份配方（其中 32 份经过一轮独立核查，并按核查结论修订，见 [docs/research](docs/research)）、41 个配料参考值（每个都有出处）、带非负约束的贝叶斯最小二乘，组合误差用完整后验协方差计算。拟合结果见 [docs/research/fit_report.md](docs/research/fit_report.md)。
- 去配料、只吃馅的热量误差（一个标准差）中位约 ±13 大卡，九成在 ±30 大卡以内；拆不准的吃法不推荐。
- 不在官方营养表里的新品按配方估算，误差超过 12% 不推荐，推荐时会注明误差。

详细说明见 [营养是怎么算的](skill/maimen-gym/references/nutrition-method.md)。

**开放数据集**：[data/ingredient_library.json](data/ingredient_library.json) 收录 44 种麦当劳中国配料的估计营养（热量、蛋白质、脂肪、碳水、钠、钙）、标准差、依据和用到它的餐品，可以直接拿去用。

## 适合谁

- 在减脂、增肌，又不想因为一顿麦当劳打乱计划的人；
- 想知道「只吃肉饼」「去掉吉士」到底少吃多少的人；
- 想用最少的钱吃够蛋白质的学生和上班族。

## 项目结构

```
skill/maimen-gym/        Skill 本体：SKILL.md、references、scripts/gym.py
src/mcdstrip/            计算代码（纯标准库）
  mcp.py                 麦当劳 MCP 客户端（Streamable HTTP）
  nutrition.py           官方营养表解析、菜单名归一
  library.py / linalg.py 配料库：非负贝叶斯最小二乘、后验协方差、删除诊断
  catalog.py             门店菜单 → 选项（套餐份数、吃法、去配料）
  solver.py              分支定界求解、支配过滤
  stores.py              门店搜索、餐段与预约
  pricing.py             算价参数构造与核价
  render.py              训练计划卡、按餐段的说法
data/reference/          配方、配料参考值、可去配料映射
data/fixtures/           官方营养表与门店菜单快照（离线演示和测试用）
docs/research/           配方研究、对抗核查结论、拟合报告
test/                    单元测试（求解器与穷举对拍、配料库、菜单、门店）
```

## 开发

```bash
python3 -m unittest discover -s test          # 全部测试
python3 scripts/fit_report.py > docs/research/fit_report.md   # 配料库拟合报告
python3 scripts/capture_fixtures.py --store 1450441 --slot 2026-10-16T19:00   # 采集门店快照（需要 Token）
python3 scripts/price_check_record.py         # 核价记录：预测价与 calculate-price 逐个对照（需要 Token）
python3 scripts/check_publish.py              # 推送前自查：没有本机路径和 Token
```

## 声明

本项目是麦当劳程序员节创意开发大赛的参赛作品，由参赛者独立开发，不是麦当劳官方产品。营养数字中除整份数据外均为估算，仅供参考，不构成医疗或营养建议；餐品、价格和供应以麦当劳官方渠道的实时结果为准。见 [CONTEST_DECLARATION.md](CONTEST_DECLARATION.md)。
