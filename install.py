"""把麦麦健身餐规划师 Skill 安装到 AI 客户端的技能目录（Windows、macOS、Linux 通用）。

    python3 install.py                      # 自动装进本机已有的 WorkBuddy 和 Claude Code
    python3 install.py --target workbuddy   # → ~/.workbuddy/skills/mcfit-meal-planner
    python3 install.py --target claude      # → ~/.claude/skills/mcfit-meal-planner
    python3 install.py --target ./dist      # 任意目录，例如打包发布

Windows 上把 python3 换成 py（或 python）。

安装内容：SKILL.md 与 references（给智能体读）、scripts/gym.py（入口）、
lib/mcdstrip（计算代码，纯 Python 标准库）、data（官方营养表快照、配方、配料参考值、晚餐和早餐两份门店快照）。
"""
import argparse
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SKILL = ROOT / "skill" / "mcfit-meal-planner"
sys.path.insert(0, str(ROOT / "src"))
from mcdstrip.mcp import token_setup_hint  # noqa: E402

# 客户端名 → (显示名, 配置目录)；技能装在配置目录下的 skills/
CLIENTS = {"workbuddy": ("WorkBuddy", ".workbuddy"), "claude": ("Claude Code", ".claude")}
# 运行要用的全部数据：配方、参考值、配料名、可去配料映射、官方营养表，外加一家门店的晚餐和早餐快照：
# 无 Token 时演示用；gym.py eat 也从这两份菜单查可去的配料（麦满分只在早餐菜单上）
DATA_DIRS = ["data/reference", "data/fixtures/stores/1450441/2026-10-16T1900", "data/fixtures/stores/1450441/2026-10-17T0730"]
DATA_FILES = ["data/fixtures/nutrition_raw.txt"]
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc")
# 改名前的安装目录（2026-10-18 前叫 maimen-gym）：不删的话客户端里会出现两个一样的技能
OLD_NAMES = ["maimen-gym"]


def is_our_skill(d: Path) -> bool:
    """只删本 Skill 装出来的目录：有入口脚本和计算代码，避免误删用户自己的同名目录。"""
    return (d / "scripts" / "gym.py").is_file() and (d / "lib" / "mcdstrip").is_dir()


def remove_old(skills_dir: Path) -> list[Path]:
    removed = []
    for name in OLD_NAMES:
        old = skills_dir / name
        if old.is_dir() and is_our_skill(old):
            shutil.rmtree(old)
            removed.append(old)
    return removed


def install(skills_dir: Path) -> Path:
    dest = skills_dir / SKILL.name
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(SKILL, dest, ignore=IGNORE)
    shutil.copytree(ROOT / "src" / "mcdstrip", dest / "lib" / "mcdstrip", ignore=IGNORE)
    for rel in DATA_DIRS:
        shutil.copytree(ROOT / rel, dest / rel, ignore=IGNORE)
    for rel in DATA_FILES:
        (dest / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / rel, dest / rel)
    return dest


def main() -> int:
    # 中文 Windows 的控制台和管道默认是 GBK，编不进 ᗰ：统一输出 UTF-8
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="安装麦麦健身餐规划师 Skill")
    ap.add_argument("--target", help="workbuddy、claude，或任意目录；不填时装进本机已有的客户端")
    a = ap.parse_args()
    home = Path.home()
    if a.target in CLIENTS:
        targets = [(CLIENTS[a.target][0], home / CLIENTS[a.target][1] / "skills")]
    elif a.target:
        targets = [(None, Path(a.target).expanduser())]
    else:
        targets = [(name, home / d / "skills") for name, d in CLIENTS.values() if (home / d).is_dir()]
        if not targets:
            print("没找到 WorkBuddy 或 Claude Code：请先安装并打开一次客户端，"
                  "或用 --target workbuddy / --target claude 指定。", file=sys.stderr)
            return 1
    for name, skills_dir in targets:
        dest = install(skills_dir)
        print(f"已安装到 {dest}" + (f"（{name}）" if name else ""))
        for old in remove_old(skills_dir):
            print(f"已删除改名前的旧版本 {old}")

    print("\n接下来：")
    print("1. 在 open.mcd.cn/mcp 申请麦当劳 MCP Token。")
    print("2. 在客户端里连上麦当劳 MCP，步骤见 README「连接麦当劳 MCP」。")
    if os.environ.get("MCD_MCP_TOKEN"):
        print("3. 已检测到环境变量 MCD_MCP_TOKEN，脚本可以直接取菜单和核价。")
    else:
        print(f"3. 设置环境变量 MCD_MCP_TOKEN（脚本取菜单、核价时用）：{token_setup_hint()}。")
    print("然后对智能体说：「今晚 500 大卡以内，蛋白质 30 克，人民广场附近」。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
