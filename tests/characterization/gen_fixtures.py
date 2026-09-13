"""Generate deterministic characterization fixtures on the unrefactored code."""
from __future__ import annotations

import json
import random
import sys
from itertools import product
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.editorial import filter_ai_relevance  # noqa: E402
from src.semantic_dedup import _similarity  # noqa: E402
from src.unified_editorial_selection import load_editorial_contract, select_regular_portfolio  # noqa: E402

OUT = Path(__file__).resolve().parent
SEED = 20260913


def _semantic_fixture() -> dict:
    titles = [
        "OpenAI raises $6.6B to scale frontier reasoning models",
        "OpenAI secures $6.6B funding for new reasoning systems",
        "Nvidia CEO Jensen Huang says AI factories will reshape computing",
        "جنسن هوانگ مدیرعامل انویدیا از کارخانه‌های هوش مصنوعی می‌گوید",
        "Anthropic appoints new CFO amid rapid enterprise growth",
        "Anthropic names a new finance chief during expansion",
        "Google DeepMind unveils a robotics foundation model",
        "گوگل دیپ‌مایند مدل بنیادی رباتیک را معرفی کرد",
        "Microsoft launches autonomous AI agents for developers",
        "مایکروسافت عامل‌های خودکار هوش مصنوعی را عرضه کرد",
        "MIT researchers publish a paper on machine consciousness",
        "پژوهشگران ام‌آی‌تی درباره آگاهی ماشینی مقاله منتشر کردند",
        "Quantum computing startup announces a fault tolerant processor",
        "A new quantum processor improves error correction",
        "Sam Altman discusses scaling laws and AGI forecasts",
        "سم آلتمن درباره قوانین مقیاس‌پذیری و هوش عمومی گفت‌وگو کرد",
        "Meta partners with researchers on open language models",
        "متا با پژوهشگران برای مدل‌های زبانی باز همکاری می‌کند",
        "Apple invests in on-device neural network inference",
        "اپل روی استنتاج شبکه عصبی روی دستگاه سرمایه‌گذاری کرد",
        "DeepMind researchers release a protein design benchmark",
        "دیپ‌مایند معیار طراحی پروتئین را منتشر کرد",
        "Nvidia appoints a new research leader after departure",
        "انویدیا پس از خروج مدیر پژوهش، رهبر جدیدی منصوب کرد",
        "OpenAI launches an AI agent platform for science",
        "OpenAI releases a scientific agent platform",
        "Robotics researchers build a physical AI system",
        "پژوهشگران رباتیک سامانه هوش مصنوعی فیزیکی ساختند",
        "AI regulation proposal targets frontier model safety",
        "پیشنهاد تنظیم‌گری هوش مصنوعی ایمنی مدل‌های مرزی را هدف می‌گیرد",
        "Neuroscience study explores cognition and artificial awareness",
        "مطالعه علوم اعصاب شناخت و آگاهی مصنوعی را بررسی می‌کند",
        "Amazon expands generative AI infrastructure investment",
        "آمازون سرمایه‌گذاری زیرساخت هوش مصنوعی مولد را افزایش داد",
        "A university launches a course on autonomous agents",
        "دانشگاه دوره‌ای درباره عامل‌های خودمختار راه‌اندازی کرد",
        "X AI publishes a new multimodal reasoning benchmark",
        "ایکس ای‌آی معیار جدید استدلال چندوجهی را منتشر کرد",
        "Scientists report a new brain computer interface result",
        "دانشمندان نتیجه تازه‌ای درباره رابط مغز و رایانه گزارش کردند",
    ]
    pairs = [
        {"left": i, "right": j, "score": round(_similarity(a, b), 6)}
        for i, a in enumerate(titles)
        for j, b in enumerate(titles)
    ]
    raw_pairs = [
        {"left": a, "right": b, "score": round(_similarity(a, b), 6)}
        for a, b in (
            ("title a", "title b"),
            ("OpenAI launches a model", "OpenAI launches a model"),
            ("quantum processor", "brain interface"),
        )
    ]
    dict_items = [
        {"title": title, "summary": summary, "leader": leader, "numbers": numbers}
        for title, summary, leader, numbers in (
            ("OpenAI raises funding", "Frontier reasoning model investment", "Sam Altman", ["6.6"]),
            ("Anthropic appoints CFO", "Company leadership change", "", []),
            ("Nvidia AI factories", "Jensen Huang explains infrastructure", "Jensen Huang", []),
            ("Quantum chip launch", "New error correction processor", "", ["3"]),
        )
    ]
    dict_pairs = [
        {"left": i, "right": j, "score": round(_similarity(a, b), 6)}
        for i, a in enumerate(dict_items)
        for j, b in enumerate(dict_items)
    ]
    return {"titles": titles, "pairs": pairs, "raw_pairs": raw_pairs, "dict_items": dict_items, "dict_pairs": dict_pairs}


