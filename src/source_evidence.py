"""Bounded publisher-page extraction for source-grounded summaries."""
from __future__ import annotations

import ipaddress
import re
from contextlib import suppress
from functools import lru_cache
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

import requests

from src.source_exclusions import is_excluded_source_url

MAX_HTML_BYTES = 1_500_000
MAX_EXTRACTED_CHARS = 6_000
_TIMEOUT = (2.5, 3.5)
_MAX_REDIRECTS = 3
_REDIRECTS = {301, 302, 303, 307, 308}
_SKIP = {"script", "style", "noscript", "svg", "canvas", "iframe", "nav", "footer", "aside", "form", "button", "select", "option", "template", "header"}
_BLOCKS = {"p", "h1", "h2", "h3", "h4", "blockquote", "li", "dd"}
_VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
_GOOGLE_NEWS = {"news.google.com"}
_NON_ARTICLE = {"youtube.com", "www.youtube.com", "youtu.be", "m.youtube.com"}
_UA = "Mozilla/5.0 (compatible; AI-Future-Radar/1.0; +https://github.com/jamshidimoh/AI-Future-Radar)"


class _ArticleParser(HTMLParser):
    """Collect readable blocks and metadata, dropping navigation and active content."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip_stack = []
        self.main_depth = 0
        self.active_block = None
        self.block_parts = []
        self.blocks = []
        self.main_parts = []
        self.title_parts = []
        self.in_title = False
        self.og_title = ""
        self.description = ""
        self.seen = set()

    @staticmethod
    def clean(value):
        return re.sub(r"\s+", " ", str(value or "")).strip()

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        attr = {str(k).lower(): str(v or "").strip() for k, v in attrs}
        if self.skip_stack:
            if tag in _SKIP and tag not in _VOID:
                self.skip_stack.append(tag)
            return
        if tag in _SKIP:
            if tag not in _VOID:
                self.skip_stack.append(tag)
            return
        if tag in {"article", "main"}:
            self.main_depth += 1
        if tag == "title":
            self.in_title = True
        if tag == "meta":
            key = (attr.get("property") or attr.get("name") or attr.get("itemprop") or "").casefold()
            value = attr.get("content", "")
            if key in {"og:title", "twitter:title"} and value and not self.og_title:
                self.og_title = value
            if key in {"description", "og:description", "twitter:description"} and value and not self.description:
                self.description = value
        if tag in _BLOCKS and self.active_block is None:
            self.active_block = tag
            self.block_parts = []

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if self.skip_stack:
            if tag == self.skip_stack[-1]:
                self.skip_stack.pop()
            return
        if tag in {"article", "main"} and self.main_depth:
            self.main_depth -= 1
        if tag == "title":
            self.in_title = False
        if self.active_block == tag:
            value = self.clean(" ".join(self.block_parts))
            minimum = 8 if tag.startswith("h") else (18 if tag in {"blockquote", "li", "dd"} else 35)
            if len(value) >= minimum and value not in self.seen:
                self.blocks.append(value)
                self.seen.add(value)
            self.active_block = None
            self.block_parts = []

    def handle_data(self, data):
        if self.skip_stack or not data.strip():
            return
        if self.active_block is not None:
            self.block_parts.append(data.strip())
        if self.main_depth:
            self.main_parts.append(data.strip())
        if self.in_title:
            self.title_parts.append(data.strip())

    def result(self):
        title = self.clean(" ".join(self.title_parts)) or self.clean(self.og_title)
        description = self.clean(self.description)
        body_blocks = self.blocks
        if sum(len(x) for x in body_blocks) < 220:
            fallback = self.clean(" ".join(self.main_parts))
            if len(fallback) > sum(len(x) for x in body_blocks):
                body_blocks = [fallback]
        pieces = []
        if title:
            pieces.append(f"Article page title: {title}")
        if description:
            pieces.append(f"Publisher page description: {description}")
        body = self.clean(" ".join(body_blocks))
        if body:
            pieces.append(f"Extracted publisher text: {body}")
        return "\n".join(pieces)[:MAX_EXTRACTED_CHARS]


def _safe_http_url(value):
    raw = str(value or "").strip()
    if not raw or is_excluded_source_url(raw):
        return False
    try:
        parsed = urlsplit(raw)
        host = (parsed.hostname or "").casefold().rstrip(".")
        if parsed.scheme.casefold() not in {"http", "https"} or not host:
            return False
        if parsed.username is not None or parsed.password is not None:
            return False
        if host in _GOOGLE_NEWS or host in _NON_ARTICLE:
            return False
        if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
            return False
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = None
        if address is not None and not address.is_global:
            return False
        _ = parsed.port
        return True
    except (ValueError, TypeError):
        return False


def _read_bounded_body(response):
    chunks = []
    total = 0
    for chunk in response.iter_content(chunk_size=8192):
        if not chunk:
            continue
        remaining = MAX_HTML_BYTES - total
        if remaining <= 0:
            break
        selected = chunk[:remaining]
        chunks.append(selected)
        total += len(selected)
        if len(selected) < len(chunk) or total >= MAX_HTML_BYTES:
            break
    return b"".join(chunks)


@lru_cache(maxsize=96)
def fetch_article_text(url):
    """Fetch a direct public publisher page with strict timeout, redirect and byte caps."""
    current = str(url or "").strip()
    if not _safe_http_url(current):
        return ""
    for redirect_count in range(_MAX_REDIRECTS + 1):
        response = None
        try:
            response = requests.get(
                current,
                allow_redirects=False,
                stream=True,
                timeout=_TIMEOUT,
                headers={"User-Agent": _UA, "Accept": "text/html,application/xhtml+xml;q=0.9"},
            )
            status = int(response.status_code)
            if status in _REDIRECTS:
                location = str(response.headers.get("Location") or "").strip()
                response.close()
                if not location or redirect_count >= _MAX_REDIRECTS:
                    return ""
                target = urljoin(current, location)
                if not _safe_http_url(target):
                    return ""
                old_scheme = urlsplit(current).scheme.casefold()
                new_scheme = urlsplit(target).scheme.casefold()
                if old_scheme == "https" and new_scheme != "https":
                    return ""
                current = target
                continue
            if status != 200:
                return ""
            content_type = str(response.headers.get("Content-Type") or "").casefold()
            if content_type and not any(t in content_type for t in ("text/html", "application/xhtml+xml")):
                return ""
            body = _read_bounded_body(response)
            encoding = str(getattr(response, "encoding", "") or "utf-8")
            try:
                html = body.decode(encoding, errors="replace")
            except LookupError:
                html = body.decode("utf-8", errors="replace")
            parser = _ArticleParser()
            parser.feed(html)
            parser.close()
            return parser.result()
        except (requests.RequestException, OSError, ValueError, TypeError, RuntimeError):
            return ""
        finally:
            if response is not None:
                with suppress(Exception):
                    response.close()
    return ""


def article_text_for_item(item):
    """Return publisher-page evidence for a candidate or an empty string."""
    if not isinstance(item, dict):
        return ""
    existing = str(item.get("_source_article_text") or "").strip()
    if existing:
        return existing[:MAX_EXTRACTED_CHARS]
    url = str(item.get("canonical_url") or item.get("link") or item.get("url") or "").strip()
    if not _safe_http_url(url):
        return ""
    text = fetch_article_text(url)
    item["_source_article_fetch_attempted"] = True
    domain = urlsplit(url).hostname or "unknown"
    if text:
        item["_source_article_text"] = text
        print(f"[Source Evidence] extracted=true domain={domain} chars={len(text)}", flush=True)
    else:
        print(f"[Source Evidence] extracted=false domain={domain} fallback=rss", flush=True)
    return text
