import json

import pytest

import agents.llm as llm
from config.settings import get_settings


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_smoke_missing_key(monkeypatch):
    monkeypatch.setenv("FEATHERLESS_API_KEY", "")
    get_settings.cache_clear()
    r = llm.smoke()
    assert r.ok is False
    assert "FEATHERLESS" in (r.error or "")


def test_smoke_ok_with_key_present(monkeypatch):
    monkeypatch.setenv("FEATHERLESS_API_KEY", "fake-key")
    get_settings.cache_clear()
    monkeypatch.setattr(llm, "_featherless_chat", lambda *_a, **_k: "pong")
    r = llm.smoke()
    assert r.ok is True


def test_smoke_fails_when_provider_errors(monkeypatch):
    monkeypatch.setenv("FEATHERLESS_API_KEY", "fake-key")
    get_settings.cache_clear()
    monkeypatch.setattr(llm, "_featherless_chat", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("401")))
    r = llm.smoke()
    assert r.ok is False
    assert "401" in (r.error or "")


def test_chat_uses_featherless_when_it_succeeds(monkeypatch):
    monkeypatch.setenv("FEATHERLESS_API_KEY", "fake-key")
    get_settings.cache_clear()
    monkeypatch.setattr(llm, "_featherless_chat", lambda *_a, **_k: json.dumps({"ok": True}))

    def _boom(*_a, **_k):
        raise AssertionError("must not call Claude when Featherless succeeds")

    monkeypatch.setattr(llm, "_claude_chat", _boom)
    out = llm.chat([{"role": "user", "content": "hi"}])
    assert json.loads(out) == {"ok": True}


def test_chat_fails_over_to_claude_on_featherless_exception(monkeypatch):
    monkeypatch.setenv("FEATHERLESS_API_KEY", "fake-key")
    monkeypatch.setenv("XAI_FALLBACK", "false")
    monkeypatch.setenv("USE_ANTHROPIC_FALLBACK", "true")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key")
    get_settings.cache_clear()

    def _raise(*_a, **_k):
        raise RuntimeError("timeout")

    monkeypatch.setattr(llm, "_featherless_chat", _raise)
    monkeypatch.setattr(llm, "_claude_chat", lambda *_a, **_k: json.dumps({"from": "claude"}))
    out = llm.chat([{"role": "user", "content": "hi"}])
    assert json.loads(out) == {"from": "claude"}


def test_chat_fails_over_to_claude_on_non_json_featherless_response(monkeypatch):
    monkeypatch.setenv("FEATHERLESS_API_KEY", "fake-key")
    monkeypatch.setenv("XAI_FALLBACK", "false")
    monkeypatch.setenv("USE_ANTHROPIC_FALLBACK", "true")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key")
    get_settings.cache_clear()

    monkeypatch.setattr(llm, "_featherless_chat", lambda *_a, **_k: "not json")
    monkeypatch.setattr(llm, "_claude_chat", lambda *_a, **_k: json.dumps({"from": "claude"}))
    out = llm.chat([{"role": "user", "content": "hi"}])
    assert json.loads(out) == {"from": "claude"}


def test_chat_does_not_json_check_when_json_mode_false(monkeypatch):
    monkeypatch.setenv("FEATHERLESS_API_KEY", "fake-key")
    get_settings.cache_clear()
    monkeypatch.setattr(llm, "_featherless_chat", lambda *_a, **_k: "plain prose, not json")
    out = llm.chat([{"role": "user", "content": "hi"}], json_mode=False)
    assert out == "plain prose, not json"


def test_chat_raises_with_combined_errors_when_all_providers_fail(monkeypatch):
    monkeypatch.setenv("FEATHERLESS_API_KEY", "fake-key")
    monkeypatch.setenv("XAI_FALLBACK", "false")
    monkeypatch.setenv("USE_ANTHROPIC_FALLBACK", "true")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-key")
    get_settings.cache_clear()

    monkeypatch.setattr(llm, "_featherless_chat", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("fh down")))
    monkeypatch.setattr(llm, "_claude_chat", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("claude down")))
    with pytest.raises(RuntimeError, match="featherless.*anthropic"):
        llm.chat([{"role": "user", "content": "hi"}])


def test_chat_fails_over_to_xai_when_flagged(monkeypatch):
    monkeypatch.setenv("FEATHERLESS_API_KEY", "fake-key")
    monkeypatch.setenv("XAI_FALLBACK", "true")
    monkeypatch.setenv("XAI_API_KEY", "fake-xai")
    get_settings.cache_clear()
    monkeypatch.setattr(llm, "_featherless_chat", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("fh down")))
    monkeypatch.setattr(llm, "_xai_chat", lambda *_a, **_k: json.dumps({"from": "xai"}))

    def _boom(*_a, **_k):
        raise AssertionError("must not call Claude when xAI succeeds")

    monkeypatch.setattr(llm, "_claude_chat", _boom)
    out = llm.chat([{"role": "user", "content": "hi"}])
    assert json.loads(out) == {"from": "xai"}


def test_chat_does_not_try_xai_when_fallback_disabled(monkeypatch):
    monkeypatch.setenv("FEATHERLESS_API_KEY", "fake-key")
    monkeypatch.setenv("XAI_FALLBACK", "false")
    monkeypatch.setenv("XAI_API_KEY", "fake-xai")
    get_settings.cache_clear()
    monkeypatch.setattr(llm, "_featherless_chat", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("fh down")))

    def _boom(*_a, **_k):
        raise AssertionError("must not call xAI when fallback is disabled")

    monkeypatch.setattr(llm, "_xai_chat", _boom)
    with pytest.raises(RuntimeError, match="fh down"):
        llm.chat([{"role": "user", "content": "hi"}])


def test_chat_does_not_try_claude_when_fallback_disabled(monkeypatch):
    monkeypatch.setenv("FEATHERLESS_API_KEY", "fake-key")
    monkeypatch.setenv("XAI_FALLBACK", "false")
    monkeypatch.setenv("USE_ANTHROPIC_FALLBACK", "false")
    get_settings.cache_clear()

    monkeypatch.setattr(llm, "_featherless_chat", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("fh down")))

    def _boom(*_a, **_k):
        raise AssertionError("must not call Claude when fallback is disabled")

    monkeypatch.setattr(llm, "_claude_chat", _boom)
    with pytest.raises(RuntimeError, match="fh down"):
        llm.chat([{"role": "user", "content": "hi"}])
