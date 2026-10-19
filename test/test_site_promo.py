"""首页宣传片入口（mockup B 版，用户 10-19 选定）：入口卡和弹窗对得上、视频和封面文件都在、手机「装」页不放宣传片。"""
import re
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"


class Tags(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


def tags() -> list:
    p = Tags()
    p.feed((SITE / "index.html").read_text(encoding="utf-8"))
    return p.tags


def media_rule(css: str, width: int) -> str:
    """把所有 @media (max-width:<width>px) 块的内容拼起来（块里不再嵌套花括号以外的结构）。"""
    out, i = [], 0
    head = f"@media (max-width:{width}px){{"
    while (i := css.find(head, i)) >= 0:
        j, depth = i + len(head), 1
        while depth:
            depth += {"{": 1, "}": -1}.get(css[j], 0)
            j += 1
        out.append(css[i + len(head):j - 1])
        i = j
    return "\n".join(out)


class HomePromoTest(unittest.TestCase):
    def setUp(self):
        self.tags = tags()
        self.css = (SITE / "assets/css/site.css").read_text(encoding="utf-8")

    def find(self, pred):
        return [a for t, a in self.tags if pred(t, a)]

    def test_entry_opens_existing_dialog(self):
        entry = self.find(lambda t, a: t == "button" and "promo-entry" in a.get("class", ""))
        self.assertEqual(len(entry), 1)
        self.assertEqual(entry[0].get("aria-haspopup"), "dialog")
        dlg = self.find(lambda t, a: t == "dialog" and a.get("id") == entry[0].get("aria-controls"))
        self.assertEqual(len(dlg), 1, "入口卡的 aria-controls 要指向弹窗")

    def test_dialog_video_and_poster_exist(self):
        video = self.find(lambda t, a: t == "video" and a.get("id") == "homePromo")
        self.assertEqual(len(video), 1)
        for attr in ("src", "poster"):
            self.assertTrue((SITE / video[0][attr]).is_file(), video[0][attr])
        self.assertIn("playsinline", video[0])          # iOS 上不自动全屏
        self.assertIn("controls", video[0])
        thumb = self.find(lambda t, a: t == "img" and a.get("src", "").endswith("promo-poster.webp"))
        self.assertTrue(thumb)

    def test_close_button_and_icon(self):
        x = self.find(lambda t, a: t == "button" and "promo-x" in a.get("class", ""))
        self.assertEqual(len(x), 1)
        self.assertIn("autofocus", x[0])                  # 打开时焦点落在关闭键，不在视频上
        self.assertTrue(self.find(lambda t, a: t == "symbol" and a.get("id") == "i-x"))

    def test_script_loaded(self):
        srcs = [a.get("src") for t, a in self.tags if t == "script" and a.get("src")]
        self.assertIn("assets/js/promo.js", srcs)
        self.assertTrue((SITE / "assets/js/promo.js").is_file())

    def test_short_window_fallbacks(self):
        # 电脑上窗口矮时 home.js 依次换成胶囊（promo-mini）、排到副标题下面（promo-flow），两档 CSS 都要在
        js = (SITE / "assets/js/home.js").read_text(encoding="utf-8")
        for cls in ("promo-mini", "promo-flow"):
            self.assertIn(f'"{cls}"', js)
            self.assertRegex(self.css, rf"\.home\.{cls} \.promo-entry\{{")
        self.assertRegex(self.css, r"\.home\.promo-flow \.promo-entry\{[^}]*position:relative")

    def test_install_page_hides_promo_on_phone_only(self):
        phone = media_rule(self.css, 640)
        self.assertRegex(phone, r"\.ins-side\{display:none\}")
        # 电脑上「装」页的宣传片还在：媒体查询外没有隐藏它
        outside = re.sub(r"@media[^{]*\{(?:[^{}]*\{[^{}]*\})*[^{}]*\}", "", self.css)
        self.assertNotRegex(outside, r"\.ins-side\{[^}]*display:none")


if __name__ == "__main__":
    unittest.main()
