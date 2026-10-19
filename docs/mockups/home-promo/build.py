"""首页放宣传片的三版 mockup：在 site/ 副本里注入 HTML 和 CSS，用无头 Chrome 截手机（375 宽）和电脑（1280 宽）。

    python3 docs/mockups/home-promo/build.py

A 首屏下方加一节：首页可以往下滚，宣传片大竖卡 + 标题 + 播放按钮
B 首屏内的入口卡：手机在三个入口下面放一张虚线框横卡；电脑在主视觉右下角的空白处放竖卡
C 浮动胶囊：右下角「▶ 46 秒看懂」，点开全屏播放（另截一张打开后的样子）
输出 board-A.png、board-B.png、board-C.png（每版一张：上面手机，下面电脑；不入库）。
"""
from __future__ import annotations

import os
import shutil
import signal
import subprocess
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PLAY = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5.5v13l11-6.5z"/></svg>'
FREEZE = "*,*::before,*::after{animation:none!important;transition:none!important}"

A_HTML = f"""<section class="mk-a"><div class="wrap mk-a-in">
<figure class="mk-a-card"><img src="assets/img/promo-poster.webp" alt=""><span class="mk-play">{PLAY}</span></figure>
<div class="mk-a-txt"><div class="mk-kicker">宣传片 · 0:46</div><h2>46 秒看懂<br>它怎么帮你点</h2>
<p>拆层算热量、分顿吃、按价格排组合，都在这支片子里。</p>
<span class="mk-btn">{PLAY}播放宣传片</span></div></div></section><script>/* 只滚 iframe 自己：scrollIntoView 会连外层拼板页一起滚，拼板顶部被裁、底部露白 */if(location.search.indexOf("s=1")>0)addEventListener("load",function(){{setTimeout(function(){{var r=document.querySelector(".mk-a").getBoundingClientRect();scrollTo(0,scrollY+r.top-(innerHeight-r.height)/2)}},300)}})</script>"""
A_CSS = """
html,body{background:var(--paper)!important}
.home{min-height:auto!important}
.mk-a{padding:72px 0 96px;border-top:1px solid var(--rule);min-height:72vh;display:flex;align-items:center}
.mk-a-in{display:flex;gap:64px;align-items:center;justify-content:center;width:100%}
.mk-a-card{position:relative;flex:0 0 300px;margin:0;border-radius:22px;overflow:hidden;box-shadow:0 18px 40px -18px rgba(23,21,15,.35)}
.mk-a-card img{display:block;width:100%;height:auto}
.mk-play{position:absolute;left:50%;top:50%;width:76px;height:76px;margin:-38px 0 0 -38px;border-radius:50%;background:var(--red);display:grid;place-items:center}
.mk-play svg{width:30px;height:30px;fill:#fff;margin-left:4px}
.mk-kicker{font-size:15px;color:var(--ink-3);letter-spacing:.04em}
.mk-a-txt h2{margin:10px 0 14px;font-size:44px;line-height:1.15;font-weight:800;letter-spacing:-.01em}
.mk-a-txt p{margin:0 0 22px;font-size:17px;line-height:1.6;color:var(--ink-2);max-width:26em}
.mk-btn{display:inline-flex;align-items:center;gap:8px;height:46px;padding:0 20px 0 16px;border:1.5px dashed var(--ink);border-radius:999px;font-weight:700;font-size:16px}
.mk-btn svg{width:18px;height:18px;fill:var(--red)}
@media (max-width:760px){
 .mk-a{padding:36px 0 48px;min-height:0}
 .mk-a-in{gap:18px;align-items:flex-end}
 .mk-a-card{flex-basis:46%;border-radius:16px}
 .mk-play{width:54px;height:54px;margin:-27px 0 0 -27px}.mk-play svg{width:22px;height:22px}
 .mk-a-txt h2{font-size:26px;margin:6px 0 10px}
 .mk-a-txt p{font-size:14px;margin-bottom:14px}
 .mk-btn{height:40px;font-size:14px;padding:0 14px 0 12px}
 .mk-kicker{font-size:13px}
}"""

