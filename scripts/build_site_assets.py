"""项目主页的图片素材：裁掉透明边、转 WebP，并写出小人眼睛的位置。

    python3 scripts/build_site_assets.py

- 信息页页眉的小人头像（site/src-img/{drumstick,nugget,burger}-raw.png）按不透明区域裁边，让脚底正好落在图片下沿。
- 首屏的三个姿势（site/src-img/*-hang/sit/peek-raw.png，GPT Image 出的无眼睛全身像）同样裁边；
  眼睛和接触点是在 1024×1536 原图上手量的，换算成裁剪后图片的百分比，写进 poses.json，home.js 靠它把眼睛和字母对齐。
  另按透明度算出几个高度上身体的左右边缘（edges），首屏标签的箭头指到边缘外一点，不戳进身体。
- 汉堡切片（「拆」页零件，cutouts/burger-v3，照实拍比例与配料图重做）、金色 ᗰ 来自宣传片素材（videos/gym-promo/assets/cutouts）。
不用 Pillow（本机 Pillow dlopen 会挂起）：ffmpeg 读写像素，cwebp 编码。
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "videos/gym-promo/scripts"))
from slice_layers import read_rgba, write_rgba  # noqa: E402

OUT = ROOT / "site/assets/img"
CUT = ROOT / "videos/gym-promo/assets/cutouts"
AVATARS = ["drumstick", "nugget", "burger"]
# 首屏 A 方向的三个姿势：眼睛 + 和标题接触的点（anchor，原图坐标）
#   drumstick-hang：两只拳头的中心（抓字母 t 的横杠）
#   nugget-sit：坐的那条线（屁股底边，坐在字母 m 的顶上）
#   burger-side：手指根部（对准金色 ᗰ 最右竖笔的外沿，根部那一小段被 ᗰ 的金边压住）；grip 是从图左边出发绕四根手指一圈的折线，
#                首页把这块画在 ᗰ 前面、其余部分画在 ᗰ 后面，看起来是从侧后方伸手扒住 ᗰ 的边
POSES = {
    "drumstick-hang": {"l": (440, 758), "r": (599, 758), "w": 42, "h": 56, "anchor": (513, 72)},
    "nugget-sit": {"l": (425, 586), "r": (604, 586), "w": 50, "h": 66, "anchor": (512, 1011)},
    "burger-side": {"l": (371, 463), "r": (557, 499), "w": 40, "h": 52, "anchor": (140, 677),
                    "grip": [(0, 550), (124, 550), (128, 612), (158, 620), (158, 690), (152, 742), (146, 802), (0, 802)]},
}


def webp(src: Path, dst: Path, q: int = 86, width: int = 0, height: int = 0) -> None:
    subprocess.run(["cwebp", "-quiet", "-q", str(q), "-alpha_q", "100", "-resize", str(width), str(height), str(src), "-o", str(dst)],
                   check=True, timeout=120)


def edges(img: np.ndarray) -> dict:
    """每隔 10% 图高取一行，记下不透明像素的最左、最右（图宽 %）。"""
    a = img[..., 3] > 128
    h, w = a.shape
    out = {}
    for pct in range(10, 100, 10):
        xs = np.where(a[int(h * pct / 100)])[0]
        if len(xs):
            out[str(pct)] = [round(float(xs.min()) / w * 100, 1), round(float(xs.max()) / w * 100, 1)]
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for name in AVATARS:
        img = read_rgba(ROOT / f"site/src-img/{name}-raw.png")
        ys, xs = np.where(img[..., 3] > 128)
        x0, x1, y0, y1 = xs.min() - 4, xs.max() + 5, ys.min() - 4, ys.max() + 1
        crop = img[y0:y1, x0:x1].copy()
        tmp = ROOT / f"site/src-img/{name}-crop.png"
        write_rgba(crop, tmp)
        webp(tmp, OUT / f"buddy-{name}.webp", 86, 420)
        print("avatar", name)
    poses = {}
    for name, e in POSES.items():
        img = read_rgba(ROOT / f"site/src-img/{name}-raw.png")
        ys, xs = np.where(img[..., 3] > 128)
        x0, x1, y0, y1 = xs.min() - 4, xs.max() + 5, ys.min() - 4, ys.max() + 5
        crop = img[y0:y1, x0:x1].copy()
        tmp = ROOT / f"site/src-img/{name}-crop.png"
        write_rgba(crop, tmp)
        # 首屏最大字号 236px，小人最高 1.18em ≈ 280px；按高度 640 出图，够 2 倍屏（鸡腿是细长条，按宽度出会到 1400px 高）
        webp(tmp, OUT / f"pose-{name}.webp", 86, 0, 640)
        w, h = int(x1 - x0), int(y1 - y0)
        pct = lambda p: [round(min(100.0, max(0.0, float(p[0] - x0) / w * 100)), 2), round(min(100.0, max(0.0, float(p[1] - y0) / h * 100)), 2)]
        poses[name] = {"aspect": round(w / h, 4), "l": pct(e["l"]), "r": pct(e["r"]), "anchor": pct(e["anchor"]),
                       "ew": round(e["w"] / w * 100, 2), "eh": round(e["h"] / h * 100, 2), "edges": edges(crop)}
        if "grip" in e:
            poses[name]["grip"] = [pct(q) for q in e["grip"]]
        print(name, poses[name])
    (OUT / "poses.json").write_text(json.dumps(poses, ensure_ascii=False, indent=1), encoding="utf-8")
    for n in ["bun-top", "pickles", "cheese-1", "patty-1", "cheese-2", "patty-2", "bun-bottom"]:
        webp(CUT / "burger-v3" / f"layer-{n}.png", OUT / f"layer-{n}.webp", 86)
    webp(CUT / "gold-m.png", OUT / "gold-m.webp", 90, 360)


if __name__ == "__main__":
    main()
