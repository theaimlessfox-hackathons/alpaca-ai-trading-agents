"""Model-agnostic chat client. Featherless is primary (partner-prize track);
xAI Grok and Claude are live runtime failovers when configured.

Only raises once every configured provider has failed, so a Featherless outage
or a malformed-JSON response doesn't need to fail the whole cycle closed if a
second provider is configured -- and if none succeed, callers
(parse_and_retry / run_proposer) already fail closed on RuntimeError.
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

    client = OpenAI(
        api_key=s.featherless_api_key,
        base_url=s.resolved_featherless_base_url(),
        timeout=20.0,
        max_retries=0,
    )
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


def _xai_chat(messages: list[dict[str, str]], *, json_mode: bool) -> str:
    s = get_settings()
    if not s.xai_api_key:
        raise RuntimeError("XAI_API_KEY missing for fallback")
    from openai import OpenAI

    client = OpenAI(
        api_key=s.xai_api_key,
        base_url=s.xai_base_url or "https://api.x.ai/v1",
        # grok-4.6 has measured at ~70s even for small structured replies. A
        # 45s cutoff made the configured fallback permanently unusable.
        timeout=120.0,
        max_retries=0,
    )
    kwargs: dict = {
        "model": s.xai_model or "grok-4",
        "messages": messages,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    resp = client.chat.completions.create(**kwargs)
    return resp.choices[0].message.content or ""


def _try_provider(name: str, call, *, json_mode: bool, errors: list[str]) -> str | None:
    try:
        text = call(json_mode=json_mode)
        if not json_mode or _looks_like_json(text):
            return text
        errors.append(f"{name}: response was not valid JSON")
    except Exception as exc:  # noqa: BLE001 - failover, do not crash the cycle
        errors.append(f"{name}: {exc}")
    return None


def chat(messages: list[dict[str, str]], *, json_mode: bool = True) -> str:
    """Try Featherless; fail over to xAI then Claude when those fallbacks are on.
    Raises only when every configured provider has failed."""
    s = get_settings()
    errors: list[str] = []

    if s.featherless_api_key:
        text = _try_provider(
            "featherless",
            lambda json_mode: _featherless_chat(messages, json_mode=json_mode),
            json_mode=json_mode,
            errors=errors,
        )
        if text is not None:
            return text
    else:
        errors.append("featherless: FEATHERLESS_API_KEY missing")

    if s.xai_fallback:
        if s.xai_api_key:
            text = _try_provider(
                "xai",
                lambda json_mode: _xai_chat(messages, json_mode=json_mode),
                json_mode=json_mode,
                errors=errors,
            )
            if text is not None:
                return text
        else:
            errors.append("xai: XAI_API_KEY missing")

    if s.use_anthropic_fallback:
        try:
            return _claude_chat(messages, json_mode=json_mode)
        except Exception as exc:  # noqa: BLE001 - same reasoning as above
            errors.append(f"anthropic: {exc}")

    raise RuntimeError("; ".join(errors) or "no LLM provider configured")
