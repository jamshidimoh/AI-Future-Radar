"""Strategic forecast and long-horizon importance scoring for AI Future Radar."""
from __future__ import annotations

FORECAST_TERMS = {
    "5 years", "within five years", "in five years", "over the next five years",
    "next five years", "next decade", "10 years", "within a decade", "six months",
    "6 months", "within months", "by 2030", "by 2035", "by 2040", "timeline",
    "forecast", "predict", "prediction", "will become", "will be able to", "years from now",
}
FRONTIER_STRATEGIC_TERMS = {
    "1000-step", "1000 step", "long-horizon reasoning", "long horizon reasoning",
    "strategic reasoning", "multi-agent", "multi agent", "agent swarm", "agentic",
    "infinite context", "long context", "persistent memory", "world model",
    "autonomous research", "autonomous systems", "recursive self-improvement",
    "superintelligence", "agi", "general intelligence", "reasoning model",
}
RISK_TERMS = {
    "ai risk", "existential risk", "catastrophic risk", "strategic risk", "national security",
    "infrastructure risk", "control problem", "loss of control", "human control", "alignment",
    "misalignment", "shutdown", "pull the plug", "unplug", "regulation", "governance",
    "arms race", "security threat", "safety threat", "dangerous capabilities", "power-seeking",
}
INFLUENTIAL_PEOPLE = {
    "eric schmidt", "sam altman", "dario amodei", "demis hassabis", "jensen huang",
    "andrew ng", "ilya sutskever", "andrej karpathy", "geoffrey hinton", "yann lecun",
    "yoshua bengio", "nick bostrom", "max tegmark", "stuart russell", "ray kurzweil",
    "mustafa suleyman", "satya nadella", "sundar pichai", "mark zuckerberg", "elon musk",
}


def strategic_forecast_score(item: dict) -> float:
    """Return a bounded strategic-importance score independent of watchlist membership."""
    text = " ".join(str(item.get(k) or "") for k in ("title", "summary", "description", "why_it_matters")).casefold()
    people_hits = sum(1 for person in INFLUENTIAL_PEOPLE if person in text)
    forecast_hits = sum(1 for term in FORECAST_TERMS if term in text)
    frontier_hits = sum(1 for term in FRONTIER_STRATEGIC_TERMS if term in text)
    risk_hits = sum(1 for term in RISK_TERMS if term in text)
    interview = str(item.get("content_type") or "").casefold() in {"interview", "podcast", "talk", "fireside", "conversation", "discussion", "q&a"}

    score = 0.0
    score += min(8.0, people_hits * 4.0)
    score += min(8.0, forecast_hits * 2.0)
    score += min(10.0, frontier_hits * 2.5)
    score += min(10.0, risk_hits * 2.5)
    if interview and (forecast_hits or frontier_hits or risk_hits):
        score += 4.0

    score = min(30.0, score)
    item["strategic_forecast_score"] = round(score, 2)
    item["strategic_forecast_signal"] = score >= 8.0
    item["strategic_risk_signal"] = risk_hits > 0
    item["influential_person_signal"] = people_hits > 0
    return score
