"""推送前自查：要发布的文件里不能有本机绝对路径和真实 Token。

用法：python3 scripts/check_publish.py            # 已跟踪 + 未忽略的新文件（推送前跑）
      python3 scripts/check_publish.py --tracked  # 只查已跟踪的文件（测试用）

发现问题时逐条列出「文件:行号」并以 1 退出；二进制文件跳过。
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# 文档里的占位写法不算：「你的用户名」「<用户名>」「%USERNAME%」「$USER」
_NOT_PLACEHOLDER = r"(?!你的用户名|用户名|<|%|\$)"
# 本机路径：macOS 用户目录、外置卷、临时目录，Windows 用户目录（含 JSON 里转义成双反斜杠的写法、中文用户名）；
# 字符集里排除 [ ]，免得这几行正则源码自己被扫出来
LOCAL_PATH = re.compile(r"/Users/" + _NOT_PLACEHOLDER + r"[^/\s\"'\\<>\[\]]+/"
                        r"|/Volumes/[^/\s\"'\\<>\[\]]+/"
                        r"|/private/(?:tmp|var)/"
                        r"|[A-Za-z]:\\{1,2}Users\\{1,2}" + _NOT_PLACEHOLDER + r"[^\\/\s\"'<>]+")
# 真实 Token：Bearer 后面，或 MCD_MCP_TOKEN 的各种赋值写法（=、setx、JSON、SetEnvironmentVariable）后面跟一串不是占位符的值
TOKEN = re.compile(r"Bearer\s+(?!\$|YOUR_|<)[A-Za-z0-9._~+/=-]{20,}"
                   r"|MCD_MCP_TOKEN['\"]?\s*[=:,\s]\s*['\"]?(?!\.\.\.|\$|<|你的)[A-Za-z0-9._~+/=-]{20,}")


def publish_files(tracked_only: bool) -> list[str]:
    cmd = ["git", "ls-files", "-z", "--cached"] + ([] if tracked_only else ["--others", "--exclude-standard"])
    out = subprocess.run(cmd, cwd=ROOT, capture_output=True, check=True).stdout
    return sorted({p for p in out.decode("utf-8").split("\0") if p and (ROOT / p).is_file()})


def scan(rel: str) -> list[str]:
    try:
        text = (ROOT / rel).read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []
    exact = os.environ.get("MCD_MCP_TOKEN", "")      # 设置了 Token 时，再查一遍它的原文
    hits = []
    for n, line in enumerate(text.splitlines(), 1):
        for kind, pat in (("本机路径", LOCAL_PATH), ("疑似 Token", TOKEN)):
            if pat.search(line):
                hits.append(f"{rel}:{n}  {kind}")
        if len(exact) >= 8 and exact in line:
            hits.append(f"{rel}:{n}  Token 原文")
    return hits


def main() -> int:
    ap = argparse.ArgumentParser(description="推送前自查本机路径和 Token")
    ap.add_argument("--tracked", action="store_true", help="只查已跟踪的文件")
    files = publish_files(ap.parse_args().tracked)
    hits = [h for f in files for h in scan(f)]
    for h in hits:
        print(h)
    print(f"查了 {len(files)} 个文件，{'发现 ' + str(len(hits)) + ' 处问题' if hits else '没有问题'}", file=sys.stderr)
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
