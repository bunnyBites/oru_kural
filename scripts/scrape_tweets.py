"""
Scrape tweets mentioning @CMOTamilnadu via X API v2 (official Bearer Token).

Cost: ~$0.005 per post returned. Server-side filter (min_faves:50 in query)
      means only qualifying tweets are fetched — typical 10–30 per call,
      ~$0.08/run, under $1/month at 2×/week.

Schedule: Monday + Thursday, 2am UTC (incremental via since_id — each run
          fetches only tweets newer than the last stored X signal).

Setup:
    1. Create a developer app at console.x.com
    2. Generate a Bearer Token
    3. Set X_BEARER_TOKEN in .env (local) or GitHub Actions secrets (CI)
    4. Load $10–15 in credits at console.x.com (~6 months of budget)

Env vars:
    X_BEARER_TOKEN          (required) Bearer Token from console.x.com
    X_MAX_RESULTS           max results per call, default 50 (range 10–100)
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY

Usage:
    python scrape_tweets.py                   # full run — scrape + upsert
    python scrape_tweets.py --from-file FILE  # skip scraping, upsert saved rows
"""

import argparse
import asyncio
import json
import os
import re
from datetime import datetime, timezone
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

X_API_BASE = "https://api.twitter.com/2"
X_MAX_RESULTS: int = min(100, max(10, int(os.environ.get("X_MAX_RESULTS", "50"))))
UPSERT_BATCH_SIZE = 100
CACHE_FILE = "last_fetch.json"

MIN_LIKES = 50
MIN_REPLIES = 10


# ── Supabase helpers ───────────────────────────────────────────────────────────

