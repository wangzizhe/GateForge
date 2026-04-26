from __future__ import annotations

import io
import os
import urllib.error
import unittest
from unittest import mock

from gateforge.llm_provider_adapter import (
    DeepSeekProviderAdapter,
    GeminiProviderAdapter,
    LLMProviderConfig,
    resolve_provider_adapter,
)


class LLMProviderAdapterTests(unittest.TestCase):
    def test_resolve_provider_adapter_detects_openai(self) -> None:
        with mock.patch("gateforge.llm_provider_adapter._bootstrap_env_from_repo", return_value=0), mock.patch.dict(
            os.environ,
            {"OPENAI_API_KEY": "sk-test", "LLM_MODEL": "gpt-5-mini"},
            clear=True,
        ):
            adapter, config = resolve_provider_adapter("")
        self.assertEqual(adapter.provider_name, "openai")
        self.assertEqual(config.provider_name, "openai")
        self.assertEqual(config.api_key, "sk-test")

    def test_resolve_provider_adapter_detects_anthropic(self) -> None:
        with mock.patch("gateforge.llm_provider_adapter._bootstrap_env_from_repo", return_value=0), mock.patch.dict(
            os.environ,
            {"ANTHROPIC_API_KEY": "anth-test", "LLM_MODEL": "claude-sonnet-4-5"},
            clear=True,
        ):
            adapter, config = resolve_provider_adapter("")
        self.assertEqual(adapter.provider_name, "anthropic")
        self.assertEqual(config.provider_name, "anthropic")
        self.assertEqual(config.api_key, "anth-test")

    def test_resolve_provider_adapter_detects_minimax(self) -> None:
        with mock.patch("gateforge.llm_provider_adapter._bootstrap_env_from_repo", return_value=0), mock.patch.dict(
            os.environ,
            {"MINIMAX_API_KEY": "minimax-test", "LLM_PROVIDER": "MiniMax", "LLM_MODEL": "MiniMax-M2.7"},
            clear=True,
        ):
            adapter, config = resolve_provider_adapter("")
        self.assertEqual(adapter.provider_name, "minimax")
        self.assertEqual(config.provider_name, "minimax")
        self.assertEqual(config.api_key, "minimax-test")
        self.assertEqual(config.extra.get("max_tokens"), 8192)
        self.assertIn("patched_model_text", str(config.extra.get("system_prompt") or ""))

    def test_resolve_provider_adapter_detects_minimax_from_anthropic_compat_env(self) -> None:
        with mock.patch("gateforge.llm_provider_adapter._bootstrap_env_from_repo", return_value=0), mock.patch.dict(
            os.environ,
            {
                "ANTHROPIC_API_KEY": "anth-minimax-test",
                "ANTHROPIC_BASE_URL": "https://api.minimaxi.com/anthropic",
                "LLM_PROVIDER": "MiniMax",
                "LLM_MODEL": "MiniMax-M2.7",
            },
            clear=True,
        ):
            adapter, config = resolve_provider_adapter("")
        self.assertEqual(adapter.provider_name, "minimax")
        self.assertEqual(config.provider_name, "minimax")
        self.assertEqual(config.api_key, "anth-minimax-test")
        self.assertEqual(config.extra.get("anthropic_base_url"), "https://api.minimaxi.com/anthropic")

    def test_resolve_provider_adapter_detects_qwen(self) -> None:
        with mock.patch("gateforge.llm_provider_adapter._bootstrap_env_from_repo", return_value=0), mock.patch.dict(
            os.environ,
            {
                "DASHSCOPE_API_KEY": "dashscope-test",
                "LLM_PROVIDER": "qwen",
                "LLM_MODEL": "qwen3.6-flash",
            },
            clear=True,
        ):
            adapter, config = resolve_provider_adapter("")
        self.assertEqual(adapter.provider_name, "qwen")
        self.assertEqual(config.provider_name, "qwen")
        self.assertEqual(config.api_key, "dashscope-test")
        self.assertEqual(config.extra.get("enable_thinking"), False)
        self.assertEqual(config.extra.get("dashscope_base_url"), "")
        self.assertIn("Do not invent new Modelica modifier names", str(config.extra.get("prompt_prefix") or ""))

    def test_resolve_provider_adapter_detects_deepseek(self) -> None:
        with mock.patch("gateforge.llm_provider_adapter._bootstrap_env_from_repo", return_value=0), mock.patch.dict(
            os.environ,
            {
                "DEEPSEEK_API_KEY": "deepseek-test",
                "LLM_PROVIDER": "deepseek",
                "LLM_MODEL": "deepseek-v4-flash",
            },
            clear=True,
        ):
            adapter, config = resolve_provider_adapter("")
        self.assertEqual(adapter.provider_name, "deepseek")
        self.assertEqual(config.provider_name, "deepseek")
        self.assertEqual(config.api_key, "deepseek-test")
        self.assertEqual(config.model, "deepseek-v4-flash")
        self.assertEqual(config.extra.get("deepseek_base_url"), "")
        self.assertEqual(config.extra.get("max_tokens"), 8192)

    def test_resolve_provider_adapter_infers_deepseek_from_model_name(self) -> None:
        with mock.patch("gateforge.llm_provider_adapter._bootstrap_env_from_repo", return_value=0), mock.patch.dict(
            os.environ,
            {
                "DEEPSEEK_API_KEY": "deepseek-test",
                "LLM_MODEL": "deepseek-v4-flash",
            },
            clear=True,
        ):
            adapter, config = resolve_provider_adapter("")
        self.assertEqual(adapter.provider_name, "deepseek")
        self.assertEqual(config.provider_name, "deepseek")
        self.assertEqual(config.api_key, "deepseek-test")

    def test_resolve_provider_adapter_requires_llm_model(self) -> None:
        with mock.patch("gateforge.llm_provider_adapter._bootstrap_env_from_repo", return_value=0), mock.patch.dict(
            os.environ,
            {"OPENAI_API_KEY": "sk-test"},
            clear=True,
        ):
            with self.assertRaisesRegex(ValueError, "missing_llm_model"):
                resolve_provider_adapter("")

    def test_gemini_503_reports_service_unavailable(self) -> None:
        adapter = GeminiProviderAdapter()
        config = LLMProviderConfig(provider_name="gemini", model="gemini-test", api_key="key")
        error = urllib.error.HTTPError(
            url="https://example.invalid",
            code=503,
            msg="Service Unavailable",
            hdrs={},
            fp=io.BytesIO(b'{"error":"high demand"}'),
        )

        with mock.patch("gateforge.llm_provider_adapter.urllib.request.urlopen", side_effect=error):
            text, err = adapter.send_text_request("prompt", config)

        self.assertEqual(text, "")
        self.assertIn("gemini_service_unavailable:503", err)

    def test_deepseek_extracts_chat_completion_content(self) -> None:
        payload = {"choices": [{"message": {"content": "{\"patched_model_text\":\"model A end A;\"}"}}]}
        self.assertEqual(
            DeepSeekProviderAdapter._extract_response_text(payload),
            "{\"patched_model_text\":\"model A end A;\"}",
        )

    def test_deepseek_503_reports_service_unavailable(self) -> None:
        adapter = DeepSeekProviderAdapter()
        config = LLMProviderConfig(provider_name="deepseek", model="deepseek-v4-flash", api_key="key")
        error = urllib.error.HTTPError(
            url="https://example.invalid",
            code=503,
            msg="Service Unavailable",
            hdrs={},
            fp=io.BytesIO(b'{"error":"server overloaded"}'),
        )

        with mock.patch("gateforge.llm_provider_adapter.urllib.request.urlopen", side_effect=error):
            text, err = adapter.send_text_request("prompt", config)

        self.assertEqual(text, "")
        self.assertIn("deepseek_service_unavailable:503", err)


if __name__ == "__main__":
    unittest.main()
