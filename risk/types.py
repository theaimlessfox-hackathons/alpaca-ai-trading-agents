from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Approve:
    max_loss: float


@dataclass(frozen=True)
class Veto:
    reason: str
