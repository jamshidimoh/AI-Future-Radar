import requests

import src.targeted_people_discovery as discovery


class FakeResponse:
    def __init__(self, payload=None, content=b"", status_code=200):
        self._payload = payload
        self.content = content
        self.status_code = status_code
        self.text = content.decode("utf-8", errors="replace")

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


def _pubmed_xml(*, author_last="Church", author_first="George M", initials="GM", title="Manufacturing-aware generative models enable petascale synthesis of designed DNA"):
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<PubmedArticleSet>
  <PubmedArticle>
    <MedlineCitation>
      <PMID>41844990</PMID>
      <Article>
        <ArticleTitle>{title}</ArticleTitle>
        <Abstract><AbstractText>We describe manufacturing-aware generative models for designed DNA, with a pipeline for biological synthesis and genetic engineering.</AbstractText></Abstract>
        <AuthorList><Author><LastName>{author_last}</LastName><ForeName>{author_first}</ForeName><Initials>{initials}</Initials></Author></AuthorList>
        <Journal><Title>Nature Biotechnology</Title><JournalIssue><PubDate><Year>2026</Year><Month>Mar</Month><Day>17</Day></PubDate></JournalIssue></Journal>
        <ArticleDate><Year>2026</Year><Month>Mar</Month><Day>17</Day></ArticleDate>
      </Article>
    </MedlineCitation>
  </PubmedArticle>
</PubmedArticleSet>""".encode()


def test_pubmed_fallback_returns_confirmed_author_with_provenance(monkeypatch):
    responses = [
        FakeResponse(payload={"esearchresult": {"idlist": ["41844990"]}}),
        FakeResponse(content=_pubmed_xml()),
    ]
    calls = []

    def get(url, **kwargs):
        calls.append((url, kwargs))
        return responses.pop(0)

    monkeypatch.setattr(discovery.requests, "get", get)
    items = discovery.fetch_targeted_people_items(["George Church"])

    assert len(items) == 1
    item = items[0]
    assert item["title"].startswith("Manufacturing-aware generative models")
    assert item["person_name"] == "George Church"
    assert item["author"] == "George Church"
    assert item["source_tier"] == 2
    assert item["source_name"] == "Nature Biotechnology"
    assert item["indexed_by"] == "PubMed / NCBI"
    assert item["published"] == "2026-03-17 00:00"
    assert item["canonical_url"] == "https://pubmed.ncbi.nlm.nih.gov/41844990/"
    assert calls[0][1]["params"]["term"] == "Church GM[Author]"
    assert len(calls) == 2


def test_pubmed_fallback_rejects_results_without_matching_person_author(monkeypatch):
    responses = [
        FakeResponse(payload={"esearchresult": {"idlist": ["123"]}}),
        FakeResponse(content=_pubmed_xml(author_last="Smith", author_first="John", initials="JS")),
    ]

    monkeypatch.setattr(discovery.requests, "get", lambda *_args, **_kwargs: responses.pop(0))

    assert discovery.fetch_targeted_people_items(["George Church"]) == []


def test_pubmed_fallback_fails_open_when_ncbi_is_unavailable(monkeypatch):
    def fail(*_args, **_kwargs):
        raise requests.Timeout("test timeout")

    monkeypatch.setattr(discovery.requests, "get", fail)

    assert discovery.fetch_targeted_people_items(["George Church"]) == []


def test_pubmed_fallback_does_not_query_unsupported_people(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("unsupported person should not trigger PubMed calls")

    monkeypatch.setattr(discovery.requests, "get", forbidden)

    assert discovery.fetch_targeted_people_items(["Andrew Ng", ""]) == []



def test_pubmed_fallback_rejects_same_initials_without_confirmed_forename(monkeypatch):
    responses = [
        FakeResponse(payload={"esearchresult": {"idlist": ["123"]}}),
        FakeResponse(content=_pubmed_xml(author_last="Church", author_first="Gregory M", initials="GM")),
    ]
    monkeypatch.setattr(discovery.requests, "get", lambda *_args, **_kwargs: responses.pop(0))

    assert discovery.fetch_targeted_people_items(["George Church"]) == []



def test_pubmed_fallback_rejects_preprint_journals(monkeypatch):
    payload = _pubmed_xml().replace(
        b"<Title>Nature Biotechnology</Title>",
        b"<Title>bioRxiv</Title>",
    )
    responses = [
        FakeResponse(payload={"esearchresult": {"idlist": ["41844990"]}}),
        FakeResponse(content=payload),
    ]
    monkeypatch.setattr(discovery.requests, "get", lambda *_args, **_kwargs: responses.pop(0))

    assert discovery.fetch_targeted_people_items(["George Church"]) == []
