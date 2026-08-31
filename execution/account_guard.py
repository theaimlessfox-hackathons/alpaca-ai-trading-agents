from __future__ import annotations

import asyncio

from config.settings import Settings, get_settings


class AccountGuardError(RuntimeError):
    pass


def assert_can_submit(*, account_id: str | None, settings: Settings | None = None) -> None:
    """`account_id` must be the REAL, currently-authenticated account id (see
    resolve_account_id below) -- not the configured expectation. Passing the
    expected value back as the thing being checked is a no-op guard; this was a
    real bug (execution/broker.py used to do exactly that).

    Fails closed: if EXPECTED_ACCOUNT_ID is configured but no account_id could be
    resolved, that is treated as "cannot verify" and raises, not "skip the check."
    """
    s = settings or get_settings()
    if not s.alpaca_paper_trade:
        raise AccountGuardError("paper_trade required")
    if s.alpaca_account_role not in {"sandbox", "competition"}:
        raise AccountGuardError("bad role")
    if not (s.expected_account_id or "").strip():
        raise AccountGuardError("EXPECTED_ACCOUNT_ID required for live submission")
    if not account_id:
        raise AccountGuardError("could not resolve a real account_id to verify against EXPECTED_ACCOUNT_ID")
    if account_id != s.expected_account_id:
        raise AccountGuardError("account_id mismatch")
    if s.alpaca_account_role == "competition" and not s.compete_enabled:
        raise AccountGuardError("competition requires COMPETE_ENABLED")
    if not s.compete_window_open():
        raise AccountGuardError("compete_after not reached")


async def resolve_account_id() -> str | None:
    """Fetch the real account id via a live MCP call. Returns None (never raises)
    on any failure -- an unresolved id is turned into a fail-closed AccountGuardError
    by assert_can_submit, not swallowed here."""
    from tools.account_tools import get_account_info

    try:
        info = await get_account_info()
    except Exception:  # noqa: BLE001 - unresolved id fails assert_can_submit closed
        return None
    data = info.get("data", info) if isinstance(info, dict) else info
    if not isinstance(data, dict):
        return None
    value = data.get("account_number") or data.get("id")
    return str(value) if value else None


def resolve_account_id_sync() -> str | None:
    return asyncio.run(resolve_account_id())
