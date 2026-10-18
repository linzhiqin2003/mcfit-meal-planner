"""发布前的资源版本号（scripts/stamp_site_assets.py）：每个本地链接都带上与文件内容一致的版本号，可重复运行，引用了不存在的文件就报错。"""
import hashlib
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import stamp_site_assets as sa  # noqa: E402


def h(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:10]


class StampSiteAssetsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.site = Path(self.tmp.name) / "site"
        shutil.copytree(ROOT / "site", self.site, ignore=shutil.ignore_patterns("src-img"))

    def tearDown(self):
        self.tmp.cleanup()

    def test_every_local_link_gets_content_version(self):
        sa.stamp(self.site)
        html = (self.site / "index.html").read_text(encoding="utf-8")
        links = re.findall(r'\b(?:src|href)="(assets/[^"]+)"', html)
        self.assertTrue(any(l.startswith("assets/js/home.js") for l in links))
        for link in links:
            path, _, ver = link.partition("?v=")
            self.assertEqual(ver, h(self.site / path), link)

    def test_css_font_url_versioned_before_css_hash(self):
        sa.stamp(self.site)
        css = (self.site / "assets/css/site.css").read_text(encoding="utf-8")
        font = self.site / "assets/fonts/noto-sans-sc-900-subset.woff2"
        self.assertIn(f"url(../fonts/noto-sans-sc-900-subset.woff2?v={h(font)})", css)
        self.assertIn("url(%23n)", css)    # data: URI 里的 SVG 滤镜引用原样保留
        html = (self.site / "index.html").read_text(encoding="utf-8")
        self.assertIn(f'href="assets/css/site.css?v={h(self.site / "assets/css/site.css")}"', html)

    def test_idempotent(self):
        sa.stamp(self.site)
        first = (self.site / "index.html").read_text(encoding="utf-8"), (self.site / "assets/css/site.css").read_text(encoding="utf-8")
        sa.stamp(self.site)
        second = (self.site / "index.html").read_text(encoding="utf-8"), (self.site / "assets/css/site.css").read_text(encoding="utf-8")
        self.assertEqual(first, second)

    def test_missing_file_is_an_error(self):
        html = self.site / "index.html"
        html.write_text(html.read_text(encoding="utf-8").replace("assets/js/home.js", "assets/js/nope.js"), encoding="utf-8")
        with self.assertRaises(FileNotFoundError):
            sa.stamp(self.site)


if __name__ == "__main__":
    unittest.main()
