"""Start official alpaca-mcp-server over stdio. No auto-restart (wave 2)."""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import tempfile
from dataclasses import dataclass

from config.settings import get_settings


def mcp_env(api_key: str | None = None, secret_key: str | None = None) -> dict[str, str]:
    """Environment shared by every MCP launch path.

    uv/uvx defaults to ``~/.cache/uv``. That directory is read-only on some
    hosted runners, which used to make account lookup fail before the server
    started and left the trading loop blocked on ``missing_account_equity``.
    """
    s = get_settings()
    env = os.environ.copy()
    if api_key is None or secret_key is None:
        key, secret = s.execution_credentials()
    else:
        key, secret = api_key, secret_key
    env["ALPACA_API_KEY"] = key
    env["ALPACA_SECRET_KEY"] = secret
    env["ALPACA_PAPER_TRADE"] = "true"
    tmp = tempfile.gettempdir()
    env.setdefault("UV_CACHE_DIR", os.path.join(tmp, "thetagate-uv-cache"))
    env.setdefault("UV_TOOL_DIR", os.path.join(tmp, "thetagate-uv-tools"))
    env.setdefault("UV_PYTHON_INSTALL_DIR", os.path.join(tmp, "thetagate-uv-python"))
    return env


def _env() -> dict[str, str]:
    return mcp_env()


# Latest alpaca-mcp-server 2.3.1 + unpinned fastmcp 3.4.7 crashes
# (fastmcp.tools.tool). Pin 3.4.0, which starts and serves the tool surface.
ALPACA_MCP_SPEC = "alpaca-mcp-server==2.3.1"
FASTMCP_SPEC = "fastmcp==3.4.0"


def command() -> list[str]:
    uvx = shutil.which("uvx")
    if uvx:
        return [uvx, "--from", ALPACA_MCP_SPEC, "--with", FASTMCP_SPEC, "alpaca-mcp-server"]
    alpaca = shutil.which("alpaca-mcp-server")
    if alpaca:
        return [alpaca]
    raise FileNotFoundError("uvx or alpaca-mcp-server not on PATH")


@dataclass
class ServerProcess:
    proc: subprocess.Popen

    def kill(self) -> None:
        if self.proc.poll() is not None:
            return
        self.proc.send_signal(signal.SIGTERM)
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait(timeout=3)


def start() -> ServerProcess:
    s = get_settings()
    if not s.alpaca_paper_trade:
        raise RuntimeError("paper only")
    proc = subprocess.Popen(
        command(),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=_env(),
    )
    return ServerProcess(proc=proc)
