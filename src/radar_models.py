"""Core domain contracts for the Radar 2.0 migration.

These models are deliberately lightweight.  They establish stable boundaries
between discovery, story construction, evidence, generation and publication
without changing the current production execution path yet.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

ContentType = Literal[
    "news",
    "official",
    "product_news",
    "interview",
    "podcast",
    "talk",
    "lecture",
    "research",
    "paper",
    "study",
    "preprint",
    "future",
    "education",
]


@dataclass(slots=True)
class SourceItem:
    """One raw/normalized item produced by a discovery adapter."""

    source_id: str
    source_name: str
    url: str
    title: str
    summary: str = ""
    description: str = ""
    source_type: str = ""
    content_type: ContentType = "news"
    published_at: datetime | None = None
    image_url: str | None = None
    people: list[str] = field(default_factory=list)
    organizations: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Evidence:
    """A bounded, traceable support record for a story claim."""

    evidence_id: str
    source_url: str
    source_name: str
    evidence_type: Literal[
        "primary",
        "official",
        "secondary",
        "original_interview",
        "research",
        "video",
        "other",
    ] = "secondary"
    claim: str = ""
    excerpt: str = ""
    retrieved_at: datetime | None = None
    confidence: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Story:
    """Canonical editorial unit built from one or more SourceItem objects."""

    story_id: str
    canonical_title: str
    sources: list[SourceItem] = field(default_factory=list)
    evidence: list[Evidence] = field(default_factory=list)
    people: list[str] = field(default_factory=list)
    organizations: list[str] = field(default_factory=list)
    topics: list[str] = field(default_factory=list)
    content_types: list[str] = field(default_factory=list)
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None
    leader_relevance: float = 0.0
    interview_signal: float = 0.0
    research_signal: float = 0.0
    importance: float = 0.0
    relevance: float = 0.0
    evidence_quality: float = 0.0
    freshness: float = 0.0
    future_value: float = 0.0
    saturation_penalty: float = 0.0
    score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CanonicalContent:
    """User-facing content contract before Telegram-specific formatting."""

    title: str
    summary: str
    why_it_matters: str
    source_name: str
    source_url: str
    chatgpt_url: str
    content_type: str
    speaker: str | None = None
    quote: str | None = None
    image_url: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def required_fields_present(self) -> bool:
        return all(
            str(value).strip()
            for value in (
                self.title,
                self.summary,
                self.why_it_matters,
                self.source_name,
                self.source_url,
                self.chatgpt_url,
            )
        )
