"""Model-agnostic chat client. Featherless is primary (partner-prize track);
Claude Sonnet 5 is a live runtime failover, not just an offline debug path.

Only raises once every configured provider has failed, so a Featherless outage
or a malformed-JSON response doesn't need to fail the whole cycle closed if a
second provider is configured -- and if neither is configured or both fail,
callers (parse_and_retry / run_proposer) already fail closed on RuntimeError.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from config.settings import get_settings


@dataclass(frozen=True)
class SmokeResult:
    ok: bool
    error: str | None
    model: str


def smoke() -> SmokeResult:
    s = get_settings()
    model = s.featherless_model or "featherless"
    if not s.featherless_api_key:
        return SmokeResult(False, "FEATHERLESS_API_KEY missing", s.featherless_model or "unset")
    try:
        text = _featherless_chat([{"role": "user", "content": "ping"}], json_mode=False)
    except Exception as exc:  # noqa: BLE001 - smoke must report the real provider error
        return SmokeResult(False, str(exc), model)
    if not (text or "").strip():
        return SmokeResult(False, "empty response", model)
    return SmokeResult(True, None, model)


def _looks_like_json(text: str) -> bool:
    try:
        json.loads(text)
        return True
    except (json.JSONDecodeError, TypeError):
        return False


def _featherless_chat(messages: list[dict[str, str]], *, json_mode: bool) -> str:
    s = get_settings()
    if not s.featherless_api_key:
        raise RuntimeError("FEATHERLESS_API_KEY missing")
    from openai import OpenAI

    client = OpenAI(api_key=s.featherless_api_key, base_url=s.featherless_base_url)
    kwargs: dict = {
        "model": s.featherless_model or "meta-llama/Meta-Llama-3.1-8B-Instruct",
        "messages": messages,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    resp = client.chat.completions.create(**kwargs)
    return resp.choices[0].message.content or ""


def _claude_chat(messages: list[dict[str, str]], *, json_mode: bool) -> str:
    s = get_settings()
    if not s.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY missing for fallback")
    import anthropic

    client = anthropic.Anthropic(api_key=s.anthropic_api_key)
    system = "\n".join(m["content"] for m in messages if m.get("role") == "system")
    if json_mode:
        system = (system + "\n\nRespond with JSON only. No prose, no markdown fences.").strip()
    convo = [{"role": m["role"], "content": m["content"]} for m in messages if m.get("role") != "system"]
    resp = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=1024,
        system=system or None,
        messages=convo,
    )
    return "".join(block.text for block in resp.content if getattr(block, "type", "") == "text")


def chat(messages: list[dict[str, str]], *, json_mode: bool = True) -> str:
    """Try Featherless; fail over live to Claude (if configured) on an error or,
    when json_mode is set, on a response that isn't even syntactically valid
    JSON. Raises only when every configured provider has failed."""
    s = get_settings()
    errors: list[str] = []

    if s.featherless_api_key:
        try:
            text = _featherless_chat(messages, json_mode=json_mode)
            if not json_mode or _looks_like_json(text):
                return text
            errors.append("featherless: response was not valid JSON")
        except Exception as exc:  # noqa: BLE001 - any Featherless failure should fail over, not crash the cycle
            errors.append(f"featherless: {exc}")
    else:
        errors.append("featherless: FEATHERLESS_API_KEY missing")

    if s.use_anthropic_fallback:
        try:
            return _claude_chat(messages, json_mode=json_mode)
        except Exception as exc:  # noqa: BLE001 - same reasoning as above
            errors.append(f"anthropic: {exc}")

    raise RuntimeError("; ".join(errors) or "no LLM provider configured")
