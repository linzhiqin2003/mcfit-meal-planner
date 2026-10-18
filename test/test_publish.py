"""要发布的内容里没有本机绝对路径和真实 Token（scripts/check_publish.py）。"""
import importlib.util
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("check_publish", ROOT / "scripts" / "check_publish.py")
cp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cp)


class PatternTest(unittest.TestCase):
    # 样例在运行时拼出来，免得这个测试文件自己被扫出问题
    def test_flags_local_paths(self):
        for s in ("/" + "Users/alice/proj/a.json", "/" + "Users/张三/repo/", "/" + "Volumes/Data/x",
                  "/" + "private/tmp/claude-501/s", "C:" + "\\Users\\bob\\maimen", "C:" + "\\Users\\张三\\repo",
                  '"C:' + '\\\\Users\\\\alice\\\\repo"'):
            self.assertTrue(cp.LOCAL_PATH.search(s), s)

    def test_ignores_placeholders_and_relative_paths(self):
        for s in ("data/fixtures/stores/1450441/details/", "~/.claude/skills/maimen-gym", "%USERPROFILE%\\.claude",
                  "C:" + "\\Users\\你的用户名", "/" + "Users/你的用户名/", "C:" + "\\Users\\%USERNAME%"):
            self.assertFalse(cp.LOCAL_PATH.search(s), s)

    def test_flags_real_tokens_not_placeholders(self):
        real = "a1B2" * 8
        name = "MCD_MCP_" + "TOKEN"
        for s in ("Bearer " + real, name + "=" + real, f'setx {name} "{real}"', f'"{name}": "{real}"',
                  f"[Environment]::SetEnvironmentVariable('{name}', '{real}', 'User')"):
            self.assertTrue(cp.TOKEN.search(s), s)
        for s in ("Bearer ${MCD_MCP_TOKEN}", "Bearer YOUR_MCP_TOKEN", "MCD_MCP_TOKEN=... python gym.py",
                  'setx MCD_MCP_TOKEN "你的Token"', '"Authorization": "Bearer ${MCD_MCP_TOKEN}"',
                  '[Environment]::SetEnvironmentVariable("MCD_MCP_TOKEN", "你的Token", "User")',
                  'env.pop("MCD_MCP_TOKEN", None)', "设置环境变量 MCD_MCP_TOKEN（脚本取菜单时用）"):
            self.assertFalse(cp.TOKEN.search(s), s)


@unittest.skipUnless(shutil.which("git") and (ROOT / ".git").exists(), "不是 git 仓库")
class TrackedFilesTest(unittest.TestCase):
    def test_tracked_files_are_clean(self):
        r = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True)
        files = [p for p in r.stdout.decode("utf-8").split("\0") if p and (ROOT / p).is_file()]
        hits = [h for f in files for h in cp.scan(f)]
        self.assertEqual(hits, [], "\n".join(hits))


if __name__ == "__main__":
    unittest.main()
