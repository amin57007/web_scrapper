from __future__ import annotations

import os
from pathlib import Path

import pytest

from ulscrape.config import Settings, load_dotenv

_LLM_ENV = (
    "UL_LLM_API_KEY",
    "LLM_API_KEY",
    "OPENAI_API_KEY",
    "OPENROUTER_API_KEY",
    "ANTHROPIC_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
)


def _clear_llm_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in _LLM_ENV:
        monkeypatch.delenv(name, raising=False)


def test_settings_reads_openai_key(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_llm_env(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-from-env")
    settings = Settings.from_env()
    assert settings.llm_api_key == "sk-from-env"


def test_settings_prefers_ul_llm_key(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_llm_env(monkeypatch)
    monkeypatch.setenv("UL_LLM_API_KEY", "ul-key")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-from-env")
    settings = Settings.from_env()
    assert settings.llm_api_key == "ul-key"


def test_load_dotenv_does_not_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        'OPENAI_API_KEY="from-file"\nUL_EMAIL="user@example.com"\n',
        encoding="utf-8",
    )
    monkeypatch.setenv("OPENAI_API_KEY", "already-set")
    monkeypatch.setenv("UL_EMAIL", "")
    monkeypatch.delenv("UL_EMAIL")
    loaded = load_dotenv(env_file)
    assert loaded == env_file.resolve()
    assert os.environ["OPENAI_API_KEY"] == "already-set"
    assert os.environ["UL_EMAIL"] == "user@example.com"
