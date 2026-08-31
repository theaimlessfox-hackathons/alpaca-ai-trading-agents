from __future__ import annotations

from agents.prompts import CRITIC_SYSTEM
from agents.schemas import CriticNote, TradeProposal


def run_critic(proposal: TradeProposal, *, chat_fn=None) -> CriticNote:
    if chat_fn is None:
        return CriticNote(
            rebuttal="Credit may not offset a fast move through the short strike.",
            invalidation=["underlying through short strike", "IV crush fails to materialize"],
        )
    raw = chat_fn(
        [
            {"role": "system", "content": CRITIC_SYSTEM},
            {"role": "user", "content": proposal.model_dump_json()},
        ]
    )
    try:
        return CriticNote.model_validate_json(raw)
    except Exception:
        return CriticNote(rebuttal=str(raw)[:400], invalidation=["model output malformed"])
