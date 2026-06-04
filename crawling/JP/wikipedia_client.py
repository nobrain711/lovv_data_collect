"""
Wikipedia API client for Japan city acquisition.

This file handles HTTP access and page extraction helpers for MediaWiki API
responses.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Final, Protocol


WIKIPEDIA_API: Final[str] = "https://{lang}.wikipedia.org/w/api.php"
DEFAULT_USER_AGENT: Final[str] = "LovvCityAcquisition/0.1"


class WikipediaClient(Protocol):
    def fetch_page(self, lang: str, title: str) -> dict[str, Any]:
        ...


class MediaWikiClient:
    def __init__(
        self,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout: int = 20,
        request_delay_seconds: float = 0.1,
        max_retries: int = 3,
    ) -> None:
        self.user_agent = user_agent
        self.timeout = timeout
        self.request_delay_seconds = request_delay_seconds
        self.max_retries = max_retries

    def fetch_page(self, lang: str, title: str) -> dict[str, Any]:
        pages = self.fetch_pages(lang, [title])
        return pages.get(title, {"query": {"pages": []}})

    def fetch_pages(self, lang: str, titles: list[str]) -> dict[str, dict[str, Any]]:
        pages_by_title: dict[str, dict[str, Any]] = {}
        for batch in _chunks(titles, 50):
            payload = self._fetch_pages_batch(lang, batch)
            pages = payload.get("query", {}).get("pages", []) or []
            redirects = payload.get("query", {}).get("redirects", []) or []
            redirect_map = {str(item.get("from")): str(item.get("to")) for item in redirects if item.get("from")}
            response_pages = {str(page.get("title")): page for page in pages}
            for title in batch:
                resolved_title = redirect_map.get(title, title)
                page = response_pages.get(resolved_title) or response_pages.get(title)
                if page is not None:
                    pages_by_title[title] = {"query": {"pages": [page]}}
        return pages_by_title

    def _fetch_pages_batch(self, lang: str, titles: list[str]) -> dict[str, Any]:
        params = {
            "action": "query",
            "format": "json",
            "formatversion": "2",
            "redirects": "1",
            "titles": "|".join(titles),
            "prop": "extracts|coordinates|pageprops|extlinks|langlinks|categories|revisions",
            "rvprop": "content",
            "rvslots": "main",
            "exintro": "1",
            "explaintext": "1",
            "ellimit": "max",
            "lllimit": "max",
            "cllimit": "max",
        }
        url = f"{WIKIPEDIA_API.format(lang=lang)}?{urllib.parse.urlencode(params)}"
        request = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
        for attempt in range(self.max_retries + 1):
            if self.request_delay_seconds > 0:
                time.sleep(self.request_delay_seconds)
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as error:
                if error.code != 429 or attempt >= self.max_retries:
                    raise
                retry_after = error.headers.get("Retry-After")
                wait_seconds = float(retry_after) if retry_after and retry_after.isdigit() else 10.0
                time.sleep(wait_seconds)
        raise RuntimeError("Unreachable MediaWiki retry state.")


def _chunks(items: list[str], size: int) -> list[list[str]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def first_page(payload: dict[str, Any]) -> dict[str, Any]:
    pages = payload.get("query", {}).get("pages", [])
    if not pages:
        return {}
    page = pages[0]
    if page.get("missing"):
        return {}
    return page


def linked_or_same_page(
    client: WikipediaClient,
    target_lang: str,
    fallback_title: str,
    source_lang: str,
) -> dict[str, Any]:
    source_page = first_page(client.fetch_page(source_lang, fallback_title))
    linked_title = langlink_title(source_page, target_lang) or fallback_title
    return first_page(client.fetch_page(target_lang, linked_title))


def langlink_title(page: dict[str, Any], lang: str) -> str | None:
    for link in page.get("langlinks", []) or []:
        if link.get("lang") == lang and link.get("title"):
            return str(link["title"])
    return None


# File History
# 2026-06-04: Split Wikipedia API access from the CLI module.
