# maimen-gym（Gyᗰ 麦门健身房）项目记忆

项目名「Gyᗰ 麦门健身房」（2026-10-15 用户定名；早期工作名「拆着吃」，目录与仓库名 maimen-gym，代码包名仍为 mcdstrip）。
Skill 名「麦麦健身餐规划师」（2026-10-16 用户定：要一听就懂；「Gyᗰ 麦门健身房」保留为项目品牌，片尾口号不改；2026-10-18 用户改：网站页眉、页脚和页面标题也改成「麦麦健身餐规划师」，README 引用行只留口号，介绍时写「Gyᗰ 麦门健身房 · 麦麦健身餐规划师」；SKILL.md 的 `name` 仍是 maimen-gym，description 以新名字开头，WorkBuddy 技能卡片显示的就是这一行）。健身人群的麦当劳点餐 Skill，口号「Go to Gym 不如 Go to ᗰ」，推荐结果写成训练计划（练腿 / 练胸 / 练背 / 练手臂，麦乐鸡算练胸）。参加麦当劳程序员创意开发大赛（M-CODE，10/25 23:59 截止，按 GitHub Star 定榜）。

## 约定
- 写实双吉素材以 `videos/gym-promo/assets/cutouts/burger-v3` 为准（参数在 bake.json，`scripts/bake_burger.py` 可复现）；用户给的麦当劳官方实拍 / 配料图只在本机当参考板，不入库。产品图在 `cutouts/sides/`，一律不画第三方品牌标志
- 纯 Python 标准库，Python ≥ 3.9（macOS 自带 3.9.6，2026-10-16 实测全部测试通过）；测试：`python3 -m unittest discover -s test`
- 用户在 Windows 和 macOS 上装：文档里的命令两套都给（macOS `python3`、Windows `py`）；CI 跑 ubuntu / windows / macos
- Token 只从 `MCD_MCP_TOKEN` 读取，不落盘、不进日志、不进仓库
- 设置 Token 的提示统一用 `mcp.token_setup_hint()`（按系统给 setx 或写 shell 配置），安装脚本和缺 Token 报错共用
- MCP 连接器：WorkBuddy 用官方 JSON（`streamablehttp`），不展开 `${MCD_MCP_TOKEN}`，要填 Token 原文；Claude Code 的 `type` 必须是 `http`，或用 `claude mcp add --transport http`
- 推送前跑 `python3 scripts/check_publish.py`：要发布的文件里不能有本机绝对路径和 Token（`test_publish` 守着已跟踪的文件）
- 公开分支是 `main`（2026-10-18 起，从单次提交开始）；`master` 是本地完整历史，旧提交里有本机路径，不推送。`assets/3d`（除 BRIEF.md）和 `videos/` 不入库，`scripts/build_site_*.py` 只能在本机跑；测试不能依赖这两个目录和 numpy，CI 是纯标准库
- mcd.cn 走代理会握手超时，客户端默认直连
- 离线快照在 `data/fixtures/`，用 `scripts/capture_fixtures.py` 重新采集
- 配方：正式版 `data/reference/recipes.json`，没有时回落到 `recipes_draft.json`
- 项目主页本地预览用 `python3 scripts/serve_site.py`（Cache-Control: no-cache + 支持 Range）；别用 `python3 -m http.server`：它不发缓存头，浏览器会按启发式缓存旧 JS（改完页面看到「新 HTML + 旧脚本」、元素缺失），也不支持 Range（视频跳不到没下载的位置）
- 发布到 GitHub Pages 时 CI 先跑 `scripts/stamp_site_assets.py` 给资源链接加内容版本号；仓库里的 index.html 不带版本号
- 主站是 https://mcd.lzqqq.org（仓库主页字段指向它），GitHub Pages 留一份。发布：提交 site/ 后运行 `python3 scripts/deploy_site.py myserver:/var/www/mcd.lzqqq.org --url https://mcd.lzqqq.org --ssh "ssh -B en0"`（本机 Clash TUN 不转发 SSH，要绑 en0）。服务器 nginx 配置在 `deploy/nginx/`；前面是 Cloudflare（Full strict），源站证书单独签给 mcd（webroot `/var/www/dsh-acme`），Cloudflare 会往页面插统计脚本，还会把不带版本号的静态文件浏览器缓存改成 4 小时
- 主页风格：「练」「拆」「装」三页是「教练批注」（.coach：印章、红笔、手写字矢量），首页是「焦点构图」；mockup 与生成脚本在 `docs/mockups/`（split2、nav、install）
- 主页数据与素材脚本：`build_site_data.py`（练页方案）、`build_site_ingredients.py`（装页散点图）、`build_site_curtain.py`（页脚举牌小人，牌子框位置要同步进 index.html，测试守着）、`build_site_fonts.py`（标题粗体子集，加新标题字要重跑）
- README 配图在 `docs/readme/`，由 `python3 scripts/build_readme_images.py` 生成（GYM 梗图横幅 + 教程帧三联图 + 实操截图，版式是用户选的 mockup C，横幅 10-18 用户改成梗图）；README 不再提「训练部位」（用户 10-18 定），主页首屏或安装教程改了要重跑，教程重剪后要重找 FRAMES 里的时间点和三联图的裁切行
- 主页视频：`python3 scripts/build_site_videos.py` 从 videos/ 的成片生成 site/assets/video/ 和封面；宣传片用 gym-promo-v5（2026-10-17：用户要求加强麦当劳品牌关联，纸袋人戴麦当劳纸袋、结尾用 GYM 梗图；v3-arches 那版仍不用）

