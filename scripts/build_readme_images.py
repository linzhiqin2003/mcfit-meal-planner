"""生成 README 的配图（docs/readme/），版式见 docs/mockups/readme 的 C 版：主页横幅 + 三个本事的三联图 + WorkBuddy 实操截图。

    python3 scripts/build_readme_images.py

需要 ffmpeg、cwebp 和 Google Chrome（只在本机跑，CI 不跑）。输入都在仓库里：
  - 横幅：site/ 首屏，用无头 Chrome 截图。截之前隐藏导航、入口按钮、副标题和滚动字幕，README 里的图不该像能点的界面
  - 三联图和实操截图：site/assets/video/install-tutorial.mp4 里动画停稳的帧（帧间差最小处，见 FRAMES）。教程重新剪辑后要重新找时间点
输出：
  - docs/readme/banner.webp         README 顶部横幅（1600 宽）
  - docs/readme/strip.webp          三个本事：拆层算热量 · 分顿吃 · 按价格排组合（每格 1280 宽，点开大图能看清字）
  - docs/readme/usage.webp          WorkBuddy 里的真实输出（带红笔批注）
  - docs/readme/social-preview.jpg  1280×640，仓库 Settings → Social preview 手动上传（GitHub 没有接口）
"""
from __future__ import annotations

import logging
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/readme"
TUTORIAL = ROOT / "site/assets/video/install-tutorial.mp4"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
# 教程里各镜动画停稳的时间（秒）：01 拆层（339 大卡、两片吉士打叉）、02 今晚 / 明早、03 四套组合卡、WorkBuddy 输出加批注
FRAMES = {"p01": 12.25, "p02": 22.9, "p03": 34.0, "usage": 100.5}
# 首屏截图时隐藏的元素；关掉所有动画和过渡，截到的就是最终画面（只靠等待时间会截到入场动画中途，半透明）
HIDE_CSS = ("<style>header.top,.focus-loop,.sub,.ticker,[class*='pill']{display:none!important}"
            "html,body{overflow:hidden!important}.stage{padding-top:56px!important}"
            "*,*::before,*::after{animation:none!important;transition:none!important}</style>")
log = logging.getLogger("readme-images")


def run(cmd: list[str]) -> None:
    log.debug("运行：%s", " ".join(cmd))
    subprocess.run(cmd, check=True, capture_output=True, timeout=300)


def frame(at: float, out: Path) -> None:
    run(["ffmpeg", "-v", "error", "-y", "-ss", str(at), "-i", str(TUTORIAL), "-frames:v", "1", str(out)])


def webp(src: Path, dst: Path, width: int = 0) -> None:
    run(["cwebp", "-quiet", "-q", "88", "-resize", str(width), "0", str(src), "-o", str(dst)])


def chrome_shot(url: str, out: Path, size: str, tmp: Path) -> None:
    """无头 Chrome 截图。Chrome 的子进程会继承输出管道，等管道关闭会卡住：输出写文件，截图文件大小稳定后结束整个进程组。"""
    with open(tmp / "chrome.log", "wb") as logf:
        p = subprocess.Popen([CHROME, "--headless=new", f"--user-data-dir={tmp / 'profile'}", "--hide-scrollbars",
                              "--allow-file-access-from-files", "--force-prefers-reduced-motion", "--force-device-scale-factor=2", f"--window-size={size}",
                              "--virtual-time-budget=8000", f"--screenshot={out}", url],
                             stdout=logf, stderr=subprocess.STDOUT, start_new_session=True)
    try:
        last, deadline = -1, time.time() + 60
        while time.time() < deadline:
            size_now = out.stat().st_size if out.exists() else 0
            if size_now and size_now == last:
                break
            last = size_now
            time.sleep(1)
        else:
            raise TimeoutError("Chrome 60 秒内没有写出截图")
    finally:
        # 主进程截完图会自己退出；退出后还没回收时，macOS 上对整个进程组发信号会报 EPERM，所以先回收再清理残留的子进程
        if p.poll() is None:
            p.terminate()
        try:
            p.wait(timeout=10)
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait()
        try:
            os.killpg(p.pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            pass


def banner(tmp: Path) -> None:
    site = tmp / "site"
    shutil.copytree(ROOT / "site", site, ignore=shutil.ignore_patterns("src-img", ".*"))
    html = (site / "index.html").read_text(encoding="utf-8")
    (site / "index.html").write_text(html.replace("</head>", HIDE_CSS + "</head>", 1), encoding="utf-8")
    shot = tmp / "hero.png"
    chrome_shot((site / "index.html").as_uri(), shot, "1280,640", tmp)   # 2 倍图：2560×1280
    # 内容在左上 2240×1050 内；再往下是背景色块的边缘
    run(["ffmpeg", "-v", "error", "-y", "-i", str(shot), "-vf", "crop=2240:1050:40:0", str(tmp / "banner.png")])
    webp(tmp / "banner.png", OUT / "banner.webp", 1600)
    run(["ffmpeg", "-v", "error", "-y", "-i", str(shot), "-vf", "crop=2240:1120:40:0,scale=1280:640", "-q:v", "3",
         str(OUT / "social-preview.jpg")])


def strip(tmp: Path) -> None:
    """三镜去掉顶部的 01/02/03 导航和底部那行说明，每格 1280 宽横排。

    按行统计非背景像素（三帧一样）：导航文字 84–153 行、下划线 186–191 行，内容 222–942 行，说明 961–1005 行；
    取 208–952 行，上下都落在空白里（之前按估计裁 120–1000 行，导航和说明各被切掉半截）。
    """
    ins = []
    for k in ("p01", "p02", "p03"):
        frame(FRAMES[k], tmp / f"{k}.png")
        ins += ["-i", str(tmp / f"{k}.png")]
    graph = ";".join(f"[{i}]crop=1920:744:0:208,scale=1280:-1[v{i}]" for i in range(3)) + ";[v0][v1][v2]hstack=3"
    run(["ffmpeg", "-v", "error", "-y", *ins, "-filter_complex", graph, str(tmp / "strip.png")])
    webp(tmp / "strip.png", OUT / "strip.webp")


def usage(tmp: Path) -> None:
    frame(FRAMES["usage"], tmp / "usage.png")
    webp(tmp / "usage.png", OUT / "usage.webp", 1600)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    for tool in ("ffmpeg", "cwebp"):
        if not shutil.which(tool):
            sys.exit(f"缺少 {tool}")
    if not Path(CHROME).exists():
        sys.exit(f"找不到 Chrome：{CHROME}")
    OUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="readme-img-") as t:
        tmp = Path(t)
        banner(tmp)
        strip(tmp)
        usage(tmp)
    for f in sorted(OUT.iterdir()):
        log.info("%-20s %6.0f KB", f.name, f.stat().st_size / 1024)


if __name__ == "__main__":
    main()
