"""
Scrape tweets mentioning @CMOTamilnadu via X API v2 and upsert to Supabase.

Usage:
    python scrape_tweets.py                      # full run — fetch + upsert
    python scrape_tweets.py --from-file FILE     # skip X API, upsert from saved JSON
"""

import argparse
import asyncio
import json
import os
import random
import time
from datetime import datetime
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

MAX_PAGES: int = int(os.environ.get("X_MAX_PAGES", "3"))
MIN_LIKES = 50
MIN_REPLIES_WITH_TAG = 10
UPSERT_BATCH_SIZE = 100
SEARCH_URL = "https://api.twitter.com/2/tweets/search/recent"
CACHE_FILE = "last_fetch.json"


async def backoff_sleep(attempt: int, base: float = 2.0, cap: float = 60.0) -> None:
    """Exponential backoff with jitter. attempt is 0-indexed."""
    delay = min(base ** attempt + random.uniform(0, 1), cap)
    print(f"Backoff: sleeping {delay:.1f}s (attempt {attempt + 1})")
    await asyncio.sleep(delay)


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
            "completed_at": datetime.utcnow().isoformat() + "Z",
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
            "completed_at": datetime.utcnow().isoformat() + "Z",
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


async def fetch_page(
    client: httpx.AsyncClient,
    bearer_token: str,
    params: dict[str, Any],
) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {bearer_token}"}
    server_err_attempts = 0

    while True:
        resp = await client.get(SEARCH_URL, params=params, headers=headers, timeout=30)

        if resp.status_code == 429:
            reset_header = resp.headers.get("x-rate-limit-reset")
            if reset_header:
                sleep_for = max(0, int(reset_header) - time.time()) + 5
                print(f"Rate limited. Sleeping {sleep_for:.0f}s until reset…")
                await asyncio.sleep(sleep_for)
            else:
                await backoff_sleep(server_err_attempts)
            continue

        if resp.status_code in (400, 401, 403):
            raise RuntimeError(f"X API error {resp.status_code}: {resp.text}") from None

        if resp.status_code >= 500:
            if server_err_attempts >= 3:
                raise RuntimeError(
                    f"X API 5xx after 3 retries: {resp.status_code}: {resp.text}"
                ) from None
            await backoff_sleep(server_err_attempts)
            server_err_attempts += 1
            continue

        resp.raise_for_status()
        return resp.json()


def has_engagement(tweet: dict[str, Any]) -> bool:
    """Returns True if the tweet has proven public traction."""
    metrics = tweet.get("public_metrics", {})
    likes = metrics.get("like_count", 0)
    replies = metrics.get("reply_count", 0)
    text = tweet.get("text", "")
    return likes >= MIN_LIKES or (replies >= MIN_REPLIES_WITH_TAG and "@CMOTamilnadu" in text)


async def fetch_latest_x_signal_id(
    client: httpx.AsyncClient,
    supabase_url: str,
    service_key: str,
) -> str | None:
    """Return the most recent X tweet ID stored in signals, to use as since_id next run."""
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


