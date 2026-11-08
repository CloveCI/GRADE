"""OpenRouter provider helpers (no network)."""

from __future__ import annotations

import json

import pytest

from autograder.llm_providers import llm_status, openrouter_fallback_enabled


def test_openrouter_fallback_disabled_without_key(monkeypatch):
    monkeypatch.delenv("GRADE_OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    assert openrouter_fallback_enabled() is False


def test_openrouter_fallback_enabled_with_key(monkeypatch):
    monkeypatch.setenv("GRADE_OPENROUTER_API_KEY", "sk-test")
    monkeypatch.setenv("GRADE_OPENROUTER_FALLBACK", "true")
    assert openrouter_fallback_enabled() is True


def test_llm_status_ready_when_openrouter_ok(monkeypatch):
    monkeypatch.setenv("GRADE_ENABLE_LLM", "true")
    monkeypatch.delenv("GRADE_GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GRADE_OPENROUTER_API_KEY", "sk-test")

    def _probe_gemini():
        return {"ok": False, "model": "gemini-2.0-flash", "error": "429"}

    def _probe_or():
        return {"ok": True, "model": "google/gemini-2.0-flash-001", "reply": "OK"}

    monkeypatch.setattr("autograder.llm_providers.probe_gemini_live", _probe_gemini)
    monkeypatch.setattr("autograder.llm_providers.probe_openrouter_live", _probe_or)

    st = llm_status()
    assert st["ready"] is True
    assert st["llm_openrouter"]["ready"] is True
