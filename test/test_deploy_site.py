"""发布到自己服务器前的准备（scripts/deploy_site.py）：只带入库的站点文件、加好版本号、权限让 nginx 读得到。"""
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import deploy_site as ds  # noqa: E402


class PrepareTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.out = Path(cls.tmp.name) / "site"
        cls.out.mkdir()
        cls.stats = ds.prepare(cls.out)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_only_tracked_files_without_dotfiles_or_sources(self):
        got = sorted(p.relative_to(self.out).as_posix() for p in self.out.rglob("*") if p.is_file())
        self.assertEqual(got, ds.site_files())
        self.assertIn("index.html", got)
        self.assertFalse([p for p in got if p.startswith("src-img/") or "/." in "/" + p])

    def test_index_links_are_stamped(self):
        html = (self.out / "index.html").read_text(encoding="utf-8")
        local = re.findall(r'\b(?:src|href)="(assets/[^"]+)"', html)
        self.assertTrue(local)
        self.assertEqual([u for u in local if "?v=" not in u], [])
        # 仓库里的 index.html 保持不带版本号
        self.assertNotIn("?v=", (ROOT / "site/index.html").read_text(encoding="utf-8"))

    @unittest.skipIf(os.name == "nt", "Windows 没有 Unix 权限位")
    def test_permissions_readable_by_web_server(self):
        self.assertEqual(self.out.stat().st_mode & 0o777, 0o755)
        for p in self.out.rglob("*"):
            self.assertEqual(p.stat().st_mode & 0o777, 0o755 if p.is_dir() else 0o644, p)


if __name__ == "__main__":
    unittest.main()