def _candidate(index: int, *, area: str, source: str, content_type: str, score: float, tier: int | None) -> dict:
    category = {
        "ai_core": "ai",
        "convergence": "quantum",
        "mind_cognition": "mind",
        "future_governance": "future",
    }[area]
    return {
        "title": f"{area.replace('_', ' ').title()} candidate {index} machine learning",
        "summary": f"Research and policy context for {area.replace('_', ' ')} candidate {index}.",
        "source": source,
        "content_type": content_type,
        "category": category,
        "mission_area": area,
        "editorial_score": score,
        "signal_score": score / 2,
        "evidence_strength": 6.0 if tier in {1, 2} else 3.0,
        "source_tier": tier,
        "published": f"2026-09-{(index % 28) + 1:02d}",
        "leader": "Jensen Huang" if index % 11 == 0 else "",
        "is_leader_watch": index % 11 == 0,
        "ai_relevance": True,
        "_ai_link": True,
        "research_signal": content_type == "research",
    }


def _selection_fixture() -> dict:
    rng = random.Random(SEED)
    candidates = [
        _candidate(0, area="ai_core", source="OpenAI", content_type="research", score=9.8, tier=3),
        _candidate(1, area="ai_core", source="Anthropic", content_type="news", score=9.4, tier=3),
        _candidate(2, area="ai_core", source="Reuters", content_type="interview", score=9.2, tier=3),
        _candidate(3, area="ai_core", source="OpenAI", content_type="news", score=8.8, tier=1),
        _candidate(4, area="convergence", source="Reuters", content_type="research", score=8.5, tier=3),
        _candidate(5, area="convergence", source="Reuters", content_type="news", score=8.0, tier=2),
        _candidate(6, area="convergence", source="Quantum Weekly", content_type="research", score=10.8, tier=3),
        _candidate(7, area="mind_cognition", source="OpenAI", content_type="research", score=9.0, tier=3),
        _candidate(8, area="mind_cognition", source="Anthropic", content_type="interview", score=8.7, tier=2),
        _candidate(9, area="future_governance", source="NIST", content_type="news", score=8.9, tier=3),
        _candidate(10, area="future_governance", source="Reuters", content_type="research", score=8.2, tier=2),
        _candidate(11, area="future_governance", source="community reddit", content_type="news", score=10.0, tier=3),
        _candidate(12, area="future_governance", source="Anthropic", content_type="research", score=6.7, tier=2),
        _candidate(13, area="convergence", source="OpenAI", content_type="research", score=6.6, tier=2),
        _candidate(14, area="ai_core", source="Reuters", content_type="news", score=5.5, tier=2),
    ]
    candidates[-1]["research_signal"] = True
    for index in range(15, 40):
        area = rng.choice(("ai_core", "convergence", "mind_cognition", "future_governance"))
        content_type = rng.choice(("news", "interview", "research", "community"))
        source = rng.choice(("OpenAI", "Anthropic", "Reuters", "community reddit"))
        tier = rng.choice((1, 2, 3))
        candidates.append(_candidate(index, area=area, source=source, content_type=content_type, score=round(rng.uniform(4.0, 8.0), 2), tier=tier))
    contract = load_editorial_contract()
    contract.update(
        convergence_target=1,
        research_target=1,
        mind_future_target=2,
        min_authoritative_items=2,
        max_same_mission_area=6,
    )
    grid = []
    reasons = set()
    for max_posts, max_per_source, max_per_type, mission_aware, strict_relevance in product(
        (3, 4, 6), (1, 2), (1, 2), (True, False), (False, True)
    ):
        selected = select_regular_portfolio(
            candidates,
            max_posts=max_posts,
            max_per_source=max_per_source,
            max_per_type=max_per_type,
            recent_source_counts={"openai": 2, "reuters": 1},
            contract=contract,
            mission_aware=mission_aware,
            strict_relevance=strict_relevance,
        )
        output = [
            [item.get("title", ""), item.get("mission_selection_reason", ""), round(float(item.get("portfolio_information_gain", 0.0)), 6)]
            for item in selected
        ]
        reasons.update(row[1] for row in output)
        grid.append(
            {
                "max_posts": max_posts,
                "max_per_source": max_per_source,
                "max_per_type": max_per_type,
                "mission_aware": mission_aware,
                "strict_relevance": strict_relevance,
                "expected": output,
            }
        )
    expected_reasons = {
        "mission_target:ai_core",
        "mission_target:convergence",
        "mission_target:mind_cognition",
        "mission_target:future_governance",
        "mission_target:research",
        "portfolio_value",
        "adaptive_source_backfill",
        "policy_repair:min_authoritative_items",
    }
    assert expected_reasons <= reasons, sorted(expected_reasons - reasons)
    return {"candidates": candidates, "contract": contract, "grid": grid, "reasons": sorted(reasons)}


