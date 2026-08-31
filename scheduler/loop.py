"""010 — snapshot + halt hook. Only scheduler file that calls flatten_all."""

from __future__ import annotations

from pathlib import Path

from execution.flatten import flatten_all
from risk.kill_switch import is_halted, is_killed
from storage.db import DEFAULT_PATH, create_all, insert_equity, session_sod_and_start


def snapshot_and_maybe_flatten(
    *,
    equity: float,
    sod: float,
    start: float,
    payloads: dict[int, dict],
    path: Path = DEFAULT_PATH,
    submit_fn=None,
    cancel_fn=None,
    lookup_fn=None,
) -> str | None:
    create_all(path)
    # Insert today's print first so session SOD is this print, not first-ever
    # competition equity, on the first cycle of a new session.
    insert_equity(equity, path=path)
    sod_now, start_now = session_sod_and_start(path)
    sod_use = sod_now if sod_now else sod
    start_use = start_now if start_now else start
    if is_killed():
        result = flatten_all(
            "kill",
            payloads=payloads,
            path=path,
            submit_fn=submit_fn,
            cancel_fn=cancel_fn,
            lookup_fn=lookup_fn,
        )
        return "kill" if result.complete else "kill_flatten_incomplete"
    halted, why = is_halted(equity, sod_use, start_use)
    if halted:
        result = flatten_all(
            why or "halt",
            payloads=payloads,
            path=path,
            submit_fn=submit_fn,
            cancel_fn=cancel_fn,
            lookup_fn=lookup_fn,
        )
        if result.complete:
            return why
        return f"{why or 'halt'}_flatten_incomplete"
    return None
