"""
Cluster unclustered signals into Issues using Gemini, then persist to Supabase.

Fetches signals where issue_id IS NULL and category is actionable,
groups them semantically into Issues (merging with existing open Issues),
upserts to issues table, populates signal_issue_map, sets signals.issue_id.

Usage:
    python cluster_issues.py
"""

import asyncio
import json
import os
import random
from datetime import datetime
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

BATCH_SIZE = 30
CLUSTER_CATEGORIES = ["Infrastructure", "Health", "Education", "Demand", "Complaint"]
MAX_EXISTING_ISSUES = 50

_CLUSTER_PROMPT = """\
You are analyzing Tamil Nadu public posts mentioning the Chief Minister (@CMOTamilnadu).
Posts may be from X (Twitter) or Reddit — treat them identically.

TASK 1 — GROUP new posts into issues:
Group posts that describe the SAME specific problem or demand.
Do NOT merge issues from different locations even if the topic matches.

TASK 2 — MERGE with existing issues where appropriate:
If a group clearly matches an existing open issue (same topic + same location),
return that issue's id as existing_issue_id instead of creating a new one.

For each group return:
- existing_issue_id: integer if merging, null if new
- title: concise English title max 10 words (only if new — omit if merging)
- summary: 1-2 sentence synthesis of citizen demand (only if new — omit if merging)
- category: one of [Infrastructure, Health, Education, Demand, Complaint, Other]
- location: specific location or null
- department: relevant govt department or null
- signal_ids: list of signal IDs in this group

Return ONLY valid JSON. No explanation. No markdown.
Format:
[{{
  "existing_issue_id": null,
  "title": "...",
  "summary": "...",
  "category": "...",
  "location": "...",
  "department": "...",
  "signal_ids": ["id1", "id2"]
}}]

Existing open issues (for merge context):
{existing_issues_json}

New posts to cluster:
{signals_json}\
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


async def fetch_unclustered_signals(client: httpx.AsyncClient, anon_key: str, supabase_url: str) -> list[dict[str, Any]]:
    cats = ",".join(f'"{c}"' for c in CLUSTER_CATEGORIES)
    resp = await client.get(
        f"{supabase_url}/rest/v1/signals",
        params={
            "issue_id": "is.null",
            "category": f"in.({cats})",
            "order": "posted_at.desc",
            "select": "id,content,translated_content,category,source,score,posted_at,author_handle",
            "limit": "200",
        },
        headers={
            "apikey": anon_key,
            "Authorization": f"Bearer {anon_key}",
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


async def fetch_open_issues(client: httpx.AsyncClient, anon_key: str, supabase_url: str) -> list[dict[str, Any]]:
    resp = await client.get(
        f"{supabase_url}/rest/v1/issues",
        params={
            "status": "neq.resolved",
            "order": "last_updated_at.desc",
            "select": "id,title,summary,category,location,voice_count,status",
            "limit": str(MAX_EXISTING_ISSUES),
        },
        headers={
            "apikey": anon_key,
            "Authorization": f"Bearer {anon_key}",
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


async def cluster_with_gemini(
    signals: list[dict[str, Any]],
    existing_issues: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    from google import genai

    model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    signals_payload = [
        {
            "id": s["id"],
            "content": s.get("translated_content") or s["content"],
            "category": s["category"],
            "source": s.get("source", "x"),
        }
        for s in signals
    ]
    issues_payload = [
        {"id": i["id"], "title": i["title"], "summary": i["summary"], "location": i["location"]}
        for i in existing_issues
    ]

    prompt = _CLUSTER_PROMPT.format(
        existing_issues_json=json.dumps(issues_payload, ensure_ascii=False),
        signals_json=json.dumps(signals_payload, ensure_ascii=False),
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
                print(f"  Gemini cluster call failed (attempt {attempt + 1}): {exc}")
                if attempt < 3:
                    await backoff_sleep(attempt)
                else:
                    raise

    raise RuntimeError("Gemini clustering failed after 4 attempts")


async def create_issue(
    client: httpx.AsyncClient,
    service_key: str,
    supabase_url: str,
    cluster: dict[str, Any],
    signal_posted_ats: dict[str, str],
) -> int | None:
    signal_ids: list[str] = cluster.get("signal_ids", [])
    earliest = min(
        (signal_posted_ats[sid] for sid in signal_ids if sid in signal_posted_ats),
        default=datetime.utcnow().isoformat() + "Z",
    )
    resp = await client.post(
        f"{supabase_url}/rest/v1/issues",
        json={
            "title": cluster.get("title", "Untitled Issue"),
            "summary": cluster.get("summary"),
            "category": cluster.get("category", "Other"),
            "location": cluster.get("location"),
            "department": cluster.get("department"),
            "status": "open",
            "voice_count": len(signal_ids),
            "first_raised_at": earliest,
            "last_updated_at": datetime.utcnow().isoformat() + "Z",
        },
        headers={**_supa_headers(service_key), "Prefer": "return=representation"},
        timeout=15,
    )
    if not resp.is_success:
        print(f"  warning: failed to create issue: {resp.text}")
        return None
    return resp.json()[0]["id"]


async def merge_into_issue(
    client: httpx.AsyncClient,
    service_key: str,
    supabase_url: str,
    issue_id: int,
    count: int,
) -> None:
    resp = await client.post(
        f"{supabase_url}/rest/v1/rpc/increment_issue_voices",
        json={"p_issue_id": issue_id, "p_count": count},
        headers=_supa_headers(service_key),
        timeout=15,
    )
    if not resp.is_success:
        print(f"  warning: increment_issue_voices failed for issue {issue_id}: {resp.text}")


async def link_signals(
    client: httpx.AsyncClient,
    service_key: str,
    supabase_url: str,
    signal_ids: list[str],
    issue_id: int,
    similarity_score: float,
) -> None:
    ids_filter = ",".join(signal_ids)
    resp = await client.patch(
        f"{supabase_url}/rest/v1/signals",
        params={"id": f"in.({ids_filter})"},
        json={"issue_id": issue_id},
        headers={**_supa_headers(service_key), "Prefer": "return=minimal"},
        timeout=15,
    )
    if not resp.is_success:
        print(f"  warning: bulk signal update failed: {resp.text}")

    map_rows = [{"signal_id": sid, "issue_id": issue_id, "similarity_score": similarity_score} for sid in signal_ids]
    resp = await client.post(
        f"{supabase_url}/rest/v1/signal_issue_map",
        json=map_rows,
        headers={**_supa_headers(service_key), "Prefer": "resolution=merge-duplicates"},
        timeout=15,
    )
    if not resp.is_success:
        print(f"  warning: signal_issue_map upsert failed: {resp.text}")


async def main() -> None:
    supabase_url = os.environ["SUPABASE_URL"].rstrip("/").removesuffix("/rest/v1")
    service_key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    anon_key = os.environ["SUPABASE_ANON_KEY"]

    run_id: int | None = None
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{supabase_url}/rest/v1/scrape_runs",
                json={"script": "cluster_issues", "status": "running"},
                headers={**_supa_headers(service_key), "Prefer": "return=representation"},
                timeout=15,
            )
            resp.raise_for_status()
            run_id = resp.json()[0]["id"]
        except Exception as exc:
            print(f"warning: scrape_runs tracking unavailable: {exc}")

    try:
        async with httpx.AsyncClient() as client:
            signals = await fetch_unclustered_signals(client, anon_key, supabase_url)
            x_count = sum(1 for s in signals if s.get("source") == "x")
            reddit_count = sum(1 for s in signals if s.get("source") == "reddit")
            print(f"Fetched {len(signals)} unclustered signals (X: {x_count}, Reddit: {reddit_count})")

            if not signals:
                print("Nothing to cluster — exiting.")
                return

            existing_issues = await fetch_open_issues(client, anon_key, supabase_url)
            print(f"Fetched {len(existing_issues)} existing open issues")

            signal_posted_ats = {s["id"]: s.get("posted_at", "") for s in signals}
            total_created = 0
            total_merged = 0
            total_linked = 0
            total_batches = (len(signals) + BATCH_SIZE - 1) // BATCH_SIZE

            for batch_start in range(0, len(signals), BATCH_SIZE):
                batch = signals[batch_start : batch_start + BATCH_SIZE]
                batch_num = batch_start // BATCH_SIZE + 1
                print(f"Clustering batch {batch_num}/{total_batches} ({len(batch)} signals)...")

                try:
                    clusters = await cluster_with_gemini(batch, existing_issues)
                except Exception as exc:
                    print(f"  batch {batch_num} clustering failed — skipping: {exc}")
                    try:
                        await client.post(
                            f"{supabase_url}/rest/v1/categorization_failures",
                            json={
                                "script": "cluster_issues",
                                "batch_num": batch_num,
                                "error": str(exc),
                                "failed_at": datetime.utcnow().isoformat() + "Z",
                            },
                            headers=_supa_headers(service_key),
                            timeout=10,
                        )
                    except Exception:
                        pass
                    continue

                batch_created = 0
                batch_merged = 0
                for cluster in clusters:
                    signal_ids = cluster.get("signal_ids", [])
                    if not signal_ids:
                        continue

                    existing_id = cluster.get("existing_issue_id")
                    if existing_id is not None:
                        await merge_into_issue(client, service_key, supabase_url, int(existing_id), len(signal_ids))
                        issue_id = int(existing_id)
                        await link_signals(client, service_key, supabase_url, signal_ids, issue_id, 0.9)
                        total_merged += 1
                        batch_merged += 1
                    else:
                        issue_id = await create_issue(client, service_key, supabase_url, cluster, signal_posted_ats)
                        if issue_id is None:
                            continue
                        await link_signals(client, service_key, supabase_url, signal_ids, issue_id, 1.0)
                        total_created += 1
                        batch_created += 1

                    total_linked += len(signal_ids)

                print(f"  New issues: {batch_created} | Merged into existing: {batch_merged}")

            async with httpx.AsyncClient() as stats_client:
                resp = await stats_client.post(
                    f"{supabase_url}/rest/v1/rpc/refresh_issue_stats",
                    headers=_supa_headers(service_key),
                    timeout=15,
                )
                if not resp.is_success:
                    print(f"  warning: refresh_issue_stats failed: {resp.status_code}")

        print(f"Done. Signals clustered: {total_linked}. New issues: {total_created}. Issues updated: {total_merged}.")

        if run_id is not None:
            async with httpx.AsyncClient() as tc:
                try:
                    await tc.patch(
                        f"{supabase_url}/rest/v1/scrape_runs",
                        params={"id": f"eq.{run_id}"},
                        json={
                            "status": "completed",
                            "completed_at": datetime.utcnow().isoformat() + "Z",
                            "tweets_fetched": len(signals),
                            "tweets_upserted": total_linked,
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
                            "completed_at": datetime.utcnow().isoformat() + "Z",
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
