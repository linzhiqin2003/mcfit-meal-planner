"""把做好的视频转成项目主页能直接播的文件，并截封面。

    python3 scripts/build_site_videos.py

输入（videos/ 下 HyperFrames 渲染的成片，目录本身不入库）：
  - videos/tutorial-workbuddy/renders/tutorial-workbuddy-16x9.mp4   安装教程，1920×1080，114 秒（前 36 秒是 Skill 和三个卖点），moov 已前置
  - videos/gym-promo/renders/gym-promo-v6.mp4                       宣传片，1080×1920，46 秒（麦当劳纸袋健身人 + 真实使用场景 + 三个卖点 + GYM 梗图结尾；v6 只把结尾的「GitHub 搜」改成新仓库名 mcfit-meal-planner，2026-10-18）
输出：
  - site/assets/video/install-tutorial.mp4  教程原样复制（码率已经够低、索引已前置，重编码只会掉画质）
  - site/assets/video/promo.mp4             宣传片缩到 720×1280、CRF 23，音频 AAC 96k，索引前置（边下边播）
  - site/assets/img/install-tutorial-poster.webp、promo-poster.webp  封面帧
教程的分段时间（「装」页的步骤跳转用）以 videos/tutorial-workbuddy/index.html 里各镜的 data-start 为准。
"""
from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIDEO_OUT = ROOT / "site/assets/video"
IMG_OUT = ROOT / "site/assets/img"
TUTORIAL = ROOT / "videos/tutorial-workbuddy/renders/tutorial-workbuddy-16x9.mp4"
PROMO = ROOT / "videos/gym-promo/renders/gym-promo-v6.mp4"
log = logging.getLogger("site-videos")


def run(cmd: list[str]) -> None:
    log.debug("运行：%s", " ".join(cmd))
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f"{cmd[0]} 失败：{r.stderr.strip()[-600:]}")


def poster(src: Path, at: float, width: int, out: Path) -> None:
    """截一帧，先出 PNG 再用 cwebp 转（本机 ffmpeg 没有 libwebp）"""
    with tempfile.TemporaryDirectory() as tmp:
        png = Path(tmp) / "frame.png"
        run(["ffmpeg", "-v", "error", "-y", "-ss", str(at), "-i", str(src), "-frames:v", "1", "-vf", f"scale={width}:-2", str(png)])
        run(["cwebp", "-quiet", "-q", "82", str(png), "-o", str(out)])
    log.info("封面 %s：%d KB", out.relative_to(ROOT), out.stat().st_size // 1024)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    for f in (TUTORIAL, PROMO):
        if not f.is_file():
            raise FileNotFoundError(f"找不到成片：{f.relative_to(ROOT)}（先在 videos/ 下渲染）")
    VIDEO_OUT.mkdir(parents=True, exist_ok=True)

    tut = VIDEO_OUT / "install-tutorial.mp4"
    shutil.copyfile(TUTORIAL, tut)
    log.info("教程 %s：%.1f MB（原样复制）", tut.relative_to(ROOT), tut.stat().st_size / 1e6)

    promo = VIDEO_OUT / "promo.mp4"
    run(["ffmpeg", "-v", "error", "-y", "-i", str(PROMO), "-vf", "scale=720:-2", "-c:v", "libx264", "-preset", "slow", "-crf", "23",
         "-profile:v", "high", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", str(promo)])
    log.info("宣传片 %s：%.1f MB", promo.relative_to(ROOT), promo.stat().st_size / 1e6)

    poster(TUTORIAL, 5.9, 1280, IMG_OUT / "install-tutorial-poster.webp")   # 片头：把麦当劳吃成健身餐 + 麦麦健身餐规划师
    poster(PROMO, 2.8, 540, IMG_OUT / "promo-poster.webp")                  # 「麦当劳 也能当健身餐 ？？？」+ 纸袋人举双吉


if __name__ == "__main__":
    main()