B_HTML = f"""<a class="mk-b" href="#"><span class="mk-b-thumb"><img src="assets/img/promo-poster.webp" alt=""><span class="mk-play">{PLAY}</span></span>
<span class="mk-b-txt"><b>宣传片 <i>0:46</i></b><span>麦当劳也能当健身餐？46 秒看懂</span></span></a>"""
B_CSS = """
.mk-b{position:absolute;z-index:4;right:var(--gutter);bottom:70px;display:flex;align-items:center;gap:16px;width:330px;padding:10px;border:1.5px dashed var(--ink);border-radius:20px;background:var(--paper);color:var(--ink);text-decoration:none}
.mk-b-thumb{flex:0 0 72px}
.mk-b-thumb{position:relative;display:block;border-radius:12px;overflow:hidden}
.mk-b-thumb img{display:block;width:100%;height:auto}
.mk-play{position:absolute;left:50%;top:50%;width:52px;height:52px;margin:-26px 0 0 -26px;border-radius:50%;background:var(--red);display:grid;place-items:center}
.mk-play svg{width:22px;height:22px;fill:#fff;margin-left:3px}
.mk-b-txt{display:flex;flex-direction:column;gap:4px;padding:0}
.mk-b-txt b{font-size:17px}.mk-b-txt i{font-style:normal;font-weight:500;color:var(--ink-3);margin-left:4px}
.mk-b-txt span{font-size:13px;color:var(--ink-2)}
@media (max-width:760px){
 .home{align-items:flex-start!important}
 .mk-b{left:16px;right:16px;bottom:58px;width:auto;flex-direction:row;align-items:center;gap:14px;padding:8px;border-radius:16px}
 .mk-b-thumb{flex:0 0 58px;border-radius:10px}
 .mk-play{width:30px;height:30px;margin:-15px 0 0 -15px}.mk-play svg{width:14px;height:14px;margin-left:2px}
 .mk-b-txt{padding:0}
 .mk-b-txt b{font-size:16px}
}"""

C_HTML = f"""<a class="mk-c" href="#"><span class="mk-c-dot"><img src="assets/img/promo-poster.webp" alt=""></span><span class="mk-c-txt">{PLAY}46 秒看懂</span></a>"""
C_CSS = """
.mk-c{position:fixed;z-index:50;right:24px;bottom:70px;display:inline-flex;align-items:center;gap:10px;height:56px;padding:0 20px 0 6px;border:1.5px solid var(--ink);border-radius:999px;background:var(--paper);color:var(--ink);font-weight:700;font-size:16px;text-decoration:none;box-shadow:0 10px 24px -12px rgba(23,21,15,.45)}
.mk-c-dot{width:44px;height:44px;border-radius:50%;overflow:hidden;flex:none}
.mk-c-dot img{width:100%;height:auto;margin-top:-14%}
.mk-c-txt{display:inline-flex;align-items:center;gap:6px}.mk-c-txt svg{width:16px;height:16px;fill:var(--red)}
@media (max-width:760px){.mk-c{right:16px;bottom:56px;height:50px;font-size:15px}.mk-c-dot{width:38px;height:38px}}"""
C_OPEN_HTML = f"""<div class="mk-modal"><div class="mk-modal-in"><img src="assets/img/promo-poster.webp" alt=""><span class="mk-play">{PLAY}</span>
<span class="mk-x">×</span></div></div>"""
C_OPEN_CSS = C_CSS + """
.mk-modal{position:fixed;inset:0;z-index:100;background:rgba(23,21,15,.72);display:grid;place-items:center}
.mk-modal-in{position:relative;height:min(86vh,760px);aspect-ratio:9/16;border-radius:20px;overflow:hidden}
.mk-modal-in img{width:100%;height:100%;object-fit:cover;display:block}
.mk-play{position:absolute;left:50%;top:50%;width:72px;height:72px;margin:-36px 0 0 -36px;border-radius:50%;background:var(--red);display:grid;place-items:center}
.mk-play svg{width:28px;height:28px;fill:#fff;margin-left:4px}
.mk-x{position:absolute;right:12px;top:10px;width:36px;height:36px;border-radius:50%;background:rgba(251,249,244,.92);display:grid;place-items:center;font-size:24px;line-height:1}"""


def variant(src: str, where: str, html: str, css: str) -> str:
    out = src.replace("</head>", f"<style>{FREEZE}{css}</style></head>", 1)
    if where == "after-home":            # A：首页主视觉那一屏之后
        i = out.index('<main class="view home')
        j = out.index("</main>", i) + len("</main>")
        return out[:j] + html + out[j:]
    if where == "in-home":               # B：首页这一屏里，滚动字幕前（按整个首页定位）
        i = out.index('<div class="ticker"')
        return out[:i] + html + out[i:]
    return out.replace("</body>", html + "</body>", 1)     # C：浮在页面上


