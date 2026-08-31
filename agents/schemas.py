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


def parse_and_retry(call_fn: Callable[[str | None], str], *, attempts: int = 3) -> TradeProposal | None:
    err: str | None = None
    for _ in range(attempts):
        raw = call_fn(err)
        try:
            data: Any = json.loads(raw) if isinstance(raw, str) else raw
            return TradeProposal.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as exc:
            err = str(exc)
    return None
