from __future__ import annotations

import json
from typing import Any, Callable, Literal

from pydantic import BaseModel, Field, ValidationError, field_validator


class ProposalLeg(BaseModel):
    side: Literal["short", "long"]
    right: Literal["put", "call"]
    strike: float
    delta: float
    bid: float
    ask: float
    iv: float
    occ_symbol: str | None = None


class TradeProposal(BaseModel):
    symbol: str
    structure: Literal["credit_spread"]
    expiration: str
    dte: int
    legs: list[ProposalLeg]
    limit: float | None = None
    qty: int = 1
    thesis: str
    confidence: float = Field(ge=0, le=1)
    est_max_loss: float = 0.0

    @field_validator("legs")
    @classmethod
    def two_legs(cls, v: list[ProposalLeg]) -> list[ProposalLeg]:
        if len(v) != 2:
            raise ValueError("credit_spread needs 2 legs")
        return v


class CriticNote(BaseModel):
    rebuttal: str
    invalidation: list[str]


def extract_json_value(raw: Any) -> Any:
    """Parse a JSON value out of model text.

    Accepts a bare object, a ```json fence, or the first {...} block inside prose.
    """
    if not isinstance(raw, str):
        return raw
    text = raw.strip()
    if not text:
        raise json.JSONDecodeError("empty", raw, 0)
    if text.startswith("```"):
        lines = text.splitlines()[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end <= start:
            raise
        return json.loads(text[start : end + 1])


def _as_proposal_data(data: Any) -> Any:
    if not isinstance(data, dict):
        return data
    if "symbol" in data and "legs" in data:
        return data
    for key in ("proposal", "trade", "data", "result"):
        inner = data.get(key)
        if isinstance(inner, dict) and "symbol" in inner:
            return inner
    return data


def parse_and_retry(call_fn: Callable[[str | None], str], *, attempts: int = 3) -> TradeProposal | None:
    err: str | None = None
    for _ in range(attempts):
        raw = call_fn(err)
        try:
            data = _as_proposal_data(extract_json_value(raw))
            return TradeProposal.model_validate(data)
        except (json.JSONDecodeError, ValidationError, TypeError) as exc:
            err = str(exc)
    return None
