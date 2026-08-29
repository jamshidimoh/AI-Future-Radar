import os
import unittest
from unittest.mock import patch

from llm_router_light import _select_hf_model, get_quality_chain


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


if __name__ == "__main__":
    unittest.main()
