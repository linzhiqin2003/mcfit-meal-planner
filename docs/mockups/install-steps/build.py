"""「装」页「三组动作」三版 mockup：第一组有两段安装命令、比后两组高出一大截，右边两栏留白太多（用户 10-19 指出）。

    python3 docs/mockups/install-steps/build.py

A 折叠左栏：macOS / Windows 做成切换，只显示一段命令（按访客系统默认选好）
B 右栏加内容：第二组加连接器入口路径和要粘贴的配置（可复制），第三组加另外几种说法和离线演示
C 改成横排：三组上下排成三行，标题在左、内容在右，第一组两段命令左右并排
在 site/ 副本里替换这一节的 HTML、追加 CSS，无头 Chrome 截电脑（1440 宽）和手机（375 宽），
输出 board-A.png、board-B.png、board-C.png（不入库）。
"""
from __future__ import annotations

import os
import re
import signal
import subprocess
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
FREEZE = "*,*::before,*::after{animation:none!important;transition:none!important}"
COPY = '<button class="copy" type="button" aria-label="复制"><svg class="i"><use href="#i-copy"/></svg></button>'
PEN = ('<svg class="mk-pen" viewBox="0 0 302 24" preserveAspectRatio="none" aria-hidden="true"><path d="M4.0 8.0 C5.0 9.5 6.7 15.7 10.0 17.0 '
       'C13.3 18.3 14.1 17.0 24.0 16.0 C54.4 12.3 115.3 9.0 161.0 9.3 C206.7 8.8 252.3 11.6 298.0 13.7"/></svg>')
MAC = ('<div class="code" aria-label="macOS 安装命令">'
       '<span class="ln"><span class="pr">$</span>git clone https://github.com/linzhiqin2003/mcfit-meal-planner.git</span>'
       '<span class="ln"><span class="pr">$</span>cd mcfit-meal-planner &amp;&amp; python3 install.py --target workbuddy</span>' + COPY + '</div>')
WIN = ('<div class="code" aria-label="Windows 安装命令">'
       '<span class="ln"><span class="pr">&gt;</span>git clone https://github.com/linzhiqin2003/mcfit-meal-planner.git</span>'
       '<span class="ln"><span class="pr">&gt;</span>cd mcfit-meal-planner</span>'
       '<span class="ln"><span class="pr">&gt;</span>py install.py --target workbuddy</span>' + COPY + '</div>')
JSON = """{
  "mcpServers": {
    "mcd-mcp": {
      "type": "streamablehttp",
      "url": "https://mcp.mcd.cn",
      "headers": {
        "Authorization": "Bearer 你的 Token"
      }
    }
  }
}"""

# ---------- A：折叠左栏 ----------
A_STEP1 = ('<div class="mk-os" role="tablist" aria-label="电脑系统">'
           f'<button role="tab" aria-selected="true">macOS · 终端{PEN}</button>'
           f'<button role="tab" aria-selected="false">Windows · PowerShell{PEN}</button></div>' + MAC +
           '<p class="note">已按你的电脑选好系统。装好后在 WorkBuddy 的技能页确认 mcfit-meal-planner 已开启</p>')
A_CSS = """
.mk-os{display:flex;gap:28px;margin:18px 0 0;border-bottom:1px solid var(--rule)}
.mk-os button{position:relative;padding:0 0 10px;border:0;background:none;font:inherit;font-size:15px;color:var(--ink-3);cursor:pointer}
.mk-os button[aria-selected="true"]{color:var(--ink);font-weight:600}
.mk-pen{position:absolute;left:-4%;bottom:-6px;width:108%;height:9px;fill:none;stroke:var(--red);stroke-width:3;stroke-linecap:round;opacity:0}
.mk-os button[aria-selected="true"] .mk-pen{opacity:1}
.ins-step .mk-os+.code{margin-top:14px}
"""

# ---------- B：右栏加内容 ----------
B_STEP2 = ('<p class="os mk-path">WorkBuddy：连接器<span>›</span>自定义连接器<span>›</span>配置 MCP，粘贴：</p>'
           '<div class="code mk-json" aria-label="麦当劳 MCP 配置">' + JSON.replace("<", "&lt;") + COPY + '</div>'
           '<p class="note">Token 填原文：WorkBuddy 不读环境变量。保存后把 mcd-mcp 设为「启用」</p>')
