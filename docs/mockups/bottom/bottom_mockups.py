"""「装」页底部（开放数据集 + 页脚）三版 mockup：在真实页面上替换这两块的标记和样式，截底部区域。
    uv run --no-project --with playwright --with pillow python docs/mockups/bottom/bottom_mockups.py
需要本地预览在跑（python3 scripts/serve_site.py）。输出本目录 bottom-<方向>.png 与对比板 bottom-board.png"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
URL = "http://localhost:8765/#/%E8%A3%85"
ROWS = [("小牛肉饼", 91, 7, "8.2"), ("吉士片", 45, 2, "3.0"), ("普通汉堡面包", 142, 6, "4.6"),
        ("安格斯牛肉饼", 266, 15, "23.1"), ("鳕鱼排", 114, 6, "10.2"), ("番茄酱", 12, 7, "0.1")]
DL = '<a class="mk-dl" href="#"><svg class="i"><use href="#i-download"/></svg>下载 ingredient_library.json</a>'
GH = '<a class="mk-ghost" href="#">在 GitHub 上看字段说明<svg class="i"><use href="#i-arrow"/></svg></a>'
SPEC = '''<dl class="mk-spec">
  <div><dt>营养</dt><dd>热量、蛋白质、脂肪、碳水、钠、钙</dd></div>
  <div><dt>误差</dt><dd>每一项都给出估计值和后验标准差</dd></div>
  <div><dt>来源</dt><dd>28 款官方整份营养 + 配方联合求解，参考美国麦当劳官网与 USDA</dd></div>
  <div><dt>格式</dt><dd>JSON · 34 KB · MIT 许可</dd></div></dl>'''
TABLE = ('<table class="ing"><thead><tr><th>配料</th><th class="r">大卡</th><th class="r">误差</th><th class="r">蛋白质</th><th class="bar barh">大卡 ± 误差</th></tr></thead><tbody>'
         + "".join(f'<tr><td class="nm">{n}</td><td class="k r">{k}</td><td class="e r">±{e}</td><td class="p r">{p}<span>g</span></td>'
                   f'<td class="bar"><div class="whisk"><span class="rg" style="left:{(k - e) / 3:.2f}%;width:{2 * e / 3:.2f}%"></span><span class="pt" style="left:{k / 3:.2f}%"></span></div></td></tr>' for n, k, e, p in ROWS)
         + '</tbody><tfoot class="scale-row"><tr><td colspan="4"></td><td class="bar"><div class="scale"><span>0</span><span>150</span><span>300 大卡</span></div></td></tr></tfoot></table>')
WHISK = "".join(f'<div class="mk-wk"><span class="nm">{n}</span><div class="tr"><i class="rng" style="left:{(k - e) / 3:.2f}%;width:{2 * e / 3:.2f}%"></i><i class="pt" style="left:{k / 3:.2f}%"></i></div><span class="v">{k}<small>±{e}</small></span></div>' for n, k, e, _ in ROWS)
NAV = '<a href="#/练"><b>练</b>点餐方案</a><a href="#/拆"><b>拆</b>只吃馅</a><a href="#/装"><b>装</b>WorkBuddy</a>'
BRAND = '<a class="brand" href="#"><span class="gy">Gy<span class="m"><svg aria-hidden="true"><use href="#g-m"/></svg></span></span><span class="cn">麦门健身房</span></a>'
DISC = "本项目是麦当劳程序员节创意开发大赛的参赛作品，不是麦当劳官方产品。除整份营养外，数字均为估算，仅供参考，不构成营养建议。"
STAR = '<a class="btn btn-line btn-sm" href="#"><svg class="i"><use href="#i-star"/></svg>在 GitHub 上 Star</a>'

BASE = '''
footer.mk-f .wrap{display:block}   /* 原页脚 .wrap 是两列网格，新结构自己排 */
.mk-open .sec-h{font-size:40px}.mk-kick{margin-bottom:10px}
.mk-dl{display:inline-flex;align-items:center;gap:10px;height:48px;padding:0 22px;border-radius:999px;background:var(--ink);color:var(--paper);font-size:15px;font-weight:600}
.mk-dl .i{width:18px;height:18px}
.mk-ghost{display:inline-flex;align-items:center;gap:6px;font-size:15px;color:var(--ink-2);border-bottom:1px solid var(--rule-2);padding-bottom:2px}
.mk-ghost .i{width:16px;height:16px}
.mk-spec{margin:28px 0 0;border-top:1px solid var(--ink)}
.mk-spec div{display:grid;grid-template-columns:56px 1fr;gap:12px;padding:12px 0;border-bottom:1px solid var(--rule);font-size:15px;line-height:1.6}
.mk-spec dt{color:var(--ink-3)}.mk-spec dd{margin:0;color:var(--ink)}
'''

V = {
"b1-spec": ("1 · 数据说明 + 两行页脚", BASE + '''
.mk-open{display:grid;grid-template-columns:minmax(0,4fr) minmax(0,8fr);gap:72px;align-items:start;margin-top:104px}
.mk-big{display:flex;align-items:flex-end;gap:14px;margin-top:22px}
.mk-big b{font-family:var(--num);font-weight:700;font-size:112px;line-height:.78}
.mk-big span{font-size:17px;line-height:1.5;color:var(--ink-2)}
.mk-acts{display:flex;flex-wrap:wrap;align-items:center;gap:14px 22px;margin-top:28px}
footer.mk-f{border-top:4px solid var(--ink);padding:0}
.mk-f .row1{display:flex;align-items:center;gap:40px;height:96px;border-bottom:1px solid var(--rule)}
.mk-f .fnav{display:flex;gap:30px;margin-left:auto;font-size:14px;color:var(--ink-2);white-space:nowrap}
.mk-f .fnav b{font-family:"MG Heavy",var(--cn);font-weight:900;font-size:17px;color:var(--ink);margin-right:6px}
.mk-f .row2{display:flex;justify-content:space-between;gap:40px;padding:22px 0 40px;font-size:13px;color:var(--ink-3)}
.mk-f .row2 a{color:var(--ink-2);border-bottom:1px solid var(--rule-2)}
''', f'''<div class="mk-open"><div><div class="kicker mk-kick">OPEN DATA</div><h2 class="sec-h">开放数据集</h2>
<div class="mk-big"><b>44</b><span>种麦当劳中国配料的<br>估计营养</span></div>{SPEC}<div class="mk-acts">{DL}{GH}</div></div><div>{TABLE}</div></div>''',
 f'''<div class="wrap"><div class="row1">{BRAND}<nav class="fnav">{NAV}</nav>{STAR}</div><div class="row2"><p style="margin:0;max-width:760px">{DISC}</p><span><a href="#">MIT License</a> · <a href="#">GitHub</a></span></div></div>'''),

"b2-slogan": ("2 · 标语收尾", BASE + '''
.mk-open{margin-top:104px}
.mk-head{display:flex;align-items:flex-end;justify-content:space-between;gap:24px;padding-bottom:18px;border-bottom:2px solid var(--ink)}
.mk-meta{margin-top:10px;font-size:15px;color:var(--ink-2)}
.mk-meta b{font-family:var(--num);font-size:1.3em;color:var(--ink)}
.mk-open .ing{margin-top:8px}
footer.mk-f{border-top:0;padding:96px 0 40px;margin-top:40px;background:linear-gradient(var(--paper),var(--paper))}
.mk-f .slo{font-family:var(--cond);font-weight:800;font-stretch:condensed;font-size:clamp(64px,9vw,136px);line-height:.92;letter-spacing:-.012em}
.mk-f .slo{white-space:nowrap}.mk-f .slo .ru{font-family:var(--cn);font-weight:700;font-size:.55em;vertical-align:.12em}
.mk-f .slo img{display:inline-block;width:auto;height:.74em;vertical-align:-.04em;margin-left:.12em}
.mk-f .cols{display:flex;align-items:flex-end;justify-content:space-between;gap:40px;margin-top:48px;padding-top:20px;border-top:1px solid var(--rule)}
.mk-f .fnav{display:flex;gap:26px;font-size:14px;color:var(--ink-2);white-space:nowrap}
.mk-f .fnav b{font-family:"MG Heavy",var(--cn);font-weight:900;font-size:17px;color:var(--ink);margin-right:6px}
.mk-f p{margin:0;max-width:640px;font-size:13px;line-height:1.8;color:var(--ink-3)}
''', f'''<div class="mk-open"><div class="mk-head"><div><div class="kicker mk-kick">OPEN DATA</div><h2 class="sec-h">开放数据集</h2>
<div class="mk-meta"><b>44</b> 种配料 · 6 项营养 · 每项带误差 · JSON 34 KB · MIT 许可</div></div>{DL}</div>{TABLE}</div>''',
 f'''<div class="wrap"><div class="slo">Go to Gym <span class="ru">不如</span><br>Go to<img src="assets/img/gold-m.webp" alt="ᗰ"></div>
<div class="cols"><div>{BRAND}<p style="margin-top:14px">{DISC}</p></div><nav class="fnav">{NAV}<a href="#">GitHub</a></nav></div></div>'''),

"b3-chart": ("3 · 图表化 + 三栏页脚", BASE + '''
.mk-open{display:grid;grid-template-columns:minmax(0,5fr) minmax(0,7fr);gap:80px;align-items:start;margin-top:104px}
.mk-open p.lead{margin:18px 0 0;font-size:17px;line-height:1.8;color:var(--ink-2)}
.mk-open p.lead b{font-family:var(--num);font-size:1.35em;color:var(--ink)}
.mk-acts{display:flex;flex-wrap:wrap;align-items:center;gap:14px 22px;margin-top:28px}
.mk-cap{display:flex;justify-content:space-between;padding-bottom:10px;border-bottom:1px solid var(--ink);font-size:13px;color:var(--ink-3)}
.mk-wk{display:grid;grid-template-columns:120px minmax(0,1fr) 84px;align-items:center;gap:16px;padding:14px 0;border-bottom:1px solid var(--rule)}
.mk-wk .nm{font-size:15px;font-weight:600}
.mk-wk .v{text-align:right;font-family:var(--num);font-weight:700;font-size:24px}.mk-wk .v small{margin-left:3px;font-size:14px;color:var(--ink-3)}
.mk-wk .tr{position:relative;height:20px;background:repeating-linear-gradient(90deg,var(--rule) 0 1px,transparent 1px 33.33%)}
.mk-wk .rng{position:absolute;top:50%;height:2px;background:var(--ink);transform:translateY(-50%)}
.mk-wk .rng::before,.mk-wk .rng::after{content:"";position:absolute;top:-5px;width:2px;height:12px;background:var(--ink)}.mk-wk .rng::before{left:0}.mk-wk .rng::after{right:0}
.mk-wk .pt{position:absolute;top:50%;width:10px;height:10px;border-radius:50%;background:var(--red);transform:translate(-50%,-50%)}
.mk-axis{display:grid;grid-template-columns:120px minmax(0,1fr) 84px;gap:16px;padding-top:8px;font-family:var(--num);font-weight:700;font-size:13px;color:var(--ink-3)}
.mk-axis div{display:flex;justify-content:space-between}
footer.mk-f{border-top:4px solid var(--ink);padding:48px 0 36px}
.mk-f .grid{display:grid;grid-template-columns:minmax(0,5fr) minmax(0,3fr) minmax(0,3fr);gap:48px}
.mk-f .tag{margin:14px 0 0;font-size:15px;color:var(--ink-2)}
.mk-f h4{margin:0 0 12px;font-size:13px;font-weight:600;letter-spacing:.08em;color:var(--ink-3)}
.mk-f ul{list-style:none;margin:0;padding:0;font-size:15px;line-height:2.1}
.mk-f ul b{font-family:"MG Heavy",var(--cn);font-weight:900;margin-right:8px}
.mk-f .bar{display:flex;justify-content:space-between;gap:40px;margin-top:40px;padding-top:18px;border-top:1px solid var(--rule);font-size:13px;color:var(--ink-3)}
''', f'''<div class="mk-open"><div><div class="kicker mk-kick">OPEN DATA</div><h2 class="sec-h">开放数据集</h2>
<p class="lead"><b>44</b> 种麦当劳中国配料的估计营养：热量、蛋白质、脂肪、碳水、钠、钙，每一项都带误差。由 28 款官方整份营养和配方联合求解，参考美国麦当劳官网与 USDA。</p>
<div class="mk-acts">{DL}{GH}</div></div>
<div><div class="mk-cap"><span>节选 6 种 · 估计值与误差</span><span>大卡</span></div>{WHISK}<div class="mk-axis"><span></span><div><span>0</span><span>100</span><span>200</span><span>300</span></div><span></span></div></div></div>''',
 f'''<div class="wrap"><div class="grid"><div>{BRAND}<p class="tag">健身人群的麦当劳点餐 Skill · Go to Gym 不如 Go to ᗰ</p></div>
<div><h4>页面</h4><ul><li><a href="#/练"><b>练</b>点餐方案</a></li><li><a href="#/拆"><b>拆</b>只吃馅</a></li><li><a href="#/装"><b>装</b>WorkBuddy</a></li></ul></div>
<div><h4>项目</h4><ul><li><a href="#">GitHub 仓库</a></li><li><a href="#">开放数据集</a></li><li><a href="#">MIT License</a></li></ul></div></div>
<div class="bar"><span>{DISC}</span><span>© 2026 Gyᗰ 麦门健身房</span></div></div>'''),
}


def main():
    shots = []
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome")
        for key, (title, css, open_html, foot_html) in V.items():
            pg = b.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
            pg.goto(URL, wait_until="networkidle"); pg.wait_for_timeout(1200)
            pg.add_style_tag(content=css + "*,*::before,*::after{animation:none!important;transition:none!important}")
            pg.evaluate("""([openHtml, footHtml]) => {
              const body = document.querySelector('#v-install .page-body');
              const sub = body.querySelector('.sub-head'), data = body.querySelector('.data');
              const box = document.createElement('div'); box.innerHTML = openHtml;
              sub.replaceWith(box.firstElementChild); data.remove();
              const f = document.querySelector('footer'); f.className = 'mk-f'; f.innerHTML = footHtml; }""", [open_html, foot_html])
            pg.wait_for_timeout(400)
            y0 = pg.evaluate("document.querySelector('.mk-open').getBoundingClientRect().top + scrollY - 60")
            h = pg.evaluate("document.documentElement.scrollHeight")
            out = HERE / f"bottom-{key}.png"
            pg.screenshot(path=str(out), full_page=True, clip={"x": 0, "y": y0, "width": 1440, "height": h - y0})
            print(key, h - y0, pg.evaluate("document.documentElement.scrollWidth - innerWidth"))
            shots.append((title, out)); pg.close()
        b.close()
    F = "/System/Library/Fonts/Hiragino Sans GB.ttc"
    ims = [(t, Image.open(f).convert("RGB")) for t, f in shots]
    W = 900; ims = [(t, im.resize((W, round(im.height * W / im.width)))) for t, im in ims]
    H = max(im.height for _, im in ims) + 90
    board = Image.new("RGB", (len(ims) * (W + 40) + 40, H), "#E6E0D3"); d = ImageDraw.Draw(board)
    for i, (t, im) in enumerate(ims):
        x = 40 + i * (W + 40); d.text((x, 24), t, fill="#17150F", font=ImageFont.truetype(F, 34)); board.paste(im, (x, 80))
    board.save(HERE / "bottom-board.png"); print("bottom-board.png", board.size)


if __name__ == "__main__":
    main()
