"""Start official alpaca-mcp-server over stdio. No auto-restart (wave 2)."""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
from dataclasses import dataclass

from config.settings import get_settings


def _env() -> dict[str, str]:
    s = get_settings()
    env = os.environ.copy()
    key, secret = s.execution_credentials()
    env["ALPACA_API_KEY"] = key
    env["ALPACA_SECRET_KEY"] = secret
    env["ALPACA_PAPER_TRADE"] = "true"
    return env


def command() -> list[str]:
    uvx = shutil.which("uvx")
    if uvx:
        return [uvx, "alpaca-mcp-server"]
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
