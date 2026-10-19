"""「装」页三组动作（docs/mockups/install-steps 的 B 版，用户 10-19 选定）：第二组贴的 MCP 配置要和仓库里的示例一致，
只把 ${MCD_MCP_TOKEN} 换成「你的 Token」（WorkBuddy 不展开环境变量）；第三组的其他说法都在。"""
import html
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"


class InstallStepsTest(unittest.TestCase):
    def setUp(self):
        self.html = (SITE / "index.html").read_text(encoding="utf-8")

    def test_mcp_config_matches_example(self):
        m = re.search(r'<div class="code cfg"[^>]*>\s*<pre>(.*?)</pre>', self.html, re.S)
        self.assertIsNotNone(m, "第二组要有 MCP 配置块")
        shown = json.loads(html.unescape(m.group(1)))
        example = json.loads((ROOT / "mcp-config.example.json").read_text(encoding="utf-8"))
        example["mcpServers"]["mcd-mcp"]["headers"]["Authorization"] = "Bearer 你的 Token"
        self.assertEqual(shown, example)

    def test_config_block_has_copy_button(self):
        block = re.search(r'<div class="code cfg".*?</div>', self.html, re.S).group(0)
        self.assertIn('class="copy"', block)
        js = (SITE / "assets/js/app.js").read_text(encoding="utf-8")
        self.assertIn('querySelector("pre")', js)          # 配置块按 pre 原样复制，不按 .ln 拼

    def test_more_prompts(self):
        items = re.search(r'<ul class="ins-more">(.*?)</ul>', self.html, re.S)
        self.assertIsNotNone(items)
        self.assertEqual(len(re.findall(r"<li>「[^」]+」</li>", items.group(1))), 3)


if __name__ == "__main__":
    unittest.main()
