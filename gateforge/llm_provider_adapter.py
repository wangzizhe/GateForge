"""LLM provider adapter protocol and concrete implementations.

Abstracts the transport layer (HTTP requests, auth, response parsing) for
different LLM providers behind a unified interface. Provider-specific wire
format details are encapsulated in each adapter, keeping the agent core
provider-agnostic.

Extracted from agent_modelica_live_executor_v1 and llm_planner.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol


# ---- env bootstrap helpers ----

ENV_KEY_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
OPENAI_MODEL_HINT_PATTERN = re.compile(r"^(gpt|o[0-9]|chatgpt|gpt-5)", re.IGNORECASE)
ANTHROPIC_MODEL_HINT_PATTERN = re.compile(r"^(claude)", re.IGNORECASE)


def _parse_env_assignment(line: str) -> tuple[str, str] | tuple[None, None]:
    text = str(line or "").strip()
    if not text or text.startswith("#"):
        return None, None
    if text.startswith("export "):
        text = text[len("export ") :].strip()
    if "=" not in text:
        return None, None
    key, raw_value = text.split("=", 1)
    key = key.strip()
    if not ENV_KEY_PATTERN.match(key):
        return None, None
    value = raw_value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return key, value


def _load_env_file(path: Path, allowed_keys: set[str] | None = None) -> int:
    if not path.exists():
        return 0
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        content = path.read_text(encoding="latin-1")
    loaded = 0
    for line in content.splitlines():
        key, value = _parse_env_assignment(line)
        if not key:
            continue
        if isinstance(allowed_keys, set) and key not in allowed_keys:
            continue
        if str(os.getenv(key) or "").strip():
            continue
        os.environ[key] = value
        loaded += 1
    return loaded


def _bootstrap_env_from_repo(allowed_keys: set[str] | None = None) -> int:
    if str(os.getenv("GATEFORGE_DISABLE_ENV_BOOTSTRAP") or "").strip() == "1":
        return 0
    repo_root = Path(__file__).resolve().parents[1]
    candidates = [Path.cwd() / ".env", repo_root / ".env"]
    loaded = 0
    seen: set[str] = set()
    for path in candidates:
        key = str(path.resolve())
        if key in seen:
            continue
        seen.add(key)
        loaded += _load_env_file(path, allowed_keys=allowed_keys)
    return loaded


# ---- provider config ----

@dataclass
class LLMProviderConfig:
    """Configuration for an LLM provider connection."""
    provider_name: str
    model: str
    api_key: str
    temperature: float = 0.1
    timeout_sec: float = 120.0
    extra: dict = field(default_factory=dict)


# ---- provider adapter protocol ----

class LLMProviderAdapter(Protocol):
    """Protocol for LLM provider transport adapters.

    Each adapter encapsulates the wire format (endpoint URL, request payload,
    auth mechanism, response parsing) for a specific LLM provider. The agent
    core calls send_text_request with a prompt and gets back response text.
    """

    @property
    def provider_name(self) -> str:
        """Return the provider identifier (e.g. 'gemini', 'openai')."""
        ...

    def send_text_request(
        self,
        prompt: str,
        config: LLMProviderConfig,
    ) -> tuple[str, str]:
        """Send a text prompt to the LLM and return (response_text, error).

        Returns:
            Tuple of (response_text, error_string).
            Empty error string means success.
        """
        ...


# ---- Gemini adapter ----

class GeminiProviderAdapter:
    """Transport adapter for the Google Gemini API."""

    @property
    def provider_name(self) -> str:
        return "gemini"

    def send_text_request(
        self,
        prompt: str,
        config: LLMProviderConfig,
    ) -> tuple[str, str]:
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{config.model}:generateContent?key={urllib.parse.quote(config.api_key)}"
        )
        req_payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": config.temperature,
                "responseMimeType": "application/json",
            },
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(req_payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=config.timeout_sec) as resp:
                response_payload = json.loads(resp.read().decode("utf-8"))
        except TimeoutError:
            return "", "gemini_request_timeout"
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            if int(exc.code) == 429:
                return "", f"gemini_rate_limited:{body[:180]}"
            return "", f"gemini_http_error:{exc.code}:{body[:180]}"
        except urllib.error.URLError as exc:
            return "", f"gemini_url_error:{exc.reason}"

        candidates = response_payload.get("candidates", [])
        if not candidates:
            return "", "gemini_no_candidates"
        text = (
            candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        )
        return text, ""


# ---- OpenAI adapter ----

class OpenAIProviderAdapter:
    """Transport adapter for the OpenAI API."""

    @property
    def provider_name(self) -> str:
        return "openai"

    @staticmethod
    def _extract_response_text(payload: dict) -> str:
        """Extract text content from an OpenAI API response."""
        if isinstance(payload.get("output_text"), str) and str(payload.get("output_text")).strip():
            return str(payload.get("output_text"))
        output = payload.get("output") if isinstance(payload.get("output"), list) else []
        parts: list[str] = []
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content") if isinstance(item.get("content"), list) else []
            for row in content:
                if not isinstance(row, dict):
                    continue
                if isinstance(row.get("text"), str):
                    parts.append(str(row.get("text")))
                elif isinstance(row.get("value"), str):
                    parts.append(str(row.get("value")))
        return "\n".join([x for x in parts if x.strip()]).strip()

    def send_text_request(
        self,
        prompt: str,
        config: LLMProviderConfig,
    ) -> tuple[str, str]:
        req_payload = {
            "model": config.model,
            "input": prompt,
            "temperature": config.temperature,
        }
        req = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            data=json.dumps(req_payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {config.api_key}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=config.timeout_sec) as resp:
                response_payload = json.loads(resp.read().decode("utf-8"))
        except TimeoutError:
            return "", "openai_request_timeout"
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            if int(exc.code) == 429:
                return "", f"openai_rate_limited:{body[:180]}"
            return "", f"openai_http_error:{exc.code}:{body[:180]}"
        except urllib.error.URLError as exc:
            return "", f"openai_url_error:{exc.reason}"

        text = self._extract_response_text(response_payload)
        return text, ""


# ---- Anthropic adapter ----

class AnthropicProviderAdapter:
    """Transport adapter for the Anthropic Messages API."""

    @property
    def provider_name(self) -> str:
        return "anthropic"

    @staticmethod
    def _extract_response_text(payload: dict) -> str:
        content = payload.get("content") if isinstance(payload.get("content"), list) else []
        parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            if str(item.get("type") or "") == "text" and isinstance(item.get("text"), str):
                parts.append(str(item.get("text")))
        return "\n".join([x for x in parts if x.strip()]).strip()

    def send_text_request(
        self,
        prompt: str,
        config: LLMProviderConfig,
    ) -> tuple[str, str]:
        req_payload = {
            "model": config.model,
            "max_tokens": int(config.extra.get("max_tokens") or 1024),
            "messages": [{"role": "user", "content": prompt}],
            "temperature": config.temperature,
        }
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps(req_payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-api-key": config.api_key,
                "anthropic-version": "2023-06-01",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=config.timeout_sec) as resp:
                response_payload = json.loads(resp.read().decode("utf-8"))
        except TimeoutError:
            return "", "anthropic_request_timeout"
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            if int(exc.code) == 429:
                return "", f"anthropic_rate_limited:{body[:180]}"
            return "", f"anthropic_http_error:{exc.code}:{body[:180]}"
        except urllib.error.URLError as exc:
            return "", f"anthropic_url_error:{exc.reason}"

        text = self._extract_response_text(response_payload)
        return text, ""


# ---- adapter factory ----

_ADAPTERS: dict[str, type] = {
    "gemini": GeminiProviderAdapter,
    "openai": OpenAIProviderAdapter,
    "anthropic": AnthropicProviderAdapter,
}


def resolve_provider_adapter(
    requested_backend: str,
) -> tuple[LLMProviderAdapter, LLMProviderConfig]:
    """Resolve an LLM provider adapter and its configuration.

    Handles env bootstrap, API key lookup, model name resolution, and
    provider auto-detection. Returns an adapter instance and its config.

    Args:
        requested_backend: Explicit backend name ('gemini', 'openai', 'rule')
            or empty string for auto-detection.

    Returns:
        Tuple of (adapter, config). For 'rule' backend, returns a config
        with empty model/api_key so the caller can fall back to rule-based
        logic.

    Raises:
        ValueError: If the requested backend is unknown.
    """
    _bootstrap_env_from_repo(
        allowed_keys={
            "GOOGLE_API_KEY",
            "GEMINI_API_KEY",
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "LLM_MODEL",
            "GATEFORGE_GEMINI_MODEL",
            "GEMINI_MODEL",
            "OPENAI_MODEL",
            "ANTHROPIC_MODEL",
            "LLM_PROVIDER",
            "GATEFORGE_LIVE_PLANNER_BACKEND",
        }
    )
    requested = str(requested_backend or "").strip().lower()
    if requested == "rule":
        return GeminiProviderAdapter(), LLMProviderConfig(
            provider_name="rule", model="", api_key=""
        )

    model = (
        str(os.getenv("LLM_MODEL") or "").strip()
        or str(os.getenv("OPENAI_MODEL") or "").strip()
        or str(os.getenv("ANTHROPIC_MODEL") or "").strip()
        or str(os.getenv("GATEFORGE_GEMINI_MODEL") or "").strip()
        or str(os.getenv("GEMINI_MODEL") or "").strip()
    )
    if not model:
        raise ValueError("missing_llm_model")
    explicit = requested if requested in {"gemini", "openai", "anthropic"} else ""
    if not explicit:
        explicit = str(
            os.getenv("LLM_PROVIDER")
            or os.getenv("GATEFORGE_LIVE_PLANNER_BACKEND")
            or ""
        ).strip().lower()
    if explicit not in {"gemini", "openai", "anthropic"}:
        if OPENAI_MODEL_HINT_PATTERN.search(model):
            explicit = "openai"
        elif ANTHROPIC_MODEL_HINT_PATTERN.search(model):
            explicit = "anthropic"
        elif "gemini" in model.lower():
            explicit = "gemini"
        else:
            raise ValueError(f"unsupported_llm_model:{model}")

    if explicit == "openai":
        api_key = str(os.getenv("OPENAI_API_KEY") or "").strip()
    elif explicit == "anthropic":
        api_key = str(os.getenv("ANTHROPIC_API_KEY") or "").strip()
    else:
        api_key = str(
            os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or ""
        ).strip()
    if not api_key:
        raise ValueError(f"missing_{explicit}_api_key")

    adapter_cls = _ADAPTERS.get(explicit)
    if adapter_cls is None:
        raise ValueError(f"Unknown LLM provider: {explicit}")

    from .llm_budget import _to_float_env

    config = LLMProviderConfig(
        provider_name=explicit,
        model=model,
        api_key=api_key,
        timeout_sec=max(
            1.0, _to_float_env("GATEFORGE_AGENT_LIVE_LLM_REQUEST_TIMEOUT_SEC", 120.0)
        ),
    )
    return adapter_cls(), config
