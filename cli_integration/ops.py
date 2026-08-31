"""One official alpaca CLI read for the demo. Not an executor."""

from __future__ import annotations

import shutil
import subprocess


def account() -> str:
    exe = shutil.which("alpaca")
    if not exe:
        raise FileNotFoundError("alpaca CLI not installed — https://github.com/alpacahq/cli")
    out = subprocess.run([exe, "account"], capture_output=True, text=True, check=False)
    if out.returncode != 0:
        raise RuntimeError(out.stderr or "alpaca account failed")
    return out.stdout
