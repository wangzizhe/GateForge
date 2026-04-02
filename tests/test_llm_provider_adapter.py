from __future__ import annotations

import os
import unittest
from unittest import mock

from gateforge.llm_provider_adapter import resolve_provider_adapter


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

    def test_resolve_provider_adapter_requires_llm_model(self) -> None:
        with mock.patch("gateforge.llm_provider_adapter._bootstrap_env_from_repo", return_value=0), mock.patch.dict(
            os.environ,
            {"OPENAI_API_KEY": "sk-test"},
            clear=True,
        ):
            with self.assertRaisesRegex(ValueError, "missing_llm_model"):
                resolve_provider_adapter("")


if __name__ == "__main__":
    unittest.main()
