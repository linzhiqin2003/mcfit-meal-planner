"""README 里的相对链接和图片都指向仓库里存在的文件，页内锚点对得上标题（GitHub 上裂图、死链很显眼）。"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINK = re.compile(r'\]\(([^)\s]+)\)|\b(?:src|href)="([^"]+)"')


def targets(text: str) -> list[str]:
    text = re.sub(r"```.*?```", "", text, flags=re.S)        # 代码块里的不算
    return [a or b for a, b in LINK.findall(text)]


def slug(heading: str) -> str:
    """GitHub 的标题锚点：转小写，去掉标点（保留连字符），空格换成连字符"""
    s = re.sub(r"[^\w\- ]", "", heading.strip().lower())
    return s.replace(" ", "-")


class ReadmeLinksTest(unittest.TestCase):
    def setUp(self):
        self.text = (ROOT / "README.md").read_text(encoding="utf-8")

    def test_relative_targets_exist(self):
        missing = []
        for t in targets(self.text):
            if re.match(r"[a-z]+:", t) or t.startswith("#"):
                continue
            path = t.split("#", 1)[0]
            if not (ROOT / path).exists():
                missing.append(t)
        self.assertEqual(missing, [])

    def test_anchors_match_headings(self):
        anchors = {slug(h) for h in re.findall(r"^#{1,6} (.+)$", self.text, flags=re.M)}
        bad = [t for t in targets(self.text) if t.startswith("#") and t[1:] not in anchors]
        self.assertEqual(bad, [])

    def test_images_have_alt_text(self):
        for tag in re.findall(r"<img [^>]*>", self.text):
            self.assertRegex(tag, r'alt="[^"]+"', tag)

    def test_detector(self):
        self.assertEqual(targets('![a](x.png) <img src="y.webp"> <a href="#z">\n```\n![b](no.png)\n```'),
                         ["x.png", "y.webp", "#z"])
        self.assertEqual(slug("营养怎么算"), "营养怎么算")
        self.assertEqual(slug("3. 设置环境变量 MCD_MCP_TOKEN"), "3-设置环境变量-mcd_mcp_token")


if __name__ == "__main__":
    unittest.main()
