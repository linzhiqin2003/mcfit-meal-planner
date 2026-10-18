"""把项目主页发布到自己的服务器：取 site/ 里入库的文件放进临时目录、加内容版本号（和 GitHub Pages 工作流一样），再 rsync 过去。

    python3 scripts/deploy_site.py myserver:/var/www/mcd.lzqqq.org --url https://mcd.lzqqq.org
    python3 scripts/deploy_site.py ... --ssh "ssh -B en0"   # 本机开着 Clash TUN 时 SSH 会卡在 banner exchange，绑物理网卡直连
    python3 scripts/deploy_site.py ... --dry-run            # 只列出会传哪些文件

- 只发布 git 跟踪的站点文件（src-img/ 出图原稿、.gitignore 不传），site/ 有未提交的改动时拒绝发布，保证线上和仓库一致；
  确实要先发再提交时加 --allow-dirty。
- rsync 带 --delete：服务器上多出来的旧文件会删掉，目标目录只放这个站点。
- 给了 --url 时，发布后取线上首页，和本地加过版本号的 index.html 逐字节比对。
- 服务器的 nginx 配置在 deploy/nginx/mcd.lzqqq.org.conf。
"""
from __future__ import annotations

import argparse
import logging
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import stamp_site_assets  # noqa: E402

log = logging.getLogger("deploy-site")
CF_BEACON = re.compile(rb'<script[^>]*static\.cloudflareinsights\.com[^>]*></script>\r?\n?')


def site_files() -> list[str]:
    """site/ 下 git 跟踪的文件（相对 site/ 的路径），点文件除外"""
    out = subprocess.run(["git", "ls-files", "-z", "site"], cwd=ROOT, capture_output=True, check=True).stdout
    rels = [p[len("site/"):] for p in out.decode("utf-8").split("\0") if p]
    return sorted(r for r in rels if not any(part.startswith(".") for part in r.split("/")))


def dirty() -> list[str]:
    out = subprocess.run(["git", "status", "--porcelain", "--", "site"], cwd=ROOT, capture_output=True, check=True,
                         encoding="utf-8").stdout
    return [line for line in out.splitlines() if line.strip()]


def prepare(dest: Path) -> dict[str, int]:
    """把要发布的文件复制到 dest 并加版本号；目录 755、文件 644，nginx 用户才读得到"""
    files = site_files()
    for rel in files:
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / "site" / rel, target)
    counts = stamp_site_assets.stamp(dest)
    for d, _, names in os.walk(dest):
        os.chmod(d, 0o755)
        for n in names:
            os.chmod(os.path.join(d, n), 0o644)
    size = sum(f.stat().st_size for f in dest.rglob("*") if f.is_file())
    log.info("待发布 %d 个文件，%.1f MB；加版本号 %s", len(files), size / 1e6, counts)
    return {"files": len(files), "bytes": size}


def rsync(src: Path, target: str, ssh: str, dry_run: bool) -> None:
    cmd = ["rsync", "-az", "--delete", "-e", ssh] + (["-n", "-v"] if dry_run else []) + [f"{src}/", target.rstrip("/") + "/"]
    log.info("运行：%s", " ".join(shlex.quote(c) for c in cmd))
    subprocess.run(cmd, check=True)


def verify(src: Path, url: str) -> None:
    req = urllib.request.Request(url.rstrip("/") + "/", headers={"Cache-Control": "no-cache", "User-Agent": "deploy-site"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        online = resp.read()
    local = (src / "index.html").read_bytes()
    # Cloudflare Web Analytics 会往页面里插一行统计脚本（域名上的设置，不是部署问题），比对前去掉
    online, injected = CF_BEACON.subn(b"", online)
    if injected:
        log.info("线上页面带 Cloudflare 统计脚本（比对时已去掉）")
    if online != local:
        raise SystemExit(f"线上首页和本次发布的不一致（线上 {len(online)} 字节，本地 {len(local)} 字节），检查缓存或目标目录")
    log.info("线上首页与本次发布一致：%s", url)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("target", help="rsync 目标，例如 myserver:/var/www/mcd.lzqqq.org")
    ap.add_argument("--ssh", default="ssh", help="rsync 用的 ssh 命令，默认 ssh")
    ap.add_argument("--url", help="站点地址，给了就在发布后核对线上首页")
    ap.add_argument("--dry-run", action="store_true", help="只列出会传的文件，不改服务器")
    ap.add_argument("--allow-dirty", action="store_true", help="site/ 有未提交改动时也发布")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

    changes = dirty()
    if changes and not args.allow_dirty:
        raise SystemExit("site/ 有未提交的改动，先提交再发布（或加 --allow-dirty）：\n" + "\n".join(changes))
    with tempfile.TemporaryDirectory(prefix="mcd-site-") as tmp:
        out = Path(tmp) / "site"
        out.mkdir()
        prepare(out)
        rsync(out, args.target, args.ssh, args.dry_run)
        if args.url and not args.dry_run:
            verify(out, args.url)


if __name__ == "__main__":
    main()
