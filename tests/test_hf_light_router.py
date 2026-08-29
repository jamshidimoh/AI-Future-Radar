import os
import unittest
from unittest.mock import patch

from llm_router_light import _select_hf_model, call_llm_with_fallback, get_quality_chain


class HuggingFaceLightRouterTests(unittest.TestCase):
    def test_free_first_rejects_paid_explicit_model(self):
        models = [
            {"id": "paid-model", "free": False, "structured": True, "providers": 4, "throughput": 100, "latency": 10, "context": 10000},
            {"id": "qwen/free-model", "free": True, "structured": True, "providers": 2, "throughput": 80, "latency": 20, "context": 8000},
        ]
        with patch.dict(os.environ, {"HF_POLICY": "free-first", "HF_MODEL": "paid-model"}, clear=False), patch("llm_router_light._discover_hf_models", return_value=models):
            self.assertEqual(_select_hf_model(), "qwen/free-model")

    def test_free_first_selects_free_model_when_no_explicit_model(self):
        models = [
            {"id": "other/free-model", "free": True, "structured": True, "providers": 1, "throughput": 20, "latency": 30, "context": 4000},
            {"id": "qwen/free-model", "free": True, "structured": True, "providers": 1, "throughput": 20, "latency": 30, "context": 4000},
        ]
        with patch.dict(os.environ, {"HF_POLICY": "free-first", "HF_MODEL": ""}, clear=False), patch("llm_router_light._discover_hf_models", return_value=models):
            self.assertEqual(_select_hf_model(), "qwen/free-model")

    def test_huggingface_is_last_fallback(self):
        names = [name for name, _ in get_quality_chain()]
        self.assertEqual(names[-1], "HuggingFace")

    def test_missing_credentials_are_skipped_without_provider_calls(self):
        env = {
            "GROQ_API_KEY": "",
            "GEMINI_API_KEY": "",
            "OPENROUTER_API_KEY": "",
            "HF_TOKEN": "",
        }
        calls = []

        def provider(*_args):
            calls.append(True)
            return "unexpected"

        providers = [("Groq:qwen/qwen3.6-27b", provider), ("Gemini", provider), ("OpenRouter:openai/gpt-oss-120b:free", provider), ("HuggingFace", provider)]
        with patch.dict(os.environ, env, clear=False):
            result, provider_name = call_llm_with_fallback("system", "user", providers=providers)
        self.assertIsNone(result)
        self.assertIsNone(provider_name)
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
