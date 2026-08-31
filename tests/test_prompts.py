from agents.prompts import PROPOSER_SYSTEM, format_cycle_recap, format_headlines


def test_format_cycle_recap_empty():
    assert format_cycle_recap([]) == "No prior cycles for this symbol yet."


def test_format_cycle_recap_oldest_to_newest():
    # recent_cycles returns most-recent-first
    rows = [
        {"verdict": "approve_dry", "reason": "ok", "proposal_json": ""},
        {"verdict": "veto", "reason": "short_delta", "proposal_json": ""},
        {"verdict": "veto", "reason": "wide_bid_ask", "proposal_json": ""},
    ]
    out = format_cycle_recap(rows)
    assert out.startswith("Last cycles for this symbol, oldest to newest:")
    # wide_bid_ask happened before short_delta happened before approve_dry
    assert out.index("wide_bid_ask") < out.index("short_delta") < out.index("approved")


def test_format_cycle_recap_handles_missing_reason():
    rows = [{"verdict": "stand_down", "reason": None, "proposal_json": ""}]
    assert "stand_down" in format_cycle_recap(rows)


def test_format_headlines_empty():
    assert format_headlines([]) == "No recent headlines."


def test_format_headlines_caps_at_five():
    heads = [f"headline {i}" for i in range(10)]
    out = format_headlines(heads)
    body = out.removeprefix("Recent headlines: ")
    assert len(body.split(" | ")) == 5


def test_proposer_prompt_mentions_recap_and_headlines_as_advisory():
    assert "recent_cycles" in PROPOSER_SYSTEM
    assert "headlines" in PROPOSER_SYSTEM
    assert "never" in PROPOSER_SYSTEM.lower() or "does not override" in PROPOSER_SYSTEM.lower() or "never a reason" in PROPOSER_SYSTEM.lower()
