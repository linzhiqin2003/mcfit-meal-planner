"""把 GPT Image 生成的红笔手写稿描成矢量：按「红色」取前景，按行范围裁出每句批注，potrace 描边，输出可内联的 SVG 片段。
    uv run --with pillow --with numpy python vectorize.py hand.png note-eat:60:470 note-save:520:1000
    uv run --with pillow --with numpy python vectorize.py hand2.png note-best:60:480 note-ok:540:960
每个参数是「输出名:起始行:结束行」（原图像素）；输出 <名>.inline.svg"""
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent


def main(src: str, pieces: list[str]) -> None:
    a = np.asarray(Image.open(HERE / src).convert("RGB")).astype(int)
    red = (a[:, :, 0] - a[:, :, 1] > 70) & (a[:, :, 0] > 140)
    for spec in pieces:
        name, y0, y1 = spec.split(":")
        m = red[int(y0):int(y1)]
        ys, xs = np.where(m)
        pad = 6
        t, b, l, r = ys.min() - pad, ys.max() + pad, xs.min() - pad, xs.max() + pad
        crop = m[t:b, l:r]
        bmp = HERE / f"{name}.pbm"
        Image.fromarray(np.where(crop, 0, 255).astype("uint8"), "L").convert("1").save(bmp)
        svg = HERE / f"{name}.svg"
        subprocess.run(["potrace", str(bmp), "-s", "-o", str(svg), "-t", "6", "-a", "1.1", "-O", "0.5", "--flat"], check=True)
        s = svg.read_text()
        d = " ".join(re.findall(r'<path d="([^"]+)"', s, re.S))
        tf = re.search(r'<g transform="([^"]+)"', s).group(1)
        out = f'<svg viewBox="0 0 {crop.shape[1]} {crop.shape[0]}" aria-hidden="true"><path transform="{tf}" d="{" ".join(d.split())}"/></svg>'
        (HERE / f"{name}.inline.svg").write_text(out)
        print(name, crop.shape[1], crop.shape[0], len(out), "bytes")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
