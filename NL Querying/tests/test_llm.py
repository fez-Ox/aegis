"""Tests for the OpenAI-compatible LLM client (pure offline, no network)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

FOLDER_ROOT = Path(__file__).resolve().parents[1]
if str(FOLDER_ROOT) not in sys.path:
    sys.path.insert(0, str(FOLDER_ROOT))

from comm.llm import (
    DEFAULT_KEY_FILE,
    LLMClient,
    LLMConfig,
    LLMError,
    parse_json_object,
)


def test_parse_json_object_accepts_plain_and_fenced_json() -> None:
    assert parse_json_object('{"intent": "locate"}')["intent"] == "locate"
    fenced = '```json\n{"intent": "temporal", "item": "glasses"}\n```'
    assert parse_json_object(fenced)["item"] == "glasses"


def test_parse_json_object_rejects_prose() -> None:
    try:
        parse_json_object("I think your keys are in the kitchen.")
    except LLMError:
        pass
    else:  # pragma: no cover - only when the guard fails
        raise AssertionError("expected LLMError for non-JSON output")


def test_config_reads_explicit_environment(monkeypatch) -> None:
    monkeypatch.setenv("AEGIS_LLM_API_KEY", "test-key")
    monkeypatch.setenv("AEGIS_LLM_BASE_URL", "https://example.test/v1/")
    monkeypatch.setenv("AEGIS_LLM_MODEL", "Qwen/Qwen3-8B-AWQ")
    config = LLMConfig.from_env()
    assert config.api_key == "test-key"
    assert config.base_url == "https://example.test/v1"
    assert config.model == "Qwen/Qwen3-8B-AWQ"


def test_config_reads_key_file(monkeypatch, tmp_path) -> None:
    key_file = tmp_path / "key.txt"
    key_file.write_text("file-key\n", encoding="utf-8")
    monkeypatch.delenv("AEGIS_LLM_API_KEY", raising=False)
    monkeypatch.setenv("AEGIS_LLM_KEY_FILE", str(key_file))
    client = LLMClient.from_env_if_configured()
    assert client is not None
    assert client.available


def test_no_key_means_no_auto_client(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("AEGIS_LLM_API_KEY", raising=False)
    monkeypatch.setenv("AEGIS_LLM_KEY_FILE", str(tmp_path / "missing.txt"))
    assert LLMClient.from_env_if_configured() is None


def test_extra_body_is_parsed_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("AEGIS_LLM_API_KEY", "x")
    monkeypatch.setenv(
        "AEGIS_LLM_EXTRA_BODY",
        '{"chat_template_kwargs": {"enable_thinking": false}}',
    )
    config = LLMConfig.from_env()
    assert config.extra_body["chat_template_kwargs"]["enable_thinking"] is False


def test_invalid_extra_body_is_ignored(monkeypatch) -> None:
    monkeypatch.setenv("AEGIS_LLM_API_KEY", "x")
    monkeypatch.setenv("AEGIS_LLM_EXTRA_BODY", "not-json")
    assert LLMConfig.from_env().extra_body == {}


def test_status_never_exposes_the_key() -> None:
    client = LLMClient(
        LLMConfig(
            base_url="https://example.test/v1",
            model="fake",
            api_key="super-secret",
            timeout=1.0,
        )
    )
    status = client.status()
    assert status["available"] is True
    assert "super-secret" not in json.dumps(status)


def test_chat_without_key_raises_cleanly() -> None:
    client = LLMClient(
        LLMConfig(
            base_url="https://example.test/v1",
            model="fake",
            api_key=None,
            timeout=1.0,
        )
    )
    try:
        client.chat([{"role": "user", "content": "hello"}])
    except LLMError as exc:
        assert "API key" in str(exc)
    else:  # pragma: no cover - only when the guard fails
        raise AssertionError("expected LLMError without an API key")


def test_defaults_target_openai(monkeypatch) -> None:
    for variable in (
        "AEGIS_LLM_API_KEY",
        "AEGIS_LLM_BASE_URL",
        "AEGIS_LLM_MODEL",
        "AEGIS_LLM_KEY_FILE",
    ):
        monkeypatch.delenv(variable, raising=False)
    config = LLMConfig.from_env()
    assert config.base_url == "https://api.openai.com/v1"
    assert config.model == "gpt-4o-mini"
    assert DEFAULT_KEY_FILE.name == "openai.txt"
    assert DEFAULT_KEY_FILE.parent.name == ".keys"


def test_chat_surfaces_provider_error_message(monkeypatch) -> None:
    class ErrorResponse:
        status_code = 429
        text = '{"error": {"message": "no credits remaining"}}'

        def json(self):
            return {
                "error": {
                    "message": "no credits remaining",
                    "type": "insufficient_quota",
                }
            }

    monkeypatch.setattr("comm.llm.httpx.post", lambda *args, **kwargs: ErrorResponse())
    client = LLMClient(
        LLMConfig(
            base_url="https://example.test/v1",
            model="fake",
            api_key="super-secret",
            timeout=1.0,
        )
    )
    try:
        client.chat([{"role": "user", "content": "hello"}])
    except LLMError as exc:
        assert "429" in str(exc)
        assert "no credits remaining" in str(exc)
        assert "super-secret" not in str(exc)
    else:  # pragma: no cover - only when the guard fails
        raise AssertionError("expected LLMError for an HTTP error")


def test_chat_json_parses_a_successful_response(monkeypatch) -> None:
    class SuccessResponse:
        status_code = 200
        text = ""

        def json(self):
            return {"choices": [{"message": {"content": '{"intent": "locate"}'}}]}

    monkeypatch.setattr(
        "comm.llm.httpx.post", lambda *args, **kwargs: SuccessResponse()
    )
    client = LLMClient(
        LLMConfig(
            base_url="https://example.test/v1",
            model="fake",
            api_key="test-key",
            timeout=1.0,
        )
    )
    assert client.chat_json([{"role": "user", "content": "hello"}]) == {
        "intent": "locate"
    }