def shot(url: str, out: Path, w: int, h: int, prof: Path) -> None:
    out.unlink(missing_ok=True)
    with open(prof.parent / "chrome.log", "wb") as logf:
        p = subprocess.Popen([CHROME, "--headless=new", f"--user-data-dir={prof}", "--hide-scrollbars", "--allow-file-access-from-files",
                              "--force-prefers-reduced-motion", "--force-device-scale-factor=2", "--run-all-compositor-stages-before-draw", f"--window-size={w},{h}",
                              "--virtual-time-budget=8000", f"--screenshot={out}", url], stdout=logf, stderr=subprocess.STDOUT,
                             start_new_session=True)
    last, deadline = -1, time.time() + 60
    while time.time() < deadline:
        n = out.stat().st_size if out.exists() else 0
        if n and n == last:
            break
        last = n
        time.sleep(1)
    if p.poll() is None:
        p.terminate()
    p.wait(timeout=10)
    try:
        os.killpg(p.pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        pass


def main() -> None:
    src = (ROOT / "site/index.html").read_text(encoding="utf-8")
    pages = {"A": variant(src, "after-home", A_HTML, A_CSS), "B": variant(src, "in-home", B_HTML, B_CSS),
             "C": variant(src, "float", C_HTML, C_CSS), "C2": variant(src, "float", C_OPEN_HTML, C_OPEN_CSS)}
    with tempfile.TemporaryDirectory(prefix="home-promo-") as t:
        tmp = Path(t)
        for name in ("assets", "data"):
            os.symlink(ROOT / "site" / name, tmp / name)
        prof = tmp / "profile"
        for k, html in pages.items():
            (tmp / f"{k}.html").write_text(html, encoding="utf-8")
        def frame(k, w, h, scale, q=""):
            return (f'<div class="fr" style="width:{w*scale:.0f}px;height:{h*scale:.0f}px"><iframe src="{k}.html{q}" width="{w}" height="{h}" '
                    f'style="transform:scale({scale});transform-origin:0 0"></iframe></div>')
        # 每版一张图：上面一排手机（375 宽），下面电脑（1280×800），手机上看也看得清
        boards = {"A": ("A 首屏下方加一节", "首页可以往下滚。手机左边是首屏、右边是滚到宣传片那一节；电脑是滚到那一节",
                        [frame("A", 375, 812, .8), frame("A", 375, 812, .8, "?s=1")], frame("A", 1280, 800, .6, "?s=1")),
                  "B": ("B 首屏内的入口卡", "不用滚动就能看到。手机放在三个入口下面，电脑放在主视觉右下角",
                        [frame("B", 375, 812, .8)], frame("B", 1280, 800, .6)),
                  "C": ("C 浮动胶囊", "右下角常驻「46 秒看懂」，点开全屏播放。手机右边是点开之后",
                        [frame("C", 375, 812, .8), frame("C2", 375, 812, .8)], frame("C", 1280, 800, .6))}
        style = """<!doctype html><meta charset="utf-8"><style>body{margin:0;padding:28px;background:#fff;
font:600 22px -apple-system,"PingFang SC",sans-serif;color:#17150F}h2{margin:0 0 6px;font-size:28px}
p{margin:0 0 16px;font-weight:400;font-size:17px;line-height:1.5;color:#47433B;max-width:44em}
.row{display:flex;gap:24px;align-items:flex-start;margin-bottom:24px}.lbl{font-size:15px;color:#77705F;margin:0 0 8px;font-weight:600}
.fr{overflow:hidden;border:1px solid #D5CEBF;border-radius:10px;flex:none}iframe{border:0;display:block}</style>"""
        for k, (title, desc, phones, desk) in boards.items():
            (tmp / f"board-{k}.html").write_text(style + f'<h2>{title}</h2><p>{desc}</p><div class="lbl">手机</div><div class="row">{"".join(phones)}</div>'
                                                 f'<div class="lbl">电脑</div><div class="row">{desk}</div>', encoding="utf-8")
            shot((tmp / f"board-{k}.html").as_uri(), HERE / f"board-{k}.png", 830, 1330, prof)
            print("board", k, (HERE / f"board-{k}.png").stat().st_size)


if __name__ == "__main__":
    main()
