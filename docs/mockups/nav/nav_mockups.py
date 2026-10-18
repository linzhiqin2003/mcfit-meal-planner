"""顶栏导航四版 mockup：在真实页面上替换 .nav 的内容和样式，截「拆」页（看选中态）和首页（无选中）的顶栏。
    uv run --no-project --with playwright --with pillow python docs/mockups/nav/nav_mockups.py
需要本地预览在跑（python3 scripts/serve_site.py）。输出本目录 nav-<方向>.png 与对比板 nav-board.png"""
from pathlib import Path
from playwright.sync_api import sync_playwright
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
URL = "http://localhost:8765/"
ITEMS = [("练", "生成训练计划", "buddy-drumstick"), ("拆", "只吃馅怎么算", "buddy-burger"), ("装", "装到 WorkBuddy", "buddy-nugget")]
PEN = ('<svg class="mk-pen" viewBox="0 0 302 24" preserveAspectRatio="none"><path pathLength="1" d="M4.0 8.0 C5.0 9.5 6.7 15.7 10.0 17.0 '
       'C13.3 18.3 14.1 17.0 24.0 16.0 C54.4 12.3 115.3 9.0 161.0 9.3 C206.7 8.8 252.3 11.6 298.0 13.7"/></svg>')

def items(fn):
    return "".join(fn(i, c, d, img) for i, (c, d, img) in enumerate(ITEMS))

VARIANTS = {
  "a-desc": ("A · 字加说明",
    items(lambda i, c, d, img: f'<a href="#/{c}" data-go="{c}" class="mk"><b>{c}</b><span>{d}</span>{PEN}</a>'),
    """.nav{gap:34px;align-items:center}.nav a.mk{position:relative;display:flex;align-items:baseline;gap:8px;padding:6px 0;border:0;color:var(--ink-2)}
    .nav a.mk b{font-family:"MG Heavy",var(--cn);font-weight:900;font-size:19px;color:var(--ink)}.nav a.mk span{font-size:14px}
    .mk-pen{position:absolute;left:-4%;bottom:-6px;width:108%;height:9px;overflow:visible;fill:none;stroke:var(--red);stroke-width:3;stroke-linecap:round;display:none}
    .nav a.mk.on span{color:var(--ink)}.nav a.mk.on .mk-pen{display:block}.nav a.mk:hover span{color:var(--ink)}"""),
  "b-stamp": ("B · 印章编号",
    items(lambda i, c, d, img: f'<a href="#/{c}" data-go="{c}" class="mk"><i>0{i+1}</i><b>{c}</b><span>{d}</span></a>'),
    """.nav{gap:30px;align-items:center}.nav a.mk{display:flex;align-items:center;gap:8px;padding:6px 0;border:0;color:var(--ink-2)}
    .nav a.mk i{font-style:normal;display:inline-flex;align-items:center;justify-content:center;width:30px;height:26px;border:2px solid var(--red);border-radius:4px;
      color:var(--red);font-family:var(--num);font-weight:700;font-size:14px;transform:rotate(-5deg)}
    .nav a.mk b{font-family:"MG Heavy",var(--cn);font-weight:900;font-size:18px;color:var(--ink)}.nav a.mk span{font-size:14px}
    .nav a.mk.on i{background:var(--red);color:var(--paper)}.nav a.mk.on span{color:var(--ink)}"""),
  "c-segment": ("C · 分段胶囊",
    items(lambda i, c, d, img: f'<a href="#/{c}" data-go="{c}" class="mk"><b>{c}</b><span>{d}</span></a>'),
    """.nav{gap:0;align-items:center;height:42px;padding:3px;border:1.5px solid var(--ink);border-radius:999px}
    .nav a.mk{display:flex;align-items:center;gap:7px;height:100%;padding:0 16px;border:0;border-radius:999px;color:var(--ink-2);transition:background-color .2s,color .2s}
    .nav a.mk b{font-family:"MG Heavy",var(--cn);font-weight:900;font-size:16px;color:var(--ink)}.nav a.mk span{font-size:14px}
    .nav a.mk{position:relative}.nav a.mk+a.mk::before{content:"";position:absolute;left:0;top:50%;width:1px;height:16px;margin-top:-8px;background:var(--rule-2)}
    .nav a.mk.on{background:var(--ink);color:var(--paper)}.nav a.mk.on b{color:var(--paper)}
    .nav a.mk.on::before,.nav a.mk.on+a.mk::before{display:none}.nav a.mk:hover:not(.on){background:rgba(23,21,15,.06)}"""),
  "d-buddy": ("D · 小人头像",
    items(lambda i, c, d, img: f'<a href="#/{c}" data-go="{c}" class="mk"><em><img src="assets/img/{img}.webp" alt=""></em><b>{c}</b><span>{d}</span></a>'),
    """.nav{gap:26px;align-items:center}.nav a.mk{display:flex;align-items:center;gap:8px;padding:4px 0;border:0;color:var(--ink-2)}
    .nav a.mk em{position:relative;display:block;width:34px;height:34px;border-radius:50%;overflow:hidden;background:var(--code);box-shadow:inset 0 0 0 1.5px var(--rule-2)}
    .nav a.mk em img{position:absolute;left:50%;top:4%;width:118%;transform:translateX(-50%)}
    .nav a.mk b{font-family:"MG Heavy",var(--cn);font-weight:900;font-size:18px;color:var(--ink)}.nav a.mk span{font-size:14px}
    .nav a.mk.on em{box-shadow:0 0 0 2px var(--paper),0 0 0 4px var(--red)}.nav a.mk.on span{color:var(--ink)}"""),
}

def main():
    shots = {}
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome")
        for key, (title, html, css) in [("now", ("现在", None, ""))] + list(VARIANTS.items()):
            pair = []
            for view in ("#/%E6%8B%86", ""):
                pg = b.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=2)
                pg.goto(URL + view, wait_until="networkidle"); pg.wait_for_timeout(1200)
                if html:
                    pg.add_style_tag(content=css)
                    pg.evaluate("""([html, view]) => { const n = document.querySelector('.nav'); n.innerHTML = html;
                        const cur = decodeURIComponent(view.replace('#/', '')); n.querySelectorAll('a').forEach(a => a.classList.toggle('on', a.dataset.go === cur)); }""", [html, view])
                    pg.wait_for_timeout(300)
                out = HERE / f"nav-{key}-{'split' if view else 'home'}.png"
                pg.screenshot(path=str(out), clip={"x": 0, "y": 0, "width": 1440, "height": 74})
                pair.append(out); pg.close()
            shots[key] = (title if key != "now" else "现在", pair)
        b.close()
    font = ImageFont.truetype("/System/Library/Fonts/Hiragino Sans GB.ttc", 30)
    rows = list(shots.items())
    W, rowH = 2880, 2 * 148 + 90
    board = Image.new("RGB", (W, rowH * len(rows) + 30), "#E6E0D3")
    d = ImageDraw.Draw(board)
    for i, (key, (title, pair)) in enumerate(rows):
        y = 30 + i * rowH
        d.text((40, y), title + ("" if key == "now" else "") , fill="#17150F", font=font)
        d.text((360, y + 4), "上：在「拆」页（选中态）　下：首页", fill="#6B655A", font=ImageFont.truetype("/System/Library/Fonts/Hiragino Sans GB.ttc", 22))
        for j, f in enumerate(pair):
            board.paste(Image.open(f).convert("RGB"), (0, y + 50 + j * 152))
    board.save(HERE / "nav-board.png"); print("nav-board.png", board.size)

if __name__ == "__main__":
    main()
