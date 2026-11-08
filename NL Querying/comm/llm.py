"""OpenAI-compatible LLM client for the hybrid NLQ escape hatch.

Provider-agnostic by design - the *same* code talks to:

* **OpenAI** (default) at ``https://api.openai.com/v1``,
* **Ollama Cloud** (``https://ollama.com/v1``) with an API key,
* **local Ollama** (``http://localhost:11434/v1``), or
* **Modal-hosted vLLM** (``https://<workspace>--aegis-llm-serve.modal.run/v1``),
  which serves the Qwen model decided for this project.

Configuration (all optional; nothing is sent until ``chat`` is called)::

    AEGIS_LLM_BASE_URL   default "https://api.openai.com/v1"
    AEGIS_LLM_MODEL      default "gpt-4o-mini"
    AEGIS_LLM_API_KEY    key value; if unset, read AEGIS_LLM_KEY_FILE
    AEGIS_LLM_KEY_FILE   default "<repo>/.keys/openai.txt"
    AEGIS_LLM_TIMEOUT    default 45 seconds
    AEGIS_LLM_EXTRA_BODY optional JSON merged into the request body (e.g.
                         '{"chat_template_kwargs": {"enable_thinking": false}}'
                         for Qwen3 on vLLM)

The ``.keys/`` directory is local-only and must never be committed. Security:
keys are never logged, echoed, or serialised into results.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

REPO_ROOT = Path(__file__).resolve().parents[2]

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_KEY_FILE = REPO_ROOT / ".keys" / "openai.txt"
DEFAULT_TIMEOUT = 45.0


class LLMError(RuntimeError):
    """The LLM endpoint was unreachable or returned unusable content."""


@dataclass(frozen=True)
class LLMConfig:
    base_url: str
    model: str
    api_key: str | None
    timeout: float
    extra_body: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_env(cls) -> LLMConfig:
        key = os.environ.get("AEGIS_LLM_API_KEY")
        if not key:
            key_file = Path(
                os.environ.get("AEGIS_LLM_KEY_FILE", DEFAULT_KEY_FILE)
            ).expanduser()
            if key_file.is_file():
                key = key_file.read_text(encoding="utf-8").strip()
        return cls(
            base_url=os.environ.get("AEGIS_LLM_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
            model=os.environ.get("AEGIS_LLM_MODEL", DEFAULT_MODEL),
            api_key=key or None,
            timeout=float(os.environ.get("AEGIS_LLM_TIMEOUT", DEFAULT_TIMEOUT)),
            extra_body=_parse_extra_body(os.environ.get("AEGIS_LLM_EXTRA_BODY", "")),
        )


def _http_error_message(response: httpx.Response) -> str:
    """Turn a provider error body into a concise, key-free message."""
    detail = ""
    try:
        payload = response.json()
    except ValueError:
        payload = None
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            detail = str(error.get("message") or error.get("code") or "")
        elif error:
            detail = str(error)
    if not detail:
        detail = (response.text or "").strip()[:300]
    suffix = f": {detail}" if detail else ""
    return f"LLM request failed ({response.status_code}){suffix}"


def _parse_extra_body(raw: str) -> dict[str, Any]:
    """Optional JSON object merged into every request body (never secrets)."""
    if not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


class LLMClient:
    """Minimal chat-completions client (no vendor SDK required)."""

    def __init__(self, config: LLMConfig | None = None) -> None:
        self.config = config or LLMConfig.from_env()

    @classmethod
    def from_env_if_configured(cls) -> LLMClient | None:
        """Build a client only when a key is available (safe local default)."""
        config = LLMConfig.from_env()
        return cls(config) if config.api_key else None

    @property
    def available(self) -> bool:
        return bool(self.config.api_key)

    def status(self) -> dict[str, Any]:
        """Safe, key-free description for smoke tests and logs."""
        return {
            "available": self.available,
            "base_url": self.config.base_url,
            "model": self.config.model,
        }

    # ------------------------------------------------------------------
    # Transport
    # ------------------------------------------------------------------
    def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
        max_tokens: int = 300,
        response_format: dict[str, Any] | None = None,
    ) -> str:
        """One chat completion; returns the assistant text content."""
        if not self.config.api_key:
            raise LLMError(
                f"no LLM API key configured (AEGIS_LLM_API_KEY or {DEFAULT_KEY_FILE})"
            )
        payload: dict[str, Any] = {
            **self.config.extra_body,
            "model": self.config.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = tools
        if response_format:
            payload["response_format"] = response_format

        try:
            response = httpx.post(
                f"{self.config.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=self.config.timeout,
            )
        except httpx.HTTPError as exc:
            raise LLMError(f"LLM request failed: {exc}") from exc

        if response.status_code >= 400:
            raise LLMError(_http_error_message(response))

        try:
            message = response.json()["choices"][0]["message"]
        except (KeyError, IndexError, ValueError) as exc:
            raise LLMError("LLM returned an unexpected payload shape") from exc
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise LLMError("LLM returned an empty completion")
        return content

    def chat_json(
        self,
        messages: list[dict[str, Any]],
        *,
        temperature: float = 0.0,
        max_tokens: int = 300,
    ) -> dict[str, Any]:
        """Chat completion parsed as one JSON object (tolerates code fences)."""
        raw = self.chat(messages, temperature=temperature, max_tokens=max_tokens)
        return parse_json_object(raw)


def parse_json_object(text: str) -> dict[str, Any]:
    """Extract the first JSON object from model output; strict otherwise."""
    cleaned = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", cleaned, re.DOTALL)
    if fenced:
        cleaned = fenced.group(1).strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end <= start:
        raise LLMError("LLM response contained no JSON object")
    try:
        parsed = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError as exc:
        raise LLMError(f"LLM response was not valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise LLMError("LLM response JSON was not an object")
    return parsed
