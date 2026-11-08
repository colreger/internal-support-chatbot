"""Search public webpages through the Brave Search API."""
import os
from urllib.parse import urlsplit

import httpx


def search_web(query: str) -> dict:
    """Search the public web for current information and return up to three sources."""
    query = query.strip()
    if not 1 <= len(query) <= 400:
        raise ValueError("Die Websuche erwartet 1 bis 400 Zeichen.")
    key = os.getenv("BRAVE_SEARCH_API_KEY")
    if not key:
        raise ValueError("Für die Websuche fehlt BRAVE_SEARCH_API_KEY.")
    try:
        response = httpx.get(
            "https://api.search.brave.com/res/v1/web/search",
            params={"q": query, "count": 3, "result_filter": "web"},
            headers={"X-Subscription-Token": key, "Accept": "application/json"},
            timeout=10,
        )
        response.raise_for_status()
        hits = response.json().get("web", {}).get("results", [])
    except (httpx.HTTPError, ValueError) as exc:
        raise ValueError("Die Anfrage an Brave Search ist fehlgeschlagen.") from exc

    return {"sources": [
        {"title": hit["title"][:200], "url": hit["url"], "snippet": hit.get("description", "")[:600]}
        for hit in hits[:3] if urlsplit(hit["url"]).scheme in ("http", "https")
    ]}
