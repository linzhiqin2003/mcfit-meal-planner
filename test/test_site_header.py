"""页眉和页脚的品牌（10-19 用户要求放回 Gyᗰ 标志）：标志在名字前面；放回标志后页眉在 800 以下排两行、410 以下 Star 按钮只留短字，都不横向溢出。"""
import re
import unittest
from pathlib import Path

from test_site_promo import media_rule

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"


class BrandTest(unittest.TestCase):
    def setUp(self):
        self.html = (SITE / "index.html").read_text(encoding="utf-8")
        self.css = (SITE / "assets/css/site.css").read_text(encoding="utf-8")

    def test_logo_before_name_in_header_and_footer(self):
        brands = re.findall(r'<a class="brand"[^>]*>(.*?)</a>', self.html, re.S)
        self.assertEqual(len(brands), 2)                  # 页眉、页脚各一个
        for b in brands:
            self.assertRegex(b, r'<span class="gy">Gy<span class="m"><svg aria-hidden="true"><use href="#g-m"/></svg></span></span>'
                                r'\s*<span class="cn">麦麦健身餐规划师</span>')
        self.assertIn('<symbol id="g-m"', self.html)

    def test_header_wraps_before_overflow(self):
        tablet = media_rule(self.css, 800)
        self.assertRegex(tablet, r"\.top \.wrap\{[^}]*flex-wrap:wrap")
        self.assertRegex(tablet, r"\.nav\{[^}]*order:3;width:100%")
        self.assertRegex(tablet, r"\.home\{min-height:calc\(100svh - 109px\)\}")   # 两行页眉更高，首屏跟着减
        self.assertRegex(media_rule(self.css, 410), r"\.top \.btn-long\{display:none\}")


if __name__ == "__main__":
    unittest.main()