async def scrape_tweets(bearer_token: str, since_id: str | None = None) -> tuple[list[dict[str, Any]], int, int]:
    """Returns (rows, page_count, skipped_count)."""
    params: dict[str, Any] = {
        "query": "@CMOTamilnadu -is:retweet -is:reply (lang:ta OR lang:en)",
        "max_results": 100,
        "tweet.fields": "created_at,author_id,text,public_metrics",
        "expansions": "author_id",
        "user.fields": "username,name",
    }

    if since_id:
        params["since_id"] = since_id
        print(f"Incremental fetch: only tweets newer than ID {since_id}")
    else:
        print("Full fetch: no prior signals found — reading up to 7 days back")

    all_rows: list[dict[str, Any]] = []
    page_count = 0
    skipped_count = 0

    async with httpx.AsyncClient() as client:
        for page_num in range(1, MAX_PAGES + 1):
            data = await fetch_page(client, bearer_token, params)
            page_count += 1

            tweets = data.get("data", [])
            users = {u["id"]: u for u in data.get("includes", {}).get("users", [])}

            print(f"Fetched page {page_num}: {len(tweets)} tweets")

            for tweet in tweets:
                author_id = tweet.get("author_id")
                if not author_id or author_id not in users:
                    print(f"  warning: author_id {author_id!r} not in users lookup — skipping tweet {tweet.get('id')}")
                    continue

                if not has_engagement(tweet):
                    skipped_count += 1
                    continue

                user = users[author_id]
                tweet_id = tweet["id"]
                metrics = tweet.get("public_metrics", {})
                all_rows.append({
                    "id": tweet_id,
                    "source": "x",
                    "author_handle": user["username"],
                    "author_name": user["name"],
                    "content": tweet["text"],
                    "url": f"https://x.com/i/web/status/{tweet_id}",
                    "posted_at": tweet["created_at"],
                    "score": metrics.get("like_count", 0),
                    "category": None,
                    "confidence": None,
                    "raw_json": tweet,
                    "scraped_at": datetime.utcnow().isoformat() + "Z",
                })

            next_token = data.get("meta", {}).get("next_token")
            if not next_token:
                break

            params["next_token"] = next_token
            await asyncio.sleep(1)

    return all_rows, page_count, skipped_count


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


async def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape @CMOTamilnadu tweets and store in Supabase.")
    parser.add_argument(
        "--from-file",
        metavar="FILE",
        help=f"Skip X API fetch; load mapped rows from FILE and upsert directly (use {CACHE_FILE} from a previous run)",
    )
    args = parser.parse_args()

    supabase_url: str = os.environ["SUPABASE_URL"].rstrip("/").removesuffix("/rest/v1")
    service_key: str = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

    run_id: int | None = None
    async with httpx.AsyncClient() as tracking_client:
        try:
            run_id = await insert_scrape_run(tracking_client, supabase_url, service_key, script="scrape_tweets")
        except Exception as exc:
            print(f"warning: scrape_runs tracking unavailable (migration not applied?): {exc}")

    page_count = 0
    skipped_count = 0

    async def _complete(fetched: int, upserted: int, pages: int) -> None:
        if run_id is None:
            return
        async with httpx.AsyncClient() as tc:
            try:
                await complete_scrape_run(tc, supabase_url, service_key, run_id,
                                          tweets_fetched=fetched, tweets_upserted=upserted,
                                          pages_fetched=pages)
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
        else:
            bearer_token: str = os.environ["X_BEARER_TOKEN"]
            async with httpx.AsyncClient() as lookup_client:
                since_id = await fetch_latest_x_signal_id(lookup_client, supabase_url, service_key)
            rows, page_count, skipped_count = await scrape_tweets(bearer_token, since_id=since_id)
            # Save before upserting so data is not lost if upsert fails
            with open(CACHE_FILE, "w", encoding="utf-8") as fh:
                json.dump(rows, fh, ensure_ascii=False, indent=2)
            print(f"Saved {len(rows)} rows to {CACHE_FILE}")

        total_fetched = len(rows)
        # Deduplicate by tweet id — X API can return the same tweet on multiple pages
        seen: dict[str, dict[str, Any]] = {}
        for row in rows:
            seen[row["id"]] = row
        rows = list(seen.values())
        if total_fetched != len(rows):
            print(f"Deduplicated {total_fetched - len(rows)} duplicate tweets → {len(rows)} unique")

        if skipped_count:
            print(f"Skipped {skipped_count} zero-engagement tweets.")

        if not rows:
            print("Done. Total fetched: 0. Total upserted: 0.")
            await _complete(0, 0, page_count)
            return

        total_upserted = await upsert_all(supabase_url, service_key, rows)
        print(f"Done. Total fetched: {total_fetched}. Total upserted: {total_upserted}. Skipped (low traction): {skipped_count}.")
        estimated_cost = total_fetched * 0.005
        print(f"Estimated X API cost this run: ${estimated_cost:.2f}")
        await _complete(total_fetched, total_upserted, page_count)

    except Exception as e:
        await _fail(str(e))
        raise


if __name__ == "__main__":
    asyncio.run(main())