B_STEP3 = ('<p class="os">也可以这样说</p><ul class="mk-more">'
           '<li>「减脂期，晚饭想吃麦当劳，40 块以内，碳水别太高」</li>'
           '<li>「明早 7 点半在福州路吃早餐，400 大卡，蛋白质 25 克」</li>'
           '<li>「双层吉士汉堡去掉吉士、只吃馅，还剩多少热量」</li></ul>'
           '<p class="note">还没申请 Token？先说「用离线快照演示一下」</p>')
B_CSS = """
.ins-step .mk-path span{margin:0 6px;color:var(--rule-2)}
.ins-step .mk-json{white-space:pre-wrap;padding-right:18px;font-size:12px;line-height:1.75}   /* 复制键只压在第一行「{」上，右边不用留那么宽 */
@media (max-width:640px){.ins-step .mk-json{padding-right:16px;font-size:11.5px}}
.mk-more{margin:8px 0 0;padding:0;list-style:none}
.mk-more li{padding:12px 0;border-bottom:1px solid var(--rule);font-size:16px;line-height:1.6;font-weight:500;color:var(--ink)}
.mk-more li:first-child{padding-top:4px}
"""

# ---------- C：横排三行 ----------
C_CSS = """
.ins-steps{grid-template-columns:minmax(0,1fr)!important}
.ins-step,.ins-step:first-child,.ins-step:last-child{display:grid;grid-template-columns:360px minmax(0,1fr);column-gap:48px;align-items:start;padding:30px 0 32px!important;border-left:0!important}
.ins-step+.ins-step{border-top:1px solid var(--rule)}
.ins-step-h{grid-row:1/span 9;padding-top:2px}
.mk-pair{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));column-gap:28px}
.ins-step .mk-pair .os{margin-top:0}
.ins-step>p:first-of-type,.ins-step>.mk-pair{margin-top:4px}
.ins-step .say{margin-top:4px}
.ins-step .mk-pair+.note{margin-top:12px}
@media (max-width:900px){
 .ins-step .mk-pair .os{margin-top:16px}
 .ins-step,.ins-step:first-child,.ins-step:last-child{grid-template-columns:minmax(0,1fr);padding:24px 0 26px!important}
 .ins-step-h{grid-row:auto}
 .mk-pair{grid-template-columns:minmax(0,1fr)}
 .ins-step .mk-pair .os+.code+.os{margin-top:16px}
}
"""


def steps_block(src: str) -> tuple[int, int]:
    i = src.index('<ol class="ins-steps">')
    return i, src.index("</ol>", i) + len("</ol>")


def variant(src: str, key: str) -> str:
    i, j = steps_block(src)
    ol = src[i:j]
    lis = re.findall(r'<li class="ins-step".*?</li>', ol, re.S)
    assert len(lis) == 3, len(lis)
    s1, s2, s3 = lis
    head = lambda li: li[:li.index("</div>", li.index('class="ins-step-h"')) + len("</div>")]
    body1 = s1[len(head(s1)):-len("</li>")]
    if key == "now":
        css = ""
    elif key == "A":
        s1 = head(s1) + A_STEP1 + "</li>"
        css = A_CSS
    elif key == "B":
        s2 = s2.replace("</li>", B_STEP2 + "</li>")
        s3 = s3.replace("</li>", B_STEP3 + "</li>")
        css = B_CSS
    else:
        pair = re.match(r'\s*(<p class="os">.*?</div>)\s*(<p class="os">.*?</div>)\s*(<p class="note">.*?</p>)\s*$', body1, re.S)
        s1 = head(s1) + f'<div class="mk-pair"><div>{pair.group(1)}</div><div>{pair.group(2)}</div></div>{pair.group(3)}</li>'
        css = C_CSS
    out = src[:i] + '<ol class="ins-steps">' + s1 + s2 + s3 + "</ol>" + src[j:]
    # 只滚 iframe 自己（scrollIntoView 会连外层拼板一起滚）；?s=title 滚到「三组动作」，?s=2 滚到第二组
    script = """<script>addEventListener("load",function(){setTimeout(function(){var m=/s=(\\w+)/.exec(location.search);if(!m)return;
var e=m[1]==="title"?document.querySelector(".ins-title"):document.querySelectorAll(".ins-step")[+m[1]-1];
scrollTo(0,scrollY+e.getBoundingClientRect().top-24)},1500)})</script>"""
    return out.replace("</head>", f"<style>{FREEZE}{css}</style></head>", 1).replace("</body>", script + "</body>", 1)


