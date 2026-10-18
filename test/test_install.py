"""安装后的 Skill 能独立运行：数据齐全、输出 UTF-8、错误提示分得清。用子进程跑，和用户的真实环境一致。"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEMO = "data/fixtures/stores/1450441/2026-10-16T1900"


class InstallTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        home = Path(cls.tmp.name) / "home"
        home.mkdir()
        cls.env = {**os.environ, "HOME": str(home), "USERPROFILE": str(home)}   # 干净的缓存目录（Windows 看 USERPROFILE）
        cls.env.pop("MCD_MCP_TOKEN", None)
        subprocess.run([sys.executable, str(ROOT / "install.py"), "--target", str(Path(cls.tmp.name) / "skills")],
                       check=True, capture_output=True, env=cls.env)
        cls.skill = Path(cls.tmp.name) / "skills" / "maimen-gym"

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_gym(self, *args, **env):
        return subprocess.run([sys.executable, "scripts/gym.py", *args], cwd=self.skill, capture_output=True,
                              env={**self.env, **env}, timeout=600)

    def test_offline_demo_runs_from_installed_copy(self):
        r = self.run_gym("plan", "--kcal-max", "400", "--protein-min", "30", "--offline", DEMO, "--format", "json")
        self.assertEqual(r.returncode, 0, r.stdout.decode("utf-8", "replace") + r.stderr.decode("utf-8", "replace"))
        d = json.loads(r.stdout)
        self.assertTrue(d["ok"])
        self.assertTrue(d["plans"])

    def test_output_is_utf8_even_on_gbk_console(self):
        # 中文 Windows：管道和控制台默认 GBK，ᗰ 和 emoji 编不进去
        r = self.run_gym("plan", "--kcal-max", "500", "--protein-min", "30", "--train", "练腿", "--offline", DEMO,
                         "--style", "gym", "--top", "1", PYTHONIOENCODING="gbk", LC_ALL="zh_CN.GBK", LANG="zh_CN.GBK")
        self.assertEqual(r.returncode, 0, r.stderr.decode("utf-8", "replace"))
        self.assertIn("Go to Gym 不如 Go to ᗰ", r.stdout.decode("utf-8"))

    def test_missing_token_is_explained(self):
        r = self.run_gym("plan", "--kcal-max", "400", "--city", "上海", "--near", "人民广场", "--format", "json")
        self.assertEqual(r.returncode, 3)
        self.assertIn("MCD_MCP_TOKEN", json.loads(r.stdout)["error"])
        s = self.run_gym("stores", "--city", "上海", "--near", "人民广场")
        self.assertIn("MCD_MCP_TOKEN", s.stdout.decode("utf-8"))
        self.assertNotIn("Traceback", s.stderr.decode("utf-8", "replace"))


class AutoTargetTest(unittest.TestCase):
    """不带 --target：只装进本机已有的客户端，一个都没有时说清楚。"""

    def run_install(self, home: Path):
        env = {**os.environ, "HOME": str(home), "USERPROFILE": str(home)}
        env.pop("MCD_MCP_TOKEN", None)
        return subprocess.run([sys.executable, str(ROOT / "install.py")], capture_output=True, env=env, timeout=120)

    def test_installs_into_existing_clients_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / ".claude").mkdir()
            r = self.run_install(home)
            out = r.stdout.decode("utf-8")
            self.assertEqual(r.returncode, 0, out + r.stderr.decode("utf-8", "replace"))
            self.assertTrue((home / ".claude" / "skills" / "maimen-gym" / "SKILL.md").is_file())
            self.assertFalse((home / ".workbuddy").exists())
            self.assertIn("Claude Code", out)
            self.assertIn("MCD_MCP_TOKEN", out)      # 没设 Token 时给出设置方法

    def test_no_client_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = self.run_install(Path(tmp))
            self.assertEqual(r.returncode, 1)
            self.assertIn("--target", r.stderr.decode("utf-8"))


class TokenHintTest(unittest.TestCase):
    def test_hint_matches_platform_and_shell(self):
        import importlib
        from unittest import mock
        sys.path.insert(0, str(ROOT / "src"))
        hint = importlib.import_module("mcdstrip.mcp").token_setup_hint
        self.assertIn("SetEnvironmentVariable(\"MCD_MCP_TOKEN\"", hint("win32"))
        for shell, platform, rc in (("/bin/zsh", "darwin", "~/.zshrc"), ("", "darwin", "~/.zshrc"),
                                    ("/bin/bash", "darwin", "~/.bash_profile"), ("/bin/bash", "linux", "~/.bashrc")):
            with mock.patch.dict(os.environ, {"SHELL": shell}):
                h = hint(platform)
            self.assertIn(rc, h, (shell, platform))
            self.assertIn("新开的终端", h)


if __name__ == "__main__":
    unittest.main()