def _relevance_items() -> list[dict]:
    items = [
        {"title": "OpenAI launches a new reasoning model", "summary": "Frontier capability update.", "category": "ai", "source_tier": 1},
        {"title": "Neural circuits improve machine learning", "summary": "A benchmark result.", "category": "ai", "source_tier": 2},
        {"title": "Quantum processor reaches a new milestone", "summary": "No artificial intelligence connection.", "category": "quantum", "source_tier": 1},
        {"title": "Nvidia CEO interview on AI factories", "summary": "Jensen Huang discusses infrastructure.", "content_type": "interview", "leader": "Jensen Huang", "is_leader_watch": True, "source_tier": 1},
        {"title": "Anthropic appoints a new CFO", "summary": "Dario Amodei announces leadership change.", "leader": "Dario Amodei", "is_leader_watch": True, "source_tier": 1},
        {"title": "AI governance proposal changes frontier model policy", "summary": "Regulators discuss safety.", "category": "future", "source_tier": 2},
        {"title": "AI security breach exposes an agent system", "summary": "A consequential technology incident.", "category": "ai", "source_tier": 2},
        {"title": "Quantum computing processor research", "summary": "A laboratory reports a new qubit result.", "category": "quantum", "source_tier": 1},
        {"title": "Machine learning interview with a university researcher", "summary": "An interview about neural methods.", "content_type": "interview", "source_tier": 2},
        {"title": "Institute publishes an annual technology report", "summary": "Curated source update.", "curated_discovery": True, "preferred_source": "Nature", "source_tier": 1},
        {"title": "Evidence-backed model deployment report", "summary": "Deployment details.", "evidence_text": "Machine learning evidence from the original research paper.", "source_tier": 2},
        {"title": "Brain computer interface clinical result", "summary": "Neurotechnology advances.", "category": "bci", "source_tier": 1},
        {"title": "Humanoid robot foundation model released", "summary": "Physical AI platform.", "category": "robotics", "source_tier": 1},
        {"title": "Synthetic biology protein design breakthrough", "summary": "Computational biology update.", "category": "genetics", "source_tier": 2},
        {"title": "Local gardening club meets this weekend", "summary": "Community event with no technology link.", "category": "community", "source_tier": 3},
        {"title": "A policy memo considers future of AI jobs", "summary": "Economy and governance implications.", "category": "future", "source_tier": 2},
        {"title": "AI agent data leak triggers regulatory action", "summary": "Safety incident and response.", "category": "ai", "source_tier": 1},
        {"title": "Consciousness study explores machine awareness", "summary": "Cognitive science research.", "category": "mind", "source_tier": 1},
    ]
    rng = random.Random(SEED)
    while len(items) < 40:
        index = len(items)
        topic = rng.choice(("machine learning", "neural networks", "quantum hardware", "robotics", "governance"))
        items.append(
            {
                "title": f"Synthetic report {index}: {topic}",
                "summary": f"Researchers describe a {topic} result and future implications.",
                "category": "ai" if "machine" in topic or "neural" in topic else "quantum",
                "source_tier": rng.choice((1, 2, 3)),
                "content_type": rng.choice(("news", "research", "interview")),
            }
        )
    return items


def _relevance_fixture() -> dict:
    items = _relevance_items()
    outputs = {}
    for label, keywords in (("supplied", ["machine learning", "neural"]), ("bridge_only", None)):
        result = filter_ai_relevance(items, keywords)
        outputs[label] = [
            {
                "title": item.get("title", ""),
                "relevance_reason": item.get("relevance_reason", ""),
                "ai_relevance_quality": item.get("ai_relevance_quality", ""),
                "ai_relevance_confidence": round(float(item.get("ai_relevance_confidence", 0.0)), 4),
                "evidence_strength": round(float(item.get("evidence_strength", 0.0)), 4),
                "early_inclusion": bool(item.get("early_inclusion")),
                "_ai_link": bool(item.get("_ai_link")),
            }
            for item in result
        ]
    return {"items": items, "outputs": outputs}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fixtures = {
        "semantic_similarity.json": _semantic_fixture(),
        "select_regular_portfolio.json": _selection_fixture(),
        "filter_ai_relevance.json": _relevance_fixture(),
    }
    for name, payload in fixtures.items():
        (OUT / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
