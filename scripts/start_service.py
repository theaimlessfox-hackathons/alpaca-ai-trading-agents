#!/usr/bin/env python3
"""Run the paper-trading scheduler and dashboard as one hosted service."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time


def main() -> int:
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    port = env.get("PORT", "8501")
    commands = [
        [sys.executable, "-m", "scheduler.cycle_loop", "--live"],
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            "dashboard/app.py",
            "--server.port",
            port,
            "--server.address",
            "0.0.0.0",
        ],
    ]
    children = [subprocess.Popen(command, env=env) for command in commands]

    def stop(_signum=None, _frame=None) -> None:
        for child in children:
            if child.poll() is None:
                child.terminate()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        while True:
            for child in children:
                code = child.poll()
                if code is not None:
                    stop()
                    for sibling in children:
                        if sibling.poll() is None:
                            sibling.wait(timeout=10)
                    return code or 1
            time.sleep(1)
    finally:
        stop()


if __name__ == "__main__":
    raise SystemExit(main())
