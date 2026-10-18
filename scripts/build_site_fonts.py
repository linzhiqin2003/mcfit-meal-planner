"""给项目主页切一份极小的标题粗体字：Noto Sans SC（OFL，可变字体）固定到 900 字重，只留「拆」页标题和小节标题用到的字。
    uv run --with fonttools --with brotli python scripts/build_site_fonts.py
输入：videos/gym-promo/assets/fonts/src/NotoSansSC.ttf（宣传片用的同一份源字体）
输出：site/assets/fonts/noto-sans-sc-900-subset.woff2
加新标题字时把字加进 TEXT 重新跑一遍；没收录的字会回落到系统黑体。"""
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "videos/gym-promo/assets/fonts/src/NotoSansSC.ttf"
OUT = ROOT / "site/assets/fonts/noto-sans-sc-900-subset.woff2"
# 「·」不收：粗体里的间隔号是全角宽，标题里会空出一大块，留给系统黑体的窄间隔号
TEXT = "拆只吃馅怎么算吃法省钱对比练生成训计划选方案装到三组动作开口说一句接麦当劳"   # 「装」：导航单字；后面是「装」页标题、小节和三组动作的标题


def main() -> None:
    font = instancer.instantiateVariableFont(TTFont(SRC), {"wght": 900})
    opts = subset.Options()
    opts.flavor = "woff2"
    opts.layout_features = ["*"]
    opts.name_IDs = ["*"]          # 保留版权与 OFL 许可信息
    sub = subset.Subsetter(opts)
    sub.populate(text=TEXT)
    sub.subset(font)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    font.flavor = "woff2"
    font.save(OUT)
    print(f"{OUT.relative_to(ROOT)}: {OUT.stat().st_size} 字节，{len(set(TEXT))} 个字")


if __name__ == "__main__":
    main()