def shot(url: str, out: Path, w: int, h: int, prof: Path) -> None:
    out.unlink(missing_ok=True)
    with open(prof.parent / "chrome.log", "wb") as logf:
        p = subprocess.Popen([CHROME, "--headless=new", f"--user-data-dir={prof}", "--hide-scrollbars", "--allow-file-access-from-files",
                              "--force-prefers-reduced-motion", "--force-device-scale-factor=2", "--run-all-compositor-stages-before-draw", f"--window-size={w},{h}",
                              "--virtual-time-budget=9000", f"--screenshot={out}", url], stdout=logf, stderr=subprocess.STDOUT,
                             start_new_session=True)
    last, deadline = -1, time.time() + 90
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
    with tempfile.TemporaryDirectory(prefix="install-steps-") as t:
        tmp = Path(t)
        for name in ("assets", "data"):
            os.symlink(ROOT / "site" / name, tmp / name)
        prof = tmp / "profile"
        for k in ("A", "B", "C", "now"):
            (tmp / f"{k}.html").write_text(variant(src, k), encoding="utf-8")

        def frame(page, w, h, k, s="title"):
            return (f'<div class="fr" style="width:{w*k:.0f}px;height:{h*k:.0f}px"><iframe src="{page}.html?s={s}#/装" width="{w}" height="{h}" '
                    f'style="transform:scale({k});transform-origin:0 0"></iframe></div>')
        boards = {
            "A": ("A 折叠左栏：系统切换", "macOS / Windows 做成切换（红笔线标当前），只显示一段命令，默认按访客电脑选好。第一栏从两段命令缩成一段；电脑上右边两栏仍空出一截，手机上这一节短了一半",
                  frame("A", 1440, 760, .6), [frame("A", 375, 812, .8)]),
            "B": ("B 右栏加内容", "第二组加上连接器入口路径和要粘贴的配置（可复制，Token 处留空），第三组加另外几种说法和离线演示。左栏不动，三栏都有一块可以直接用的东西",
                  frame("B", 1440, 860, .6), [frame("B", 375, 812, .8, "2"), frame("B", 375, 812, .8, "3")]),
            "C": ("C 改成横排", "三组上下排成三行，标题和时间按钮在左，内容在右；第一组两段命令左右并排。哪一组内容多，那一行就高，不会空出整栏",
                  frame("C", 1440, 760, .6), [frame("C", 375, 812, .8)]),
            "now": ("现在", "第一组两段命令，右边两栏只有一两句话", frame("now", 1440, 760, .6), []),
        }
        style = """<!doctype html><meta charset="utf-8"><style>body{margin:0;padding:28px;background:#fff;
font:600 22px -apple-system,"PingFang SC",sans-serif;color:#17150F}h2{margin:0 0 6px;font-size:28px}
p{margin:0 0 16px;font-weight:400;font-size:17px;line-height:1.5;color:#47433B;max-width:48em}
.row{display:flex;gap:24px;align-items:flex-start;margin-bottom:24px}.lbl{font-size:15px;color:#77705F;margin:0 0 8px;font-weight:600}
.fr{overflow:hidden;border:1px solid #D5CEBF;border-radius:10px;flex:none}iframe{border:0;display:block}</style>"""
        for k, (title, desc, desk, phones) in boards.items():
            phone_html = f'<div class="lbl">手机</div><div class="row">{"".join(phones)}</div>' if phones else ""
            (tmp / f"board-{k}.html").write_text(style + f'<h2>{title}</h2><p>{desc}</p><div class="lbl">电脑</div><div class="row">{desk}</div>'
                                                 + phone_html, encoding="utf-8")
            h = 200 + int(desk.split("height:")[1].split("px")[0]) + (700 if phones else 0)
            shot((tmp / f"board-{k}.html").as_uri(), HERE / f"board-{k}.png", 920, h, prof)
            print("board", k, (HERE / f"board-{k}.png").stat().st_size)


if __name__ == "__main__":
    main()
