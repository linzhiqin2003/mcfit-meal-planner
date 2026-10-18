"""麦麦健身餐规划师命令行入口（给智能体调用）。

    python scripts/gym.py plan --kcal-max 500 --protein-min 30 --city 上海 --near 人民广场 --format json
    python scripts/gym.py eat 双层吉士汉堡 --format json
    python scripts/gym.py stores --city 上海 --near 人民广场

安装后计算代码在本 Skill 的 lib/ 下；在仓库里直接运行时用仓库的 src/。
"""
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
for cand in (SKILL / "lib", SKILL.parents[1] / "src"):
    if (cand / "mcdstrip").is_dir():
        sys.path.insert(0, str(cand))
        break
else:
    sys.exit("找不到计算代码：请用仓库里的 install.py 安装本 Skill。")

from mcdstrip.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
