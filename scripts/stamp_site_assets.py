"""发布前给项目主页的本地资源链接加内容版本号：assets/... → assets/...?v=<内容哈希前 10 位>。

    python3 scripts/stamp_site_assets.py [站点目录，默认 site]

GitHub Pages 给静态文件 10 分钟缓存。只改了 HTML 和 JS 中的一个时，访客可能拿到「新页面 + 旧脚本」，
页面就会缺东西（2026-10-16 本地预览里首页红圆和箭头「没出来」就是旧 home.js 配新页面）。
内容一变链接就变，浏览器自然去取新文件；内容没变链接不变，缓存照常命中。

只改站点目录里的文件，就地写回：.github/workflows/pages.yml 在上传前对 CI 里的工作副本运行，仓库里的 index.html 保持干净。
处理范围：index.html 里 src/href 指向 assets/ 的链接，以及 assets/css/*.css 里 url() 指向的本地文件（字体等）。
先给 CSS 里的 url() 加版本号，再算 CSS 自己的哈希，这样只换了字体时 CSS 的链接也会变。可以重复运行，结果不变。
"""
from __future__ import annotations

import hashlib
import logging
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
log = logging.getLogger("stamp-assets")
ATTR = re.compile(r'(?P<attr>\b(?:src|href))="(?P<path>assets/[^"?#]+)(?:\?v=[0-9a-f]*)?"')
# 只认带文件扩展名的相对路径：data: URI 里面也会出现 url(%23n) 这类 SVG 滤镜引用，不能当成文件
CSS_URL = re.compile(r'url\((?P<q>["\']?)(?P<path>(?!data:|https?:|/)[^"\')?#%]+\.(?:woff2?|ttf|otf|png|webp|jpe?g|gif|svg))(?:\?v=[0-9a-f]*)?(?P=q)\)')


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:10]


def stamp_css(css: Path) -> int:
    text = css.read_text(encoding="utf-8")
    n = 0

    def sub(m: re.Match) -> str:
        nonlocal n
        target = (css.parent / m["path"]).resolve()
        if not target.is_file():
            raise FileNotFoundError(f"{css.name} 引用的文件不存在：{m['path']}")
        n += 1
        return f'url({m["q"]}{m["path"]}?v={digest(target)}{m["q"]})'

    css.write_text(CSS_URL.sub(sub, text), encoding="utf-8")
    return n


def stamp_html(html: Path, site: Path) -> int:
    text = html.read_text(encoding="utf-8")
    n = 0

    def sub(m: re.Match) -> str:
        nonlocal n
        target = site / m["path"]
        if not target.is_file():
            raise FileNotFoundError(f"{html.name} 引用的文件不存在：{m['path']}")
        n += 1
        return f'{m["attr"]}="{m["path"]}?v={digest(target)}"'

    html.write_text(ATTR.sub(sub, text), encoding="utf-8")
    return n


def stamp(site: Path) -> dict[str, int]:
    counts = {}
    for css in sorted((site / "assets/css").glob("*.css")):
        counts[css.relative_to(site).as_posix()] = stamp_css(css)
    counts["index.html"] = stamp_html(site / "index.html", site)
    return counts


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    site = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "site"
    for name, n in stamp(site).items():
        log.info("%s：%d 个链接加了版本号", name, n)


if __name__ == "__main__":
    main()
