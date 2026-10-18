"""把 GPT Image mockup 拼成对比板：overview.png（四张整页并排）与 board-<方向>.png（整页 + 三帧分镜 + 说明）。
python3 -I 不可用时用：uv run --with pillow python board.py"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
FONT = "/System/Library/Fonts/Hiragino Sans GB.ttc"
BG, INK, MUTED = "#E6E0D3", "#17150F", "#6B655A"
DIRS = [
    ("s1-stage", "1 · 舞台分解", "汉堡沿中轴炸开，切吃法时各层左右滑走：肉留中间，面包变虚影，吉士只剩轮廓"),
    ("s2-barbell", "2 · 杠铃配重", "每层是一片配重：吃掉的留在杠上，面包上架，吉士落地；翻牌记分板翻到 182"),
    ("s3-poster", "3 · 杂志大字", "429 → 182 做成满幅大字，汉堡层卡在数字之间；滚动时划线、红字滑入"),
    ("s4-flatlay", "4 · 俯拍分拣", "俯拍亚麻台面分三区：盘子、保鲜盒、划掉；各层沿虚线弧飞进各自区域"),
]


def font(size):
    return ImageFont.truetype(FONT, size)


def fit(im, w=None, h=None):
    r = (w / im.width) if w else (h / im.height)
    return im.resize((round(im.width * r), round(im.height * r)), Image.LANCZOS)


def overview():
    pages = [(t, Image.open(HERE / f"{k}.png").convert("RGB")) for k, t, _ in DIRS if (HERE / f"{k}.png").exists()]
    W, gap, top = 620, 40, 90
    ims = [(t, fit(im, w=W)) for t, im in pages]
    H = max(im.height for _, im in ims) + top + 40
    out = Image.new("RGB", (len(ims) * (W + gap) + gap, H), BG)
    d = ImageDraw.Draw(out)
    for i, (t, im) in enumerate(ims):
        x = gap + i * (W + gap)
        d.text((x, 30), t, fill=INK, font=font(34))
        out.paste(im, (x, top))
    out.save(HERE / "overview.png"); print("overview", out.size)


def boards():
    for k, t, note in DIRS:
        pg, mo = HERE / f"{k}.png", HERE / f"{k}-motion.png"
        if not (pg.exists() and mo.exists()):
            continue
        page = fit(Image.open(pg).convert("RGB"), h=1500)
        mot = fit(Image.open(mo).convert("RGB"), w=1500)
        W = 60 + page.width + 50 + mot.width + 60
        H = 130 + max(page.height, mot.height + 200) + 60
        out = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(out)
        d.text((60, 40), t, fill=INK, font=font(44))
        out.paste(page, (60, 130))
        x = 60 + page.width + 50
        d.text((x, 130), "切换吃法：整份吃 → 去吉士 + 只吃馅（三帧分镜）", fill=INK, font=font(30))
        d.text((x, 175), note, fill=MUTED, font=font(24))
        out.paste(mot, (x, 230))
        out.save(HERE / f"board-{k}.png"); print("board", k, out.size)


STYLES = [
    ("t1-editorial", "A · 杂志编辑", "宋体大标题 + 左侧节号栏，文字像杂志排版"),
    ("t2-sport", "B · 运动海报", "超粗窄体、竖排 SPLIT SETS、红条分节、深色比价带"),
    ("t3-swiss", "C · 瑞士网格", "可见 12 栏网格、三行巨型标题、红方块点缀"),
    ("t4-coach", "D · 教练批注", "印刷版面 + 红笔圈注、箭头和手写批注"),
]


def styles():
    W, gap, top = 700, 44, 150
    ims = [(t, n, fit(Image.open(HERE / f"{k}.png").convert("RGB"), w=W)) for k, t, n in STYLES]
    H = max(im.height for *_, im in ims) + top + 44
    out = Image.new("RGB", (len(ims) * (W + gap) + gap, H), BG)
    d = ImageDraw.Draw(out)
    for i, (t, n, im) in enumerate(ims):
        x = gap + i * (W + gap)
        d.text((x, 34), t, fill=INK, font=font(40))
        d.text((x, 92), n, fill=MUTED, font=font(24))
        out.paste(im, (x, top))
    out.save(HERE / "styles.png"); print("styles", out.size)


TRAIN = [
    ("r1-markup", "A · 原排版加批注", "结构不动，换上印章、粗标题和红笔圈注"),
    ("r2-clipboard", "B · 训练单夹板", "训练单变成夹在木板上的一张纸，红笔写在纸上"),
    ("r3-columns", "C · 左右两栏", "左边教练清单（参数、方案），右边大号训练单"),
]


def train():
    W, gap, top = 760, 44, 150
    ims = [(t, n, fit(Image.open(HERE / f"{k}.png").convert("RGB"), w=W)) for k, t, n in TRAIN]
    H = max(im.height for *_, im in ims) + top + 44
    out = Image.new("RGB", (len(ims) * (W + gap) + gap, H), BG)
    d = ImageDraw.Draw(out)
    for i, (t, n, im) in enumerate(ims):
        x = gap + i * (W + gap)
        d.text((x, 34), t, fill=INK, font=font(40))
        d.text((x, 92), n, fill=MUTED, font=font(24))
        out.paste(im, (x, top))
    out.save(HERE / "train.png"); print("train", out.size)


HOME = [
    ("h1-redpen", "1 · 红笔动线", "划掉 Gym、圈住金色 M，红色虚线按 01 → 02 → 03 串起三个入口"),
    ("h2-track", "2 · 跑道", "一条田径跑道 S 形穿过画面，三个入口是沿途的号码站，终点格子旗"),
    ("h3-focus", "3 · 焦点构图", "金色 M 背后一个大红圆，粗箭头从「不如」绕回来，底部数字跑马灯"),
    ("h4-steps", "4 · 球鞋脚印", "小人们走出一串脚印通向各自入口，地上一层体育馆标线"),
]


def home():
    W, gap, top, cap = 1100, 50, 150, 110
    ims = [(t, n, fit(Image.open(HERE / f"{k}.png").convert("RGB"), w=W)) for k, t, n in HOME]
    ih = ims[0][2].height
    out = Image.new("RGB", (2 * W + 3 * gap, 2 * (ih + cap) + gap + 20), BG)
    d = ImageDraw.Draw(out)
    for i, (t, n, im) in enumerate(ims):
        x = gap + (i % 2) * (W + gap); y = 20 + (i // 2) * (ih + cap + gap // 2)
        d.text((x, y + 6), t, fill=INK, font=font(38))
        d.text((x + 330, y + 18), n, fill=MUTED, font=font(24))
        out.paste(im, (x, y + cap - 40))
    out.save(HERE / "home.png"); print("home", out.size)


if __name__ == "__main__":
    import sys
    if sys.argv[1:] == ["home"]:
        home()
    elif sys.argv[1:] == ["train"]:
        train()
    elif sys.argv[1:] == ["styles"]:
        styles()
    else:
        overview(); boards()
