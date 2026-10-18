"""本地预览服务器（scripts/serve_site.py）：每个响应带 no-cache；支持 Range，视频才能跳到没下载的位置。"""
import functools
import sys
import tempfile
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import serve_site  # noqa: E402


class ServeSiteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.data = bytes(range(256)) * 40          # 10240 字节
        (Path(cls.tmp.name) / "v.mp4").write_bytes(cls.data)
        handler = functools.partial(serve_site.NoCacheHandler, directory=cls.tmp.name)
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        cls.base = f"http://127.0.0.1:{cls.httpd.server_address[1]}/v.mp4"
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown(); cls.httpd.server_close(); cls.tmp.cleanup()

    def get(self, rng=None):
        req = urllib.request.Request(self.base, headers={"Range": rng} if rng else {})
        with urllib.request.urlopen(req) as r:
            return r.status, dict(r.headers), r.read()

    def test_full_response_has_no_cache_and_accept_ranges(self):
        status, h, body = self.get()
        self.assertEqual(status, 200)
        self.assertEqual(h["Cache-Control"], "no-cache")
        self.assertEqual(h["Accept-Ranges"], "bytes")
        self.assertEqual(body, self.data)

    def test_range_returns_206_slice(self):
        status, h, body = self.get("bytes=5000-5099")
        self.assertEqual(status, 206)
        self.assertEqual(h["Content-Range"], f"bytes 5000-5099/{len(self.data)}")
        self.assertEqual(body, self.data[5000:5100])

    def test_open_ended_and_suffix_ranges(self):
        self.assertEqual(self.get("bytes=10000-")[2], self.data[10000:])
        self.assertEqual(self.get("bytes=-16")[2], self.data[-16:])

    def test_unsatisfiable_range(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self.get(f"bytes={len(self.data) + 10}-")
        self.assertEqual(cm.exception.code, 416)


if __name__ == "__main__":
    unittest.main()
