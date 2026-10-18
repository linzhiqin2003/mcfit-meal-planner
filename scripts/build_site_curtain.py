"""页脚「小人谢幕」的素材：三个小人从腰部以上探出来举着空白牌子（site/src-img/bow-*-raw.png，GPT Image 出图，生成脚本 site/src-img/gen_bow.sh；
第一版全身像太高，留在 site/src-img/bow-v1/）。

    python3 scripts/build_site_curtain.py

- 按不透明区域裁边（腰部的切口落在图片下沿，页面上压在页脚的地平线上），按高度 360px 出 WebP：site/assets/img/bow-{drumstick,burger,nugget}.webp
- 找出牌子的白色内框（牌子是纯白卡片，按「整行都很白」的行和列定位，鞋子也是白的但不会占满一整行），
  换算成裁剪后图片的百分比，写进 site/assets/img/bow.json，并同步改写 index.html 里每个小人的 --ar/--sx/--sy/--sw/--sh 和图片宽高
  （页脚的牌子文字按这个框摆），test_site_curtain 检查两边一致。
不用 Pillow（本机 Pillow dlopen 会挂起）：ffmpeg 读写像素，cwebp 编码，与 build_site_assets.py 一致。
"""
from __future__ import annotations

import json
import logging
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "videos/gym-promo/scripts"))
sys.path.insert(0, str(ROOT / "scripts"))
from slice_layers import read_rgba, write_rgba  # noqa: E402
from build_site_assets import webp  # noqa: E402

SRC = ROOT / "site/src-img"
OUT = ROOT / "site/assets/img"
HTML = ROOT / "site/index.html"
HEIGHT = 360
CAST = ["drumstick", "burger", "nugget"]     # 页脚从左到右：练、拆、装
log = logging.getLogger("site-curtain")


def sign_box(img: np.ndarray) -> tuple[int, int, int, int]:
    """牌子白色内框 (x0, y0, x1, y1)：整行白像素超过图宽 35% 的连续行里，白像素占多数的列"""
    rgb, a = img[..., :3].astype(int), img[..., 3]
    white = (rgb.min(axis=2) > 236) & (a > 250)
    h, w = white.shape
    rows = np.where(white.sum(axis=1) > w * 0.35)[0]
    if len(rows) < 10:
        raise ValueError("找不到牌子：没有足够白的行")
    # 取最长的一段连续行（牌子），避免零星的白行
    runs = np.split(rows, np.where(np.diff(rows) > 1)[0] + 1)
    band = max(runs, key=len)
    cols = np.where(white[band].mean(axis=0) > 0.5)[0]
    return int(cols.min()), int(band.min()), int(cols.max()) + 1, int(band.max()) + 1


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    meta = {}
    for name in CAST:
        img = read_rgba(SRC / f"bow-{name}-raw.png")
        ys, xs = np.where(img[..., 3] > 128)
        x0, x1, y0, y1 = xs.min() - 4, xs.max() + 5, ys.min() - 4, ys.max() + 1
        crop = img[y0:y1, x0:x1].copy()
        tmp = SRC / f"bow-{name}-crop.png"
        write_rgba(crop, tmp)
        webp(tmp, OUT / f"bow-{name}.webp", 86, 0, HEIGHT)
        sx0, sy0, sx1, sy1 = sign_box(crop)
        h, w = crop.shape[:2]
        pct = lambda v, d: round(v / d * 100, 2)
        meta[name] = {"aspect": round(w / h, 4), "sign": {"x": pct(sx0, w), "y": pct(sy0, h), "w": pct(sx1 - sx0, w), "h": pct(sy1 - sy0, h)}}
        log.info("%s：%dx%d，牌子 %s", name, w, h, meta[name]["sign"])
    (OUT / "bow.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    sync_html(meta)


def sync_html(meta: dict) -> None:
    """把 bow.json 的数值写回 index.html 里三个小人的 style 和 <img> 宽高"""
    html = HTML.read_text(encoding="utf-8")
    for name, m in meta.items():
        sg = m["sign"]
        style = f'--ar:{m["aspect"]};--sx:{sg["x"]}%;--sy:{sg["y"]}%;--sw:{sg["w"]}%;--sh:{sg["h"]}%'
        pat = re.compile(r'(<a class="bow"[^>]*style=")[^"]*("><img src="assets/img/bow-' + name + r'\.webp" alt="" width=")\d+(" height=")\d+(")')
        html, k = pat.subn(lambda mo: mo[1] + style + mo[2] + str(round(m["aspect"] * HEIGHT)) + mo[3] + str(HEIGHT) + mo[4], html)
        if k != 1:
            raise RuntimeError(f"index.html 里找不到小人 {name} 的标记")
    HTML.write_text(html, encoding="utf-8")
    log.info("已同步 index.html 里三个小人的牌子位置")


if __name__ == "__main__":
    main()