async def insert_scrape_run(
    client: httpx.AsyncClient,
    supabase_url: str,
    service_key: str,
    script: str,
) -> int:
    resp = await client.post(
        f"{supabase_url}/rest/v1/scrape_runs",
        json={"script": script, "status": "running"},
        headers={
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()[0]["id"]


async def complete_scrape_run(
    client: httpx.AsyncClient,
    supabase_url: str,
    service_key: str,
    run_id: int,
    tweets_fetched: int,
    tweets_upserted: int,
    pages_fetched: int,
) -> None:
    resp = await client.patch(
        f"{supabase_url}/rest/v1/scrape_runs",
        params={"id": f"eq.{run_id}"},
        json={
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "tweets_fetched": tweets_fetched,
            "tweets_upserted": tweets_upserted,
            "pages_fetched": pages_fetched,
        },
        headers={
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
        timeout=15,
    )
    resp.raise_for_status()


async def fail_scrape_run(
    client: httpx.AsyncClient,
    supabase_url: str,
    service_key: str,
    run_id: int,
    error: str,
) -> None:
    resp = await client.patch(
        f"{supabase_url}/rest/v1/scrape_runs",
        params={"id": f"eq.{run_id}"},
        json={
            "status": "failed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "error_message": error,
        },
        headers={
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
        timeout=15,
    )
    resp.raise_for_status()


async def fetch_latest_x_signal_id(
    client: httpx.AsyncClient,
    supabase_url: str,
    service_key: str,
) -> str | None:
    """Return the most-recent X tweet ID stored in signals, used as since_id next run."""
    try:
        resp = await client.get(
            f"{supabase_url}/rest/v1/signals",
            params={
                "source": "eq.x",
                "select": "id,posted_at",
                "order": "posted_at.desc",
                "limit": "1",
            },
            headers={
                "apikey": service_key,
                "Authorization": f"Bearer {service_key}",
            },
            timeout=15,
        )
        resp.raise_for_status()
        rows = resp.json()
        return rows[0]["id"] if rows else None
    except Exception as exc:
        print(f"warning: could not fetch latest signal ID (will do full fetch): {exc}")
        return None


async def upsert_batch(
    client: httpx.AsyncClient,
    supabase_url: str,
    service_key: str,
    rows: list[dict[str, Any]],
) -> None:
    resp = await client.post(
        f"{supabase_url}/rest/v1/signals",
        json=rows,
        headers={
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates",
        },
        timeout=30,
    )
    if not resp.is_success:
        raise RuntimeError(f"Supabase upsert {resp.status_code}: {resp.text}") from None


async def upsert_all(
    supabase_url: str,
    service_key: str,
    rows: list[dict[str, Any]],
) -> int:
    async with httpx.AsyncClient() as client:
        for i in range(0, len(rows), UPSERT_BATCH_SIZE):
            batch = rows[i : i + UPSERT_BATCH_SIZE]
            await upsert_batch(client, supabase_url, service_key, batch)
            print(f"Upserted batch of {len(batch)} signals")
    return len(rows)


# ── X API v2 scraping ──────────────────────────────────────────────────────────

async def scrape_with_x_api(
    bearer_token: str,
    since_id: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """
    Fetch tweets via X API v2 /tweets/search/recent.
    Returns (rows, pages_fetched).

    min_faves is not available on Basic tier, so engagement is filtered client-side
    after fetching (MIN_LIKES=50 or MIN_REPLIES=10).
    """
    query = "@CMOTamilnadu -is:retweet -is:reply (lang:ta OR lang:en)"
    params: dict[str, str] = {
        "query": query,
        "max_results": str(X_MAX_RESULTS),
        "tweet.fields": "created_at,public_metrics,author_id,lang",
        "expansions": "author_id",
        "user.fields": "username,name",
    }
    if since_id:
        params["since_id"] = since_id
        print(f"Incremental: fetching tweets newer than ID {since_id}")
    else:
        print("Full fetch — no prior X signals found")

    print(f"Query: {query!r}   max_results={X_MAX_RESULTS}")

    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "User-Agent": "oru-kural/1.0",
    }

    now_utc = datetime.now(timezone.utc).isoformat()

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{X_API_BASE}/tweets/search/recent",
            headers=headers,
            params=params,
        )

    if resp.status_code == 401:
        raise RuntimeError(
            "X_BEARER_TOKEN is invalid or expired. Regenerate at console.x.com."
        )
    if resp.status_code == 429:
        reset_at = int(resp.headers.get("x-rate-limit-reset", 0))
        wait = max(15, reset_at - int(datetime.now(timezone.utc).timestamp()) + 5)
        raise RuntimeError(f"X API rate limit hit — retry after {wait}s")
    if resp.status_code == 400 and since_id:
        # X API enforces a 7-day rolling window; extract the suggested minimum ID and retry.
        try:
            errors = resp.json().get("errors", [])
            for err in errors:
                m = re.search(r"larger than (\d+)", err.get("message", ""))
                if m:
                    min_id = m.group(1)
                    print(f"warning: since_id {since_id} is outside X API's 7-day window — retrying with min valid ID {min_id}")
                    params["since_id"] = min_id
                    async with httpx.AsyncClient(timeout=30) as retry_client:
                        resp = await retry_client.get(
                            f"{X_API_BASE}/tweets/search/recent",
                            headers=headers,
                            params=params,
                        )
                    break
        except Exception:
            pass
    if not resp.is_success:
        raise RuntimeError(
            f"X API {resp.status_code}: {resp.text}"
        )
    body = resp.json()

    tweets: list[dict[str, Any]] = body.get("data", [])
    users: dict[str, dict[str, Any]] = {
        u["id"]: u for u in body.get("includes", {}).get("users", [])
    }
    meta = body.get("meta", {})

    rows: list[dict[str, Any]] = []
    skipped = 0
    for tweet in tweets:
        metrics = tweet.get("public_metrics", {})
        likes = metrics.get("like_count", 0)
        replies = metrics.get("reply_count", 0)
        if likes < MIN_LIKES and replies < MIN_REPLIES:
            skipped += 1
            continue

        user = users.get(tweet.get("author_id", ""), {})
        tweet_id = tweet["id"]
        username = user.get("username", "unknown")

        rows.append({
            "id": tweet_id,
            "source": "x",
            "author_handle": username,
            "author_name": user.get("name", username),
            "content": tweet["text"],
            "url": f"https://x.com/{username}/status/{tweet_id}",
            "posted_at": tweet.get("created_at", now_utc),
            "score": likes,
            "category": None,
            "confidence": None,
            "raw_json": tweet,
            "scraped_at": now_utc,
        })

    result_count = meta.get("result_count", len(tweets))
    print(
        f"Fetched {result_count} tweets, kept {len(rows)} with engagement, "
        f"skipped {skipped} low-traction"
    )

    if meta.get("next_token"):
        print(
            "Note: more results available — incremental since_id on next run will catch overflow."
        )

    return rows, 1


# ── main ───────────────────────────────────────────────────────────────────────

async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scrape @CMOTamilnadu tweets via X API v2 and store in Supabase."
    )
    parser.add_argument(
        "--from-file",
        metavar="FILE",
        help=f"Skip scraping; load mapped rows from FILE and upsert directly "
             f"(use {CACHE_FILE} from a previous run)",
    )
    args = parser.parse_args()

    supabase_url: str = os.environ["SUPABASE_URL"].rstrip("/").removesuffix("/rest/v1")
    service_key: str = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

    run_id: int | None = None
    async with httpx.AsyncClient() as tracking_client:
        try:
            run_id = await insert_scrape_run(
                tracking_client, supabase_url, service_key, script="scrape_tweets"
            )
        except Exception as exc:
            print(f"warning: scrape_runs tracking unavailable: {exc}")

    async def _complete(fetched: int, upserted: int, pages: int) -> None:
        if run_id is None:
            return
        async with httpx.AsyncClient() as tc:
            try:
                await complete_scrape_run(
                    tc, supabase_url, service_key, run_id,
                    tweets_fetched=fetched, tweets_upserted=upserted, pages_fetched=pages,
                )
            except Exception as exc:
                print(f"warning: failed to complete scrape_run: {exc}")

    async def _fail(error: str) -> None:
        if run_id is None:
            return
        async with httpx.AsyncClient() as tc:
            try:
                await fail_scrape_run(tc, supabase_url, service_key, run_id, error=error)
            except Exception as exc:
                print(f"warning: failed to mark scrape_run as failed: {exc}")

    try:
        if args.from_file:
            print(f"Loading rows from {args.from_file}…")
            with open(args.from_file, encoding="utf-8") as fh:
                rows: list[dict[str, Any]] = json.load(fh)
            print(f"Loaded {len(rows)} rows.")
            pages = 0
        else:
            bearer_token = os.environ.get("X_BEARER_TOKEN", "").strip()
            if not bearer_token:
                raise RuntimeError(
                    "X_BEARER_TOKEN env var is not set.\n"
                    "Generate a Bearer Token at console.x.com and add it to .env or GitHub secrets."
                )

            async with httpx.AsyncClient() as lookup_client:
                since_id = await fetch_latest_x_signal_id(
                    lookup_client, supabase_url, service_key
                )

            rows, pages = await scrape_with_x_api(bearer_token, since_id=since_id)

            with open(CACHE_FILE, "w", encoding="utf-8") as fh:
                json.dump(rows, fh, ensure_ascii=False, indent=2)
            print(f"Saved {len(rows)} rows to {CACHE_FILE}")

        total_fetched = len(rows)

        # Deduplicate by tweet id (safety net for page-boundary overlaps)
        seen: dict[str, dict[str, Any]] = {}
        for row in rows:
            seen[row["id"]] = row
        rows = list(seen.values())
        if total_fetched != len(rows):
            print(f"Deduplicated {total_fetched - len(rows)} duplicates → {len(rows)} unique")

        if not rows:
            print("Done. 0 qualifying tweets this run — normal for quiet periods.")
            await _complete(0, 0, pages if not args.from_file else 0)
            return

        total_upserted = await upsert_all(supabase_url, service_key, rows)
        print(f"Done. Fetched: {total_fetched}. Upserted: {total_upserted}.")
        await _complete(total_fetched, total_upserted, pages if not args.from_file else 0)

    except Exception as e:
        await _fail(str(e))
        raise


if __name__ == "__main__":
    asyncio.run(main())
