"""
Scrape TN Government and The Hindu TN RSS feeds, enrich with Gemini, upsert to Supabase.

Usage:
    python scrape_cm_events.py
"""

import asyncio
import json
import os
import random
import re
from datetime import datetime, timezone
from typing import Any

import feedparser
import httpx
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL: str = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_ROLE_KEY: str = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

RSS_FEEDS: list[tuple[str, str]] = [
    ("https://www.tn.gov.in/rss/pressrelease.xml", "TN Government"),
    ("https://www.thehindu.com/news/national/tamil-nadu/?service=rss", "The Hindu TN"),
]

# HTML sources scraped directly (no RSS available)
# Each entry: (url, source_name)
HTML_SOURCES: list[tuple[str, str]] = [
    ("https://chennai.nic.in/category/press-release/", "Chennai District"),
    ("https://tn.nic.in/events/", "TN NIC Events"),
]

ENRICH_BATCH_SIZE = 20

_ENRICH_PROMPT = """\
You are analyzing Tamil Nadu government press releases and news articles.
Context (2026): CM is Vijay (TVK party). Key active schemes: Vetri Nichayam, Tamizh Pudhalvan,
Neengal Nalama, Vetri TN Super App, Mudhalvar Makkal Sevai Nanbar.

For each article, extract:
- location: specific place in Tamil Nadu mentioned, or null
- department: relevant government department (e.g. "PWD", "Health Dept"), or null
- category: one of [Infrastructure, Health, Education, Welfare Scheme, Public Event, Other]

Return ONLY valid JSON. No explanation. No markdown.
Format:
[{{"index": <int>, "location": "<str or null>", "department": "<str or null>", "category": "<str>"}}]

Articles:
{articles_json}\
"""


async def backoff_sleep(attempt: int, base: float = 2.0, cap: float = 60.0) -> None:
    delay = min(base ** attempt + random.uniform(0, 1), cap)
    print(f"  Backoff: sleeping {delay:.1f}s")
    await asyncio.sleep(delay)


def parse_feeds() -> list[dict[str, Any]]:
    """Parse all RSS feeds synchronously (feedparser is sync). Returns normalized event dicts."""
    events: list[dict[str, Any]] = []
    for url, source_name in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            print(f"  {source_name}: {len(feed.entries)} entries")
            for entry in feed.entries:
                source_url = entry.get("link", "").strip()
                if not source_url:
                    continue
                published = entry.get("published_parsed") or entry.get("updated_parsed")
                event_date: str | None = None
                if published:
                    event_date = datetime(*published[:6]).isoformat() + "Z"
                events.append({
                    "title": entry.get("title", "").strip(),
                    "description": entry.get("summary", "").strip()[:1000],
                    "event_date": event_date,
                    "source_url": source_url,
                    "source_name": source_name,
                    "location": None,
                    "department": None,
                    "category": None,
                })
        except Exception as exc:
            print(f"  warning: failed to parse {source_name}: {exc}")
    return events


async def scrape_html_sources(client: httpx.AsyncClient) -> list[dict[str, Any]]:
    """Scrape HTML press-release pages that lack RSS feeds."""
    events: list[dict[str, Any]] = []
    for url, source_name in HTML_SOURCES:
        try:
            resp = await client.get(url, timeout=20, follow_redirects=True,
                                    headers={"User-Agent": "OruKural/2.0 civic-dashboard"})
            if not resp.is_success:
                print(f"  {source_name}: HTTP {resp.status_code} — skipping")
                continue
            html = resp.text
            # Extract <a href="...">...</a> pairs from article/post listings.
            # Both chennai.nic.in (WordPress) and tn.nic.in use anchor-based listings.
            anchors = re.findall(
                r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
                html, re.DOTALL | re.IGNORECASE
            )
            seen: set[str] = set()
            for href, raw_title in anchors:
                title = re.sub(r"<[^>]+>", "", raw_title).strip()
                # Skip navigation links, empty titles, and off-domain URLs
                if (not title or len(title) < 10
                        or href in seen
                        or href.startswith("#")
                        or ("http" in href and source_name.split()[0].lower() not in href)):
                    continue
                seen.add(href)
                full_url = href if href.startswith("http") else url.rstrip("/") + "/" + href.lstrip("/")
                events.append({
                    "title": title[:300],
                    "description": "",
                    "event_date": None,
                    "source_url": full_url,
                    "source_name": source_name,
                    "location": None,
                    "department": None,
                    "category": None,
                })
            print(f"  {source_name}: {len(seen)} entries")
        except Exception as exc:
            print(f"  warning: failed to scrape {source_name}: {exc}")
    return events


