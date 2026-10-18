"""本地预览项目主页：和 `python3 -m http.server` 一样，但每个响应都带 Cache-Control: no-cache，并支持 Range 请求。

    python3 scripts/serve_site.py [端口，默认 8765]

为什么不用 http.server：它只发 Last-Modified、不发缓存控制头，浏览器会按「距上次修改时间的 10%」自行缓存，
一个三小时没改的 home.js 会被直接从缓存读十几分钟。改了 HTML/CSS 却还在用旧 JS 时，页面就会缺东西
（2026-10-16 首页红圆和箭头「没出来」就是这个原因）。no-cache 让浏览器每次都回来问，文件没变时服务器回 304，几乎不花时间。

Range：http.server 忽略 Range、永远返回整个文件（200），浏览器就没法跳到视频还没下载的位置——「装」页点「0:22」
教程停在原地（2026-10-16）。GitHub Pages 支持 Range（回 206），这里补上，让本地预览和线上一致。
"""
from __future__ import annotations

import functools
import logging
import os
import re
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SITE = Path(__file__).resolve().parents[1] / "site"
log = logging.getLogger("serve-site")


RANGE = re.compile(r"bytes=(\d*)-(\d*)$")


class NoCacheHandler(SimpleHTTPRequestHandler):
    _remaining: int | None = None

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Accept-Ranges", "bytes")
        super().end_headers()

    def send_head(self):
        """有 Range 头且请求的是普通文件时回 206 和对应的一段；其他情况交给父类"""
        self._remaining = None
        m = RANGE.match(self.headers.get("Range", "").strip())
        path = self.translate_path(self.path)
        if not m or not os.path.isfile(path):
            return super().send_head()
        size = os.path.getsize(path)
        if m[1]:
            start, end = int(m[1]), int(m[2]) if m[2] else size - 1
        elif m[2]:                                   # bytes=-N：最后 N 个字节
            start, end = max(0, size - int(m[2])), size - 1
        else:
            return super().send_head()
        end = min(end, size - 1)
        if start > end:
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{size}")
            self.end_headers()
            return None
        f = open(path, "rb")
        f.seek(start)
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(end - start + 1))
        self.end_headers()
        self._remaining = end - start + 1
        return f

    def copyfile(self, source, outputfile) -> None:
        if self._remaining is None:
            return super().copyfile(source, outputfile)
        left = self._remaining
        while left > 0:
            chunk = source.read(min(64 * 1024, left))
            if not chunk:
                break
            outputfile.write(chunk)
            left -= len(chunk)

    def log_message(self, fmt: str, *args) -> None:   # 走 logging，便于和其他脚本的日志统一
        log.debug("%s %s", self.address_string(), fmt % args)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    handler = functools.partial(NoCacheHandler, directory=str(SITE))
    with ThreadingHTTPServer(("127.0.0.1", port), handler) as httpd:
        log.info("预览 %s → http://localhost:%d（不缓存）", SITE, port)
        httpd.serve_forever()


if __name__ == "__main__":
    main()
