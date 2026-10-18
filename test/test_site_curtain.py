"""页脚小人谢幕：index.html 里每个小人牌子的位置（--sx/--sy/--sw/--sh/--ar）和 scripts/build_site_curtain.py 写的 bow.json 一致，图片都在。

构建脚本要 numpy、scipy 和 videos/ 下的切图脚本（videos/ 不入库），干净克隆和 CI 里没有：
一致性检查只读 site/ 下的文件，照常跑；牌子框算法的测试跳过。
"""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
try:
    import numpy as np
    import build_site_curtain as bc  # noqa: E402
except ImportError:
    np = bc = None


class SiteCurtainTest(unittest.TestCase):
    def test_html_sign_boxes_match_bow_json(self):
        meta = json.loads((ROOT / "site/assets/img/bow.json").read_text(encoding="utf-8"))
        html = (ROOT / "site/index.html").read_text(encoding="utf-8")
        found = re.findall(r'<a class="bow"[^>]*style="--ar:([\d.]+);--sx:([\d.]+)%;--sy:([\d.]+)%;--sw:([\d.]+)%;--sh:([\d.]+)%"><img src="assets/img/bow-(\w+)\.webp"', html)
        # bow.json 按 CAST 的顺序写，页面从左到右的顺序要和它一致
        self.assertEqual([f[5] for f in found], list(meta))
        if bc is not None:
            self.assertEqual(list(meta), bc.CAST)
        for ar, sx, sy, sw, sh, name in found:
            m = meta[name]
            self.assertAlmostEqual(float(ar), m["aspect"], places=4, msg=name)
            for k, v in zip("xywh", (sx, sy, sw, sh)):
                self.assertAlmostEqual(float(v), m["sign"][k], places=2, msg=f"{name} sign.{k}，请重新运行 build_site_curtain.py 并同步 index.html")
            self.assertTrue((ROOT / f"site/assets/img/bow-{name}.webp").is_file())

    @unittest.skipIf(bc is None, "没有 numpy / scipy 或 videos/ 下的切图脚本")
    def test_sign_box_ignores_white_sneakers(self):
        # 合成一张图：中间一块白牌子，底下一双白鞋（只占一小段宽度），牌子框只取中间那块
        img = np.zeros((200, 100, 4), np.uint8)
        img[..., 3] = 255
        img[..., :3] = (200, 120, 60)
        img[80:110, 10:90, :3] = 255
        img[180:195, 20:35, :3] = 250
        img[180:195, 60:75, :3] = 250
        self.assertEqual(bc.sign_box(img), (10, 80, 90, 110))


if __name__ == "__main__":
    unittest.main()