async def enrich_with_gemini(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Add location, department, category to events via Gemini Flash."""
    from google import genai

    model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    for batch_start in range(0, len(events), ENRICH_BATCH_SIZE):
        batch = events[batch_start : batch_start + ENRICH_BATCH_SIZE]
        payload = [
            {"index": i, "title": e["title"], "description": e["description"]}
            for i, e in enumerate(batch)
        ]
        prompt = _ENRICH_PROMPT.format(articles_json=json.dumps(payload, ensure_ascii=False))

        for attempt in range(4):
            try:
                response = await client.aio.models.generate_content(model=model_name, contents=prompt)
                text = response.text.strip()
                if text.startswith("```"):
                    lines = text.splitlines()
                    text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
                results = json.loads(text)
                for result in results:
                    idx = result.get("index", 0)
                    if 0 <= idx < len(batch):
                        batch[idx]["location"] = result.get("location")
                        batch[idx]["department"] = result.get("department")
                        batch[idx]["category"] = result.get("category", "Other")
                break
            except Exception as exc:
                exc_str = str(exc)
                if "ResourceExhausted" in type(exc).__name__ or "resource_exhausted" in exc_str.lower():
                    print("  Gemini quota exhausted — sleeping 60s…")
                    await asyncio.sleep(60)
                else:
                    print(f"  Gemini enrich batch failed (attempt {attempt + 1}): {exc}")
                    if attempt < 3:
                        await backoff_sleep(attempt)
                    else:
                        for event in batch:
                            event.setdefault("category", "Other")
                        break

    return events


async def upsert_events(client: httpx.AsyncClient, events: list[dict[str, Any]]) -> int:
    if not events:
        return 0
    resp = await client.post(
        f"{SUPABASE_URL}/rest/v1/cm_events",
        json=events,
        headers={
            "apikey": SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates",
        },
        timeout=30,
    )
    if not resp.is_success:
        raise RuntimeError(f"Supabase upsert cm_events {resp.status_code}: {resp.text}")
    return len(events)


async def main() -> None:
    supabase_url = os.environ["SUPABASE_URL"].rstrip("/").removesuffix("/rest/v1")
    service_key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

    run_id: int | None = None
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{supabase_url}/rest/v1/scrape_runs",
                json={"script": "scrape_cm_events", "status": "running"},
                headers={
                    "apikey": service_key,
                    "Authorization": f"Bearer {service_key}",
                    "Content-Type": "application/json",
                    "Prefer": "return=representation",
                },
                timeout=15,
            )
            resp.raise_for_status()
            run_id = resp.json()[0]["id"]
        except Exception as exc:
            print(f"warning: scrape_runs tracking unavailable: {exc}")

    try:
        print("Parsing RSS feeds…")
        events = parse_feeds()

        print("Scraping HTML sources…")
        async with httpx.AsyncClient() as html_client:
            html_events = await scrape_html_sources(html_client)
        events.extend(html_events)
        print(f"  total raw events: {len(events)}")

        if not events:
            print("No events found — exiting.")
            return

        print("Enriching with Gemini…")
        events = await enrich_with_gemini(events)

        print("Upserting to Supabase…")
        async with httpx.AsyncClient() as client:
            upserted = await upsert_events(client, events)
        print(f"Done. Upserted: {upserted} events.")

        if run_id is not None:
            async with httpx.AsyncClient() as tc:
                try:
                    await tc.patch(
                        f"{supabase_url}/rest/v1/scrape_runs",
                        params={"id": f"eq.{run_id}"},
                        json={
                            "status": "completed",
                            "completed_at": datetime.now(timezone.utc).isoformat(),
                            "tweets_fetched": len(events),
                            "tweets_upserted": upserted,
                        },
                        headers={
                            "apikey": service_key,
                            "Authorization": f"Bearer {service_key}",
                            "Content-Type": "application/json",
                            "Prefer": "return=minimal",
                        },
                        timeout=15,
                    )
                except Exception as exc:
                    print(f"warning: failed to complete scrape_run: {exc}")

    except Exception as e:
        if run_id is not None:
            async with httpx.AsyncClient() as tc:
                try:
                    await tc.patch(
                        f"{supabase_url}/rest/v1/scrape_runs",
                        params={"id": f"eq.{run_id}"},
                        json={
                            "status": "failed",
                            "completed_at": datetime.now(timezone.utc).isoformat(),
                            "error_message": str(e),
                        },
                        headers={
                            "apikey": service_key,
                            "Authorization": f"Bearer {service_key}",
                            "Content-Type": "application/json",
                            "Prefer": "return=minimal",
                        },
                        timeout=15,
                    )
                except Exception as exc:
                    print(f"warning: failed to mark scrape_run as failed: {exc}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
