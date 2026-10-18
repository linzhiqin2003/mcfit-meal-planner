"""入库的 Python 文件里，文本读写都要写明 encoding。

Windows 默认按系统代码页（英文版 cp1252、中文版 GBK）读写，不写 encoding 时一读中文数据文件就会
UnicodeDecodeError。macOS 和 Linux 默认是 UTF-8，本地测试发现不了，以前只有 Windows CI 报错。
这里按语法树检查 Path.read_text / Path.write_text / open(...)：二进制模式（mode 里有 b）不算，
Image.open 这类非文件读写的 open 也不算。
"""
import ast
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _mode(call: ast.Call, builtin: bool):
    for k in call.keywords:
        if k.arg == "mode":
            return k.value
    args = call.args[1:] if builtin else call.args  # open(file, mode) / Path.open(mode)
    return args[0] if args else None


def missing_encoding(source: str) -> list[int]:
    lines = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call) or any(k.arg == "encoding" for k in node.keywords):
            continue
        f = node.func
        if isinstance(f, ast.Attribute) and f.attr in ("read_text", "write_text"):
            lines.append(node.lineno)
        elif (isinstance(f, ast.Name) and f.id == "open") or (
                isinstance(f, ast.Attribute) and f.attr == "open"
                and not (isinstance(f.value, ast.Name) and f.value.id in ("Image", "webbrowser", "opener", "os"))):
            mode = _mode(node, isinstance(f, ast.Name))
            if isinstance(mode, ast.Constant) and "b" in str(mode.value):
                continue
            lines.append(node.lineno)
    return lines


class EncodingTest(unittest.TestCase):
    def test_detector(self):
        src = ("p.read_text()\np.read_text(encoding='utf-8')\nopen('a')\nopen('a', 'rb')\n"
               "p.open('w')\np.open(mode='wb')\nImage.open('x.png')\np.write_text(s, encoding='utf-8')\n")
        self.assertEqual(missing_encoding(src), [1, 3, 5])

    def test_tracked_python_files_set_encoding(self):
        out = subprocess.run(["git", "ls-files", "-z", "*.py"], cwd=ROOT, capture_output=True, check=True).stdout
        bad = []
        for rel in filter(None, out.decode("utf-8").split("\0")):
            path = ROOT / rel
            if not path.is_file():
                continue
            for line in missing_encoding(path.read_text(encoding="utf-8")):
                bad.append(f"{rel}:{line}")
        self.assertEqual(bad, [], "文本读写要写 encoding=\"utf-8\"，否则 Windows 上会按系统代码页解码")


if __name__ == "__main__":
    unittest.main()
