"""「装」页加视频的三版布局 mockup（HTML，用真实样式、真实视频封面）。
    python3 docs/mockups/install/build.py   → 本目录 v1-cinema.html、v2-sync.html、v3-pair.html
顶栏、图标、开放数据集直接从 site/index.html 摘出来；<base> 指向 site/，资源路径和线上一致。"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
SITE = HERE.parents[2] / "site"
src = (SITE / "index.html").read_text(encoding="utf-8")
DEFS = re.search(r'<svg width="0" height="0".*?</svg>', src, re.S).group(0)
HEADER = re.search(r'<header class="top">.*?</header>', src, re.S).group(0).replace('data-go="装">', 'data-go="装" aria-current="page">', 1)
OPEN = re.search(r'    <div class="sub-head"><div class="kicker">OPEN DATA</div>.*?\n    </div>\n  </div>\n</section>', src, re.S).group(0)
OPEN = OPEN.rsplit("\n  </div>\n</section>", 1)[0]
U = ('<svg class="pen pen-u" viewBox="0 0 302 24" preserveAspectRatio="none" aria-hidden="true"><path pathLength="1" d="M4.0 8.0 C5.0 9.5 6.7 15.7 10.0 17.0 '
     'C13.3 18.3 14.1 17.0 24.0 16.0 C54.4 12.3 115.3 9.0 161.0 9.3 C206.7 8.8 252.3 11.6 298.0 13.7"/></svg>')
PLAY = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5.5v13l11-6.5z"/></svg>'

HEAD = f'''<div class="page-head wrap">
    <a class="back" href="#"><svg class="i"><use href="#i-arrow"/></svg>回到首页</a>
    <img class="page-avatar" src="assets/img/buddy-nugget.webp" alt="" width="420" height="584">
    <div class="ph-text">
      <div class="kicker">INSTALL</div>
      <h1 class="page-title"><span class="ib">装 ·</span> <span class="ib"><span class="pen-mark">装到 WorkBuddy{U}</span></span></h1>
      <p>三组动作：装 Skill、接麦当劳 MCP、开口说一句。跟着 78 秒的视频做一遍就好。</p>
    </div>
  </div>'''

def player(cls=""):
    return f'''<figure class="player {cls}"><video preload="none" playsinline poster="assets/img/install-tutorial-poster.webp" src="assets/video/install-tutorial.mp4"></video>
      <button class="big-play" type="button" aria-label="播放安装教程">{PLAY}</button><figcaption><b>安装教程</b><span>1:18 · 有配音</span></figcaption></figure>'''

def promo(cls=""):
    return f'''<figure class="promo {cls}"><video preload="none" playsinline poster="assets/img/promo-poster.webp" src="assets/video/promo.mp4"></video>
      <button class="big-play sm" type="button" aria-label="播放宣传片">{PLAY}</button></figure>'''

STEPS = [
    ("01", "装 Skill", "0:06", '''<div class="code"><span class="ln"><span class="pr">$</span>git clone https://github.com/linzhiqin2003/maimen-gym.git</span><span class="ln"><span class="pr">$</span>cd maimen-gym &amp;&amp; python3 install.py --target workbuddy</span><button class="copy" type="button" aria-label="复制命令"><svg class="i"><use href="#i-copy"/></svg></button></div>
        <p class="note">装好后在 WorkBuddy 的技能页确认 maimen-gym 已开启</p>'''),
    ("02", "接麦当劳 MCP", "0:22", '''<p>在 <code>open.mcd.cn/mcp</code> 申请麦当劳 MCP Token，然后在 WorkBuddy 的连接器里添加麦当劳 MCP，粘贴配置、点信任。</p>'''),
    ("03", "开口说一句", "0:47", '''<p>新建任务，直接说：</p><p class="say">「今晚练腿，500 大卡以内，蛋白质 30 克，人民广场附近」</p>'''),
]

def step(n, t, at, body, cls=""):
    return f'''<li class="st {cls}"><div class="st-h"><span class="stamp">{n}</span><h3>{t}</h3><button class="jump" type="button">{PLAY}{at}</button></div>{body}</li>'''

BASE_CSS = '''
body{background:var(--paper)}
.player,.promo{position:relative;margin:0}
.player video,.promo video{display:block;width:100%;height:auto;background:#000}
.player video{aspect-ratio:16/9;border-radius:14px;box-shadow:0 1px 0 rgba(23,21,15,.06),0 18px 40px -18px rgba(23,21,15,.35)}
.big-play{position:absolute;left:50%;top:50%;display:flex;align-items:center;justify-content:center;width:84px;height:84px;margin:-62px 0 0 -42px;border:0;border-radius:50%;background:var(--red);color:var(--paper);cursor:pointer;box-shadow:0 10px 30px -8px rgba(210,58,30,.55)}
.big-play svg{width:34px;height:34px;margin-left:4px;fill:currentColor}
.big-play.sm{width:60px;height:60px;margin:-30px 0 0 -30px}.big-play.sm svg{width:24px;height:24px}
.player figcaption{display:flex;align-items:baseline;gap:12px;margin-top:14px;font-size:14px;color:var(--ink-3)}
.player figcaption b{font-size:16px;color:var(--ink)}
.steps3{list-style:none;margin:0;padding:0}
.st-h{display:flex;align-items:center;gap:14px}
.st-h h3{margin:0;font-family:"MG Heavy",var(--cn);font-weight:900;font-size:26px;line-height:1.2}
.st-h .stamp{font-size:18px}
.jump{display:inline-flex;align-items:center;gap:4px;margin-left:auto;height:30px;padding:0 12px 0 9px;border:1.5px solid var(--rule-2);border-radius:999px;background:none;font-family:var(--num);font-weight:700;font-size:15px;color:var(--ink-2);cursor:pointer}
.jump svg{width:13px;height:13px;fill:currentColor}
.st p{margin:14px 0 0;font-size:15px;line-height:1.8;color:var(--ink-2)}
.st p code{font-family:var(--mono);font-size:14px;color:var(--ink)}
.st .say{margin-top:6px;font-size:21px;line-height:1.5;font-weight:600;color:var(--ink)}
.st .code{margin-top:16px;font-size:13px;padding:16px 56px 16px 18px}
.st .note{font-size:14px;color:var(--ink-3)}
.sec{display:flex;align-items:center;gap:16px;margin:0;font-family:"MG Heavy",var(--cn);font-weight:900;font-size:40px}
'''

V1 = ("v1-cinema", "影院主屏", '''
.v1 .player{margin-top:8px}
.rail{position:relative;display:grid;grid-template-columns:6fr 16.5fr 24.5fr 31fr;margin-top:22px;border-top:3px solid var(--ink)}
.rail span{position:relative;padding-top:10px;font-family:var(--num);font-weight:700;font-size:14px;color:var(--ink-3)}
.rail span::before{content:"";position:absolute;left:0;top:-9px;width:2px;height:15px;background:var(--ink)}
.rail span:first-child::before{display:none}
.v1 .steps3{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:40px;margin-top:36px}
.v1 .st{padding-top:22px;border-top:1px solid var(--rule)}
.v1 .st.on{border-top:2px solid var(--red)}
.pair2{display:grid;grid-template-columns:300px minmax(0,1fr);gap:72px;align-items:center;margin-top:96px}
.phone{padding:10px;border-radius:40px;background:var(--ink);box-shadow:0 22px 50px -20px rgba(23,21,15,.5)}
.phone video{border-radius:30px;aspect-ratio:9/16}
.pair2 h2{margin:10px 0 0;font-size:40px;line-height:1.2;font-weight:600}
.pair2 p{margin:14px 0 0;max-width:520px;font-size:16px;line-height:1.8;color:var(--ink-2)}
''', lambda: f'''
    {player()}
    <div class="rail"><span></span><span>01 装 Skill · 0:06</span><span>02 接麦当劳 MCP · 0:22</span><span>03 开口说一句 · 0:47</span></div>
    <ol class="steps3">{"".join(step(*s, cls="on" if i == 0 else "") for i, s in enumerate(STEPS))}</ol>
    <div class="pair2"><div class="phone">{promo()}</div><div><div class="kicker">PROMO</div><h2>27 秒，看懂麦门健身房</h2><p>Go to Gym 不如 Go to ᗰ：告诉它热量、蛋白质和今天练哪里，最便宜的点法和「只吃馅」的吃法帮你算好。</p></div></div>
''')

V2 = ("v2-sync", "步骤联动分栏", '''
.v2 .grid{display:grid;grid-template-columns:minmax(0,5fr) minmax(0,7fr);gap:56px;align-items:start}
.v2 .stick{position:sticky;top:24px}
.v2 .st{position:relative;padding:26px 0 28px;border-top:1px solid var(--rule)}
.v2 .st:first-child{border-top:2px solid var(--ink)}
.v2 .st.on .st-h h3{color:var(--ink)}
.v2 .st.on::before{content:"";position:absolute;left:-26px;top:22px;bottom:24px;width:12px;border:3px solid var(--red);border-right:0;border-radius:10px 0 0 10px;opacity:.9}
.v2 .st.on .jump{border-color:var(--red);color:var(--red)}
.v2 .st:not(.on) .st-h h3{color:var(--ink-3)}
.v2 .prog{display:flex;gap:6px;margin-top:16px}
.v2 .prog i{flex:1;height:5px;border-radius:3px;background:var(--rule)}
.v2 .prog i.done{background:var(--ink)}.v2 .prog i.now{background:linear-gradient(90deg,var(--red) 55%,var(--rule) 55%)}
.promo-row{display:grid;grid-template-columns:240px minmax(0,1fr);gap:64px;align-items:center;margin-top:96px;padding-top:40px;border-top:2px solid var(--ink)}
.promo-row .promo video{border-radius:18px;aspect-ratio:9/16}
.promo-row h2{margin:10px 0 0;font-size:36px;line-height:1.2;font-weight:600}
.promo-row p{margin:12px 0 0;max-width:560px;font-size:16px;line-height:1.8;color:var(--ink-2)}
''', lambda: f'''
    <div class="grid">
      <ol class="steps3">{"".join(step(*s, cls="on" if i == 0 else "") for i, s in enumerate(STEPS))}</ol>
      <div class="stick">{player()}<div class="prog"><i class="now"></i><i></i><i></i></div></div>
    </div>
    <div class="promo-row">{promo()}<div><div class="kicker">PROMO</div><h2>27 秒，看懂麦门健身房</h2><p>Go to Gym 不如 Go to ᗰ：告诉它热量、蛋白质和今天练哪里，最便宜的点法和「只吃馅」的吃法帮你算好。</p></div></div>
''')

V3 = ("v3-pair", "双屏并排", '''
.v3 .screens{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:32px;align-items:end}
.v3 .promo video{border-radius:14px;aspect-ratio:9/16;box-shadow:0 18px 40px -18px rgba(23,21,15,.35)}
.v3 .promo figcaption,.v3 .cap{display:flex;align-items:baseline;gap:12px;margin-top:14px;font-size:14px;color:var(--ink-3)}
.v3 .cap b{font-size:16px;color:var(--ink)}
.v3 .checklist{margin-top:72px}
.v3 .steps3{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:0;margin-top:24px;border-top:2px solid var(--ink)}
.v3 .st{padding:26px 32px 30px;border-left:1px solid var(--rule)}
.v3 .st:first-child{padding-left:0;border-left:0}.v3 .st:last-child{padding-right:0}
.v3 .tick{display:inline-block;width:26px;height:26px;margin-left:auto;border:2px solid var(--rule-2);border-radius:6px}
.v3 .st .jump{margin-left:0}
.v3 .st-h{flex-wrap:wrap}
''', lambda: f'''
    <div class="screens">
      <div>{player().replace('<figcaption><b>安装教程</b><span>1:18 · 有配音</span></figcaption>', '')}<div class="cap"><b>安装教程</b><span>1:18 · 跟着做一遍</span></div></div>
      <div>{promo()}<div class="cap"><b>宣传片</b><span>0:28</span></div></div>
    </div>
    <div class="checklist"><h2 class="sec">三组动作</h2>
      <ol class="steps3">{"".join(step(*s) for s in STEPS)}</ol></div>
''')

TPL = '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<base href="../../../site/"><title>装 · {title}</title><link rel="stylesheet" href="assets/css/site.css"><style>{css}</style></head>
<body>{defs}
{header}
<section class="view page coach {key}" id="v-install">
  {head}
  <div class="wrap page-body">{body}
    <div style="height:24px"></div>
{open}
  </div>
</section>
</body></html>'''

for key, title, css, body in (V1, V2, V3):
    html = TPL.format(title=title, css=BASE_CSS + css, defs=DEFS, header=HEADER, key=key.split("-")[0], head=HEAD, body=body(), open=OPEN)
    (HERE / f"{key}.html").write_text(html, encoding="utf-8")
    print(key)
