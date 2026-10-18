"""手绘红笔笔画（圈、下划线、箭头、对勾、叉、强调线）：在理想曲线上加一点固定种子的抖动，输出 SVG path。
python3 strokes.py  → 打印每一笔的 viewBox 与 d，复制进 site/index.html"""
import math
import random

random.seed(7)


def smooth(pts):
    """Catmull-Rom 转三次贝塞尔，得到顺滑的一笔"""
    d = f"M{pts[0][0]:.1f} {pts[0][1]:.1f}"
    for i in range(len(pts) - 1):
        p0 = pts[max(i - 1, 0)]; p1 = pts[i]; p2 = pts[i + 1]; p3 = pts[min(i + 2, len(pts) - 1)]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        d += f" C{c1[0]:.1f} {c1[1]:.1f} {c2[0]:.1f} {c2[1]:.1f} {p2[0]:.1f} {p2[1]:.1f}"
    return d


def circle():
    # 不闭合的椭圆：从左上起笔绕一圈多一点，收笔时向外甩出，像随手一圈
    cx, cy, rx, ry = 200, 130, 178, 108
    pts, n, t0, sweep = [], 26, math.radians(205), math.radians(392)
    for k in range(n + 1):
        t = t0 + sweep * k / n
        grow = 1 + 0.07 * k / n + 0.025 * math.sin(3 * t + 0.6)
        pts.append((cx + rx * grow * math.cos(t), cy + ry * grow * math.sin(t) * (1 - 0.06 * math.cos(t))))
    return "0 0 400 260", smooth(pts)


def underline():
    pts = [(4, 8), (10, 17), (24, 16)] + [(24 + 274 * k / 6, 14 - 5 * math.sin(k / 6 * math.pi) + random.uniform(-1, 1)) for k in range(1, 7)]
    return "0 0 302 24", smooth(pts)


def jot(n=6, x0=0, y0=0, x1=0, y1=0, wob=1.2):
    return [(x0 + (x1 - x0) * k / n + random.uniform(-wob, wob), y0 + (y1 - y0) * k / n + random.uniform(-wob, wob)) for k in range(n + 1)]


if __name__ == "__main__":
    vb, d = circle(); print("circle", vb, d, sep="\n  ")
    vb, d = underline(); print("underline", vb, d, sep="\n  ")
    print("arrow  0 0 90 100\n  " + smooth([(4, 10), (34, 8), (60, 24), (70, 52), (64, 90)]) + " M50 76 L64 92 L78 74")
    print("tick  0 0 80 70\n  " + smooth([(4, 38), (14, 48), (24, 62)]) + " " + smooth([(24, 62), (36, 40), (54, 18), (78, 3)]))
    print("cross 0 0 80 72\n  " + smooth(jot(5, 10, 8, 70, 64)) + " " + smooth(jot(5, 70, 10, 12, 66)))
    print("burst 0 0 40 40\n  M8 16 L4 4 M18 12 L24 2 M24 22 L36 16")
    print("hook  0 0 40 40\n  " + smooth([(34, 34), (20, 30), (10, 20), (7, 6)]) + " M2 15 L7 4 L16 12")
