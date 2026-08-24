import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from editorial import filter_ai_relevance

class DomainRegressionTests(unittest.TestCase):
    def check(self, title, summary, category="ai", **extra):
        item={"title":title,"summary":summary,"category":category,"content_type":"research","source":"Test","source_tier":1}
        item.update(extra)
        return filter_ai_relevance([item],["AI","AGI","machine learning"])

    def test_pure_quantum_rejected(self):
        self.assertEqual(self.check("Holonomic quantum gates","Quantum optimization and error correction." ,"quantum"),[])

    def test_quantum_ai_kept(self):
        x=self.check("Quantum machine learning","A hybrid quantum-classical model improves an AI benchmark.","quantum")[0]
        self.assertEqual(x["topic_family"],"quantum_ai")

    def test_consciousness_ai_kept(self):
        x=self.check("Machine consciousness and AI","Computational models connect consciousness with artificial intelligence.","consciousness")[0]
        self.assertEqual(x["topic_family"],"consciousness_cognition")

    def test_consciousness_without_tech_rejected(self):
        self.assertEqual(self.check("Philosophy of consciousness","A discussion of qualia only.","philosophy"),[])

    def test_future_ai_kept(self):
        x=self.check("The future of AI","Forecasts for AGI, robotics and long-term technology.","future")[0]
        self.assertEqual(x["topic_family"],"future_technology")

    def test_irrelevant_health_rejected(self):
        self.assertEqual(self.check("Healthcare is failing women","A health policy discussion with no AI link.","health"),[])

    def test_youtube_evidence_text_reaches_ai_gate(self):
        x=self.check(
            "Interview with a technology researcher",
            "",
            evidence_text="The discussion covers artificial intelligence, AI agents and reasoning models.",
            content_type="podcast",
            source="YouTube - Test AI",
        )[0]
        self.assertEqual(x["topic_family"],"ai_core")
        self.assertEqual(x["relevance_reason"],"ai_evidence")

if __name__=="__main__": unittest.main()
