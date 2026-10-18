"""麦当劳 MCP 客户端（Streamable HTTP，纯标准库）。

- Token 只从参数或环境变量 MCD_MCP_TOKEN 读取，不落盘、不写日志。
- mcd.cn 是国内 CDN，走本机代理常握手超时，默认直连；直连失败再退回环境代理。
- 业务错误（HTTP 200 但 code≠200）抛 McdBusinessError，携带业务码，便于上层区分「门店打烊」「参数错误」等。
"""
from __future__ import annotations

import json
import logging
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from typing import Any

URL = "https://mcp.mcd.cn"
PROTOCOL = "2025-06-18"
log = logging.getLogger(__name__)


def token_setup_hint(platform: str | None = None) -> str:
    """当前系统上设置 MCD_MCP_TOKEN 的一行命令和后续操作，给安装脚本和缺 Token 的报错共用。"""
    platform = platform or sys.platform
    if platform.startswith("win"):
        # 不用 setx：它会把超过 1024 个字符的值截断
        cmd = '在 PowerShell 运行 [Environment]::SetEnvironmentVariable("MCD_MCP_TOKEN", "你的Token", "User")'
    else:
        shell = os.environ.get("SHELL", "")
        rc = "~/.zshrc" if shell.endswith("zsh") or (platform == "darwin" and not shell) else \
            "~/.bash_profile" if platform == "darwin" else "~/.bashrc"
        cmd = f"在终端运行 echo 'export MCD_MCP_TOKEN=\"你的Token\"' >> {rc}"
    return f"{cmd}，然后关掉所有终端窗口、完全退出 WorkBuddy 或 Claude Code 再重新打开（Claude Code 要从新开的终端启动）"


class McdMcpError(RuntimeError):
    """传输层或协议层错误。"""


class McdAuthError(McdMcpError):
    """没有 Token，或 Token 无效、过期（HTTP 401/403）。"""


class McdBusinessError(McdMcpError):
    """接口返回 HTTP 200，但业务码不是 200。"""

    def __init__(self, tool: str, code: Any, message: str):
        super().__init__(f"{tool} 业务失败：{code} {message}")
        self.tool, self.code, self.message = tool, code, message


class McdMcp:
    def __init__(self, token: str | None = None, timeout: float = 30, retries: int = 3, min_interval: float = 0.12):
        self._token = token or os.environ.get("MCD_MCP_TOKEN")
        if not self._token:
            raise McdAuthError("缺少 MCD_MCP_TOKEN")
        self.timeout, self.retries, self.min_interval = timeout, retries, min_interval
        self._id = 0
        self._lock = threading.Lock()
        self._last = 0.0
        self._direct = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        self._proxied = urllib.request.build_opener()
        self.calls = 0
        self._rpc("initialize", {"protocolVersion": PROTOCOL, "capabilities": {},
                                 "clientInfo": {"name": "mcdstrip", "version": "0.1.0"}})
        self._rpc("notifications/initialized", notify=True)

    # ---- 底层 ----
    def _throttle(self) -> None:
        with self._lock:
            wait = self._last + self.min_interval - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()

    def _post(self, body: dict) -> tuple[str, str]:
        data = json.dumps(body).encode()
        err: Exception | None = None
        for attempt in range(self.retries):
            opener = self._direct if attempt % 2 == 0 else self._proxied
            req = urllib.request.Request(URL, data=data, method="POST", headers={
                "Authorization": f"Bearer {self._token}", "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream"})
            self._throttle()
            try:
                with opener.open(req, timeout=self.timeout) as r:
                    return r.read().decode("utf-8"), r.headers.get("Content-Type", "")
            except urllib.error.HTTPError as e:
                if e.code in (401, 403):
                    raise McdAuthError(f"鉴权失败（HTTP {e.code}），请检查 Token") from e
                err = e
            except Exception as e:  # 网络抖动：换通道重试
                err = e
            log.debug("POST 第 %d 次失败：%s", attempt + 1, err)
            time.sleep(0.4 * (attempt + 1))
        raise McdMcpError(f"请求失败：{err}")

    def _rpc(self, method: str, params: dict | None = None, notify: bool = False) -> Any:
        body: dict = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            body["params"] = params
        if not notify:
            with self._lock:
                self._id += 1
                body["id"] = self._id
        raw, ctype = self._post(body)
        if notify or not raw.strip():
            return None
        if "event-stream" in ctype:
            frames = [ln[5:].strip() for ln in raw.splitlines() if ln.startswith("data:")]
            if not frames:
                raise McdMcpError("SSE 响应里没有 data 帧")
            raw = frames[-1]
        msg = json.loads(raw)
        if "error" in msg:
            raise McdMcpError(f"{method} 协议错误：{msg['error']}")
        return msg.get("result")

    # ---- 对外 ----
    def tools(self) -> list[dict]:
        return self._rpc("tools/list")["tools"]

    def call(self, name: str, **args: Any) -> dict:
        """返回 structuredContent（含 success / code / message / data），不判断业务码。"""
        t0 = time.monotonic()
        res = self._rpc("tools/call", {"name": name, "arguments": args}) or {}
        self.calls += 1
        sc = res.get("structuredContent") or {}
        log.debug("%s %s → code=%s（%.2fs）", name, _brief(args), sc.get("code"), time.monotonic() - t0)
        return sc

    def data(self, name: str, **args: Any) -> Any:
        """只取 data；业务码不是 200 时抛 McdBusinessError，避免把空数据当成真实结果。"""
        sc = self.call(name, **args)
        code = sc.get("code")
        if code not in (200, "200", None):
            raise McdBusinessError(name, code, sc.get("message", ""))
        return sc.get("data")


def _brief(args: dict) -> str:
    s = json.dumps(args, ensure_ascii=False)
    return s if len(s) <= 160 else s[:157] + "..."