## 已确认的接口事实（2026-10-15 实测）
- 单品可去配料在餐品详情顶层 `modification`；套餐在每组选项的 `modification`
- 面包不在任何可去配料里；吉士是一个开关（双吉两片一起去）
- 去配料不改价；套餐内带特制参数核价通过
- 特制参数要整组传：保留的 selectedKey + 数量 1，去掉的 unselectedKey + 数量 0
- 餐段切换空档或门店临时停业时 query-meals 返回 600057，预约时间也一样
- 「随单购麦金卡/早餐卡优惠」的 currentPrice 只有连同会员卡一起买才有：不带 withOrder 算价按 originalPrice（人气超值四件套 ¥57；吉士蛋麦满分组合 ¥12），带上会多一张卡（麦金卡体验卡 ¥9.9、6折满分早餐卡 ¥11.9）。所以默认按原价（`catalog.price_cents`）
- 套餐组有份数：round.quantity（堡堡随心拼 主食 2、小食 3、饮料 2），choice.maxQuantity 限制单项份数（BFF四宫格每样 1 份）；核价时同组相同配置合并为一条并带数量
- 菜单名常和营养表对不上：单品先试详情名；`normalize` 按规则改写（麦咖啡™ 前缀、5块麦乐鸡、麦辣鸡翅2块、可口可乐（小杯））；块数不同按块换算（麦辣鸡翅4块 = 2 × 麦辣鸡翅-2块）
- query-nearby-stores 地点搜不到返回 600014；可预约时段是文字（「宵夜(00:00至04:45,22:14至23:59)，早餐(…)」），餐段之间有空档

## 数据结论
- 牛肉饼 ≈ 89 大卡 / 8 g 蛋白 / 0 碳水；芝士片 ≈ 46 大卡、钙 ≈ 83 mg（吉士汉堡包 − 汉堡包）；与美国官网配料数据吻合
- 先验里没写的营养素一律按「未知」处理（弱先验），曾误设为 0 ± 20 导致芝士钙算成 72（2026-10-15 审查发现）
- 双吉的番茄酱约 10 大卡、芥末酱 0：「去酱」对双吉几乎没用
- 板烧鸡腿堡不能套用麦满分的鸡腿排（会算出面包含 15 g 蛋白）；早餐另建 chicken.grill_thigh_breakfast（约 100 大卡，是汉堡那块的一半）
- **能去掉或能留到下一顿的配料（面包、酱、菜、黄油）必须有参考值**：没有参考值又总是一起出现的两个配料会被平分（曾把板烧鸡腿和玉米长面包各算成 141 大卡）。肉类可以没有参考值，由官方总数倒推。`test_removable_parts_have_references` 守着
- 拆分可信度：热量标准差 ≤ max(15, 0.4 × 热量) 才拿来给吃法建议（`library.is_reliable`）；只靠参考值的酱（芥末沙拉酱、红油、辣椒黄油酱）达不到，所以不出「去这个酱」
- 不在营养表里的餐品（高达吉士双牛堡、龙焰系）用配料库预测：误差 ≤ 12% 才推荐，且方案下面注明「估算」
- 烟肉蛋麦满分、培根双层安格斯厚牛堡的官方数值自相矛盾，列在 recipes.json 的 `_fit_exclude`，只预测不拟合
- 安格斯的黄油在菜单上可单独去掉，不能并进面包
- 早餐板烧鸡腿的钠被全部分给了烤味酱（鸡腿钠 ≈ 0）：早餐里两者总是 1:1 出现，钠怎么分只能靠参考值，属于已知局限

## 性能
- 一家店不设热量上限时套餐可展开到 18 万个选项：`Builder.options` 必须给 `kcal_max`（CLI 用目标的 1.25 倍）
- 求解：先按上限筛，再做支配过滤（天际线；考虑部位蛋白、占比、份数上限），按方案实质去重取前 k；典型查询 2–7 秒
- 配料库按输入内容哈希缓存在 `~/.cache/mcdstrip/library-*.pkl`；门店详情按门店 + 取餐方式缓存 6 小时，菜单每次实时拉

