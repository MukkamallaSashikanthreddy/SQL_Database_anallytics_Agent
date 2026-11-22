from __future__ import annotations

from app import llm_provider


def test_model_configuration_is_gemini_flash_lite(monkeypatch):
    monkeypatch.setattr(llm_provider, "GOOGLE_MODEL", "gemini-3.5-flash-lite")
    assert llm_provider.gemini_configuration_status()["model"] == "gemini-3.5-flash-lite"


def test_provider_status_does_not_leak_api_key(monkeypatch):
    monkeypatch.setattr(llm_provider, "GOOGLE_API_KEY", "private-key-value")
    status = llm_provider.gemini_configuration_status()
    assert "private-key-value" not in repr(status)


def test_provider_timeout_and_retry_settings(monkeypatch):
    monkeypatch.setattr(llm_provider, "GEMINI_TIMEOUT_SECONDS", 30)
    status = llm_provider.gemini_configuration_status()
    assert status["timeout_seconds"] == 30
    assert status["automatic_retries"] == 0
