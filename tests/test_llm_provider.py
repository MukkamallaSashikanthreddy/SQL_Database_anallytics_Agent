from __future__ import annotations

from app import llm_provider


def test_provider_status_hides_secret(monkeypatch):
    monkeypatch.setattr(llm_provider, "GOOGLE_API_KEY", "secret-value")
    monkeypatch.setattr(llm_provider, "GOOGLE_MODEL", "gemini-3.5-flash-lite")
    result = llm_provider.gemini_configuration_status()
    assert result["configured"] is True
    assert result["model"] == "gemini-3.5-flash-lite"
    assert "secret-value" not in str(result)


def test_provider_status_when_key_missing(monkeypatch):
    monkeypatch.setattr(llm_provider, "GOOGLE_API_KEY", "")
    assert llm_provider.gemini_configuration_status()["configured"] is False


def test_response_text_handles_string():
    assert llm_provider.response_text(type("Message", (), {"content": "SELECT 1"})()) == "SELECT 1"


def test_response_text_handles_text_blocks():
    message = type("Message", (), {"content": [{"type": "text", "text": "SELECT 1"}, {"type": "text", "text": "LIMIT 1"}]})()
    assert llm_provider.response_text(message) == "SELECT 1\nLIMIT 1"


def test_missing_key_raises_provider_configuration_error(monkeypatch):
    import pytest
    monkeypatch.setattr(llm_provider, "GOOGLE_API_KEY", "")
    with pytest.raises(llm_provider.ProviderConfigurationError):
        llm_provider.get_gemini_model()


def test_model_factory_uses_current_google_genai_parameters(monkeypatch):
    import sys
    import types

    captured = {}

    class FakeChatGoogleGenerativeAI:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    fake_module = types.ModuleType("langchain_google_genai")
    fake_module.ChatGoogleGenerativeAI = FakeChatGoogleGenerativeAI
    monkeypatch.setitem(sys.modules, "langchain_google_genai", fake_module)
    monkeypatch.setattr(llm_provider, "GOOGLE_API_KEY", "test-google-key")
    monkeypatch.setattr(llm_provider, "GOOGLE_MODEL", "gemini-3.5-flash-lite")
    monkeypatch.setattr(llm_provider, "GEMINI_TIMEOUT_SECONDS", 30)
    llm_provider.get_gemini_model.cache_clear()
    try:
        llm_provider.get_gemini_model()
    finally:
        llm_provider.get_gemini_model.cache_clear()

    assert captured["api_key"] == "test-google-key"
    assert captured["model"] == "gemini-3.5-flash-lite"
    assert captured["timeout"] == 30
    assert captured["max_retries"] == 0
    assert captured["thinking_level"] == "low"
    assert "temperature" not in captured
    assert "google_api_key" not in captured
