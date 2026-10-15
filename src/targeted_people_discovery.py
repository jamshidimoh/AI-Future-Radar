"""Authoritative PubMed fallback for a narrowly scoped People Bootstrap gap.

This adapter never manufactures publication state: it returns only records from
NCBI PubMed whose author list confirms the watched person. Each item still flows
through the ordinary evidence, language, editorial, duplicate and delivery gates.
"""
from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Any

import requests

logger = logging.getLogger(__name__)

EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
TARGETED_AUTHOR_QUERIES = {
    "george church": "Church GM[Author]",
}
DEFAULT_TIMEOUT_SECONDS = 8.0
MAX_RESULTS = 8


def _element_text(node: ET.Element | None) -> str:
    if node is None:
        return ""
    return " ".join(" ".join(node.itertext()).split()).strip()


def _pubdate(article: ET.Element) -> str:
    date_nodes = [
        article.find("./MedlineCitation/Article/ArticleDate"),
        article.find("./MedlineCitation/Article/Journal/JournalIssue/PubDate"),
        article.find("./PubmedData/History/PubMedPubDate"),
    ]
    for node in date_nodes:
        if node is None:
            continue
        year = _element_text(node.find("./Year"))
        month = _element_text(node.find("./Month"))
        day = _element_text(node.find("./Day"))
        medline_date = _element_text(node.find("./MedlineDate"))
        if not year and medline_date:
            match = re.search(r"\b(19\d{2}|20\d{2})\b", medline_date)
            year = match.group(1) if match else ""
            if not month:
                month_match = re.search(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b", medline_date, re.I)
                month = month_match.group(1) if month_match else ""
        if not year:
            continue
        try:
            month_number = datetime.strptime(month[:3].title(), "%b").month if month and not month.isdigit() else int(month or 1)
            day_number = int(day or 1)
            parsed = datetime(int(year), month_number, day_number)
        except (TypeError, ValueError, OverflowError):
            try:
                parsed = datetime(int(year), 1, 1)
            except (TypeError, ValueError, OverflowError):
                continue
        return parsed.strftime("%Y-%m-%d 00:00")
    return ""


def _confirmed_author(article: ET.Element, person: str) -> tuple[bool, str]:
    target = str(person or "").strip().casefold()
    author_names: list[str] = []
    confirmed = False
    for author in article.findall("./MedlineCitation/Article/AuthorList/Author"):
        collective = _element_text(author.find("./CollectiveName"))
        surname = _element_text(author.find("./LastName"))
        forename = _element_text(author.find("./ForeName"))
        initials = re.sub(r"[^A-Za-z]", "", _element_text(author.find("./Initials"))).upper()
        if collective:
            author_names.append(collective)
        elif surname:
            display = " ".join(part for part in (forename, surname) if part)
            author_names.append(display or surname)
        if (
            target == "george church"
            and surname.casefold() == "church"
            and forename.casefold().startswith("george")
        ):
            confirmed = True
    return confirmed, "; ".join(author_names)


def fetch_targeted_people_items(
    people: list[str],
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    max_results: int = MAX_RESULTS,
) -> list[dict[str, Any]]:
    """Fetch recent PubMed citations for supported undelivered watched experts.

    External failures are fail-open for normal news production (return no items),
    while author matching, source identity and all editorial gates remain strict.
    """
    items: list[dict[str, Any]] = []
    requested = {
        str(person).strip().casefold(): str(person).strip()
        for person in (people or [])
        if str(person).strip().casefold() in TARGETED_AUTHOR_QUERIES
    }
    for normalized, person in requested.items():
        try:
            response = requests.get(
                f"{EUTILS_BASE}/esearch.fcgi",
                params={
                    "db": "pubmed",
                    "term": TARGETED_AUTHOR_QUERIES[normalized],
                    "retmax": str(max(1, min(int(max_results), 20))),
                    "sort": "pub date",
                    "retmode": "json",
                },
                timeout=timeout,
                headers={"User-Agent": "AI-Future-Radar/1.0 (research discovery; contact: project maintainer)"},
            )
            response.raise_for_status()
            search_data = response.json()
            search_result = search_data.get("esearchresult", {}) if isinstance(search_data, dict) else {}
            identifiers = [str(value) for value in search_result.get("idlist", []) if str(value).isdigit()]
            if not identifiers:
                logger.info("Targeted PubMed discovery returned no identifiers for person=%s", person)
                continue

            article_response = requests.get(
                f"{EUTILS_BASE}/efetch.fcgi",
                params={"db": "pubmed", "id": ",".join(identifiers), "retmode": "xml"},
                timeout=timeout,
                headers={"User-Agent": "AI-Future-Radar/1.0 (research discovery; contact: project maintainer)"},
            )
            article_response.raise_for_status()
            root = ET.fromstring(article_response.content)
            for record in root.findall("./PubmedArticle"):
                pmid = _element_text(record.find("./MedlineCitation/PMID"))
                article = record.find("./MedlineCitation/Article")
                if not pmid or article is None:
                    continue
                confirmed, authors = _confirmed_author(record, person)
                if not confirmed:
                    logger.warning("Targeted PubMed candidate rejected: author identity did not match person=%s pmid=%s", person, pmid)
                    continue
                title = _element_text(article.find("./ArticleTitle"))
                if not title:
                    continue
                abstract_parts = [
                    _element_text(section)
                    for section in article.findall("./Abstract/AbstractText")
                    if _element_text(section)
                ]
                abstract = " ".join(abstract_parts).strip()
                journal = _element_text(article.find("./Journal/Title")) or "PubMed-indexed journal"
                published = _pubdate(record)
                link = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
                content = abstract or title
                items.append(
                    {
                        "title": title,
                        "summary": content[:6000],
                        "description": content[:10000],
                        "author": person,
                        "authors": authors,
                        "person_name": person,
                        "watch_person": person,
                        "leader": person,
                        "publisher": journal,
                        "source": "PubMed / NCBI",
                        "source_name": "PubMed / NCBI",
                        "source_url": "https://pubmed.ncbi.nlm.nih.gov/",
                        "source_tier": 1,
                        "tier": 1,
                        "official": True,
                        "provenance_url": link,
                        "link": link,
                        "url": link,
                        "canonical_url": link,
                        "published": published,
                        "content_type": "research",
                        "category": "genetics",
                        "topic_family": "bio",
                        "discovery_method": "targeted_pubmed_author_fallback",
                    }
                )
        except (requests.RequestException, ValueError, TypeError, AttributeError, ET.ParseError) as exc:
            logger.warning("Targeted PubMed discovery failed for person=%s error=%s", person, type(exc).__name__)
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for item in sorted(items, key=lambda row: (str(row.get("published") or ""), str(row.get("title") or "")), reverse=True):
        marker = str(item.get("canonical_url") or item.get("link") or "")
        if marker and marker not in seen:
            seen.add(marker)
            unique.append(item)
    return unique
