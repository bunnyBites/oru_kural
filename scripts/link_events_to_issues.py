"""
Match recent CM events to open issues using Gemini, update issue status.

Usage:
    python link_events_to_issues.py
"""

import asyncio
import json
import os
import random
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL: str = os.environ["SUPABASE_URL"]
SUPABASE_ANON_KEY: str = os.environ["SUPABASE_ANON_KEY"]
SUPABASE_SERVICE_ROLE_KEY: str = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

MIN_CONFIDENCE = 0.7
EVENTS_LOOKBACK_DAYS = 14
MAX_ISSUES = 30
MAX_EVENTS = 50

_LINK_PROMPT = """\
You are matching Tamil Nadu government actions to citizen-reported issues.
For each CM event, determine if it directly addresses any of the open issues.

Only return matches where confidence >= 0.7.
Location specificity matters — a Chennai event does NOT resolve a Coimbatore issue.

Return ONLY valid JSON. No explanation. No markdown.
Return [] if no confident matches.

Format:
[{{
  "event_id": <int>,
  "issue_id": <int>,
  "confidence": <0.0-1.0>,
  "resolution_status": "in_progress" or "resolved",
  "resolution_note": "1 sentence explaining how this event addresses the issue"
}}]

Open Issues:
{issues_json}

Recent CM Events:
{events_json}\
"""


async def backoff_sleep(attempt: int, base: float = 2.0, cap: float = 60.0) -> None:
    delay = min(base ** attempt + random.uniform(0, 1), cap)
    print(f"  Backoff: sleeping {delay:.1f}s")
    await asyncio.sleep(delay)


def _supa_headers(key: str) -> dict[str, str]:
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


async def fetch_open_issues(client: httpx.AsyncClient) -> list[dict[str, Any]]:
    resp = await client.get(
        f"{SUPABASE_URL}/rest/v1/issues",
        params={
            "status": "in.(open,acknowledged,in_progress)",
            "order": "voice_count.desc",
            "select": "id,title,summary,category,location,voice_count,status",
            "limit": str(MAX_ISSUES),
        },
        headers={
            "apikey": SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


async def fetch_unlinked_events(client: httpx.AsyncClient) -> list[dict[str, Any]]:
    cutoff = (datetime.now(tz=timezone.utc) - timedelta(days=EVENTS_LOOKBACK_DAYS)).isoformat()
    resp = await client.get(
        f"{SUPABASE_URL}/rest/v1/cm_events",
        params={
            "linked_issue_id": "is.null",
            "scraped_at": f"gte.{cutoff}",
            "order": "event_date.desc",
            "select": "id,title,description,location,department,category,event_date,source_url",
            "limit": str(MAX_EVENTS),
        },
        headers={
            "apikey": SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


async def match_with_gemini(
    issues: list[dict[str, Any]],
    events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    from google import genai

    model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    prompt = _LINK_PROMPT.format(
        issues_json=json.dumps(issues, ensure_ascii=False),
        events_json=json.dumps(events, ensure_ascii=False),
    )

    for attempt in range(4):
        try:
            response = await client.aio.models.generate_content(model=model_name, contents=prompt)
            text = response.text.strip()
            if text.startswith("```"):
                lines = text.splitlines()
                text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            return json.loads(text)
        except Exception as exc:
            exc_str = str(exc)
            if "ResourceExhausted" in type(exc).__name__ or "resource_exhausted" in exc_str.lower():
                print("  Gemini quota exhausted — sleeping 60s…")
                await asyncio.sleep(60)
            else:
                print(f"  Gemini match call failed (attempt {attempt + 1}): {exc}")
                if attempt < 3:
                    await backoff_sleep(attempt)
                else:
                    raise

    raise RuntimeError("Gemini matching failed after 4 attempts")


async def apply_match(client: httpx.AsyncClient, match: dict[str, Any]) -> None:
    event_id = match["event_id"]
    issue_id = match["issue_id"]
    status = match.get("resolution_status", "in_progress")
    note = match.get("resolution_note", "")

    resp = await client.patch(
        f"{SUPABASE_URL}/rest/v1/issues",
        params={"id": f"eq.{issue_id}"},
        json={
            "status": status,
            "linked_event_id": event_id,
            "resolution_note": note,
            "last_updated_at": datetime.now(timezone.utc).isoformat(),
        },
        headers={**_supa_headers(SUPABASE_SERVICE_ROLE_KEY), "Prefer": "return=minimal"},
        timeout=15,
    )
    if not resp.is_success:
        print(f"  warning: failed to update issue {issue_id}: {resp.text}")
        return

    resp = await client.patch(
        f"{SUPABASE_URL}/rest/v1/cm_events",
        params={"id": f"eq.{event_id}"},
        json={"linked_issue_id": issue_id},
        headers={**_supa_headers(SUPABASE_SERVICE_ROLE_KEY), "Prefer": "return=minimal"},
        timeout=15,
    )
    if not resp.is_success:
        print(f"  warning: failed to update cm_event {event_id}: {resp.text}")


async def main() -> None:
    supabase_url = os.environ["SUPABASE_URL"].rstrip("/").removesuffix("/rest/v1")
    service_key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

    run_id: int | None = None
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{supabase_url}/rest/v1/scrape_runs",
                json={"script": "link_events_to_issues", "status": "running"},
                headers={**_supa_headers(service_key), "Prefer": "return=representation"},
                timeout=15,
            )
            resp.raise_for_status()
            run_id = resp.json()[0]["id"]
        except Exception as exc:
            print(f"warning: scrape_runs tracking unavailable: {exc}")

    try:
        async with httpx.AsyncClient() as client:
            print("Fetching open issues…")
            issues = await fetch_open_issues(client)
            print(f"  found {len(issues)} active issues")

            print("Fetching recent unlinked CM events…")
            events = await fetch_unlinked_events(client)
            print(f"  found {len(events)} unlinked events")

            if not issues or not events:
                print("No issues or events to match. Exiting.")
                return

            print("Matching with Gemini…")
            matches = await match_with_gemini(issues, events)
            confident = [m for m in matches if m.get("confidence", 0) >= MIN_CONFIDENCE]
            print(f"  {len(confident)} confident matches (>= {MIN_CONFIDENCE})")

            for match in confident:
                await apply_match(client, match)
                print(
                    f"  Linked: Issue #{match['issue_id']}"
                    f" → Event #{match['event_id']}"
                    f" Status: {match.get('resolution_status')} | Confidence: {match.get('confidence')}"
                )

        print(f"Done. Checked {len(issues)} issues against {len(events)} events. Found {len(confident)} confident matches. Updated {len(confident)} issues.")

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
                            "tweets_upserted": len(confident),
                        },
                        headers={**_supa_headers(service_key), "Prefer": "return=minimal"},
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
                        headers={**_supa_headers(service_key), "Prefer": "return=minimal"},
                        timeout=15,
                    )
                except Exception as exc:
                    print(f"warning: failed to mark scrape_run as failed: {exc}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
