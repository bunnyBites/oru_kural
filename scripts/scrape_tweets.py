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
import time
from datetime import datetime
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

MAX_PAGES = 10
UPSERT_BATCH_SIZE = 100
SEARCH_URL = "https://api.twitter.com/2/tweets/search/recent"
CACHE_FILE = "last_fetch.json"


async def fetch_page(
    client: httpx.AsyncClient,
    bearer_token: str,
    params: dict[str, Any],
) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {bearer_token}"}
    retries = 0

    while True:
        resp = await client.get(SEARCH_URL, params=params, headers=headers, timeout=30)

        if resp.status_code == 429:
            reset_ts = int(resp.headers.get("x-rate-limit-reset", time.time() + 60))
            sleep_for = max(0, reset_ts - time.time()) + 5
            print(f"Rate limited. Sleeping {sleep_for:.0f}s until reset…")
            await asyncio.sleep(sleep_for)
            continue

        if resp.status_code in (400, 401, 403):
            raise RuntimeError(f"X API error {resp.status_code}: {resp.text}") from None

        if resp.status_code >= 500:
            retries += 1
            if retries > 3:
                raise RuntimeError(f"X API 5xx after 3 retries: {resp.status_code}: {resp.text}") from None
            print(f"X API {resp.status_code} — retry {retries}/3 in 10s…")
            await asyncio.sleep(10)
            continue

        resp.raise_for_status()
        return resp.json()


async def scrape_tweets(bearer_token: str) -> list[dict[str, Any]]:
    params: dict[str, Any] = {
        "query": "@CMOTamilnadu -is:retweet (lang:ta OR lang:en)",
        "max_results": 100,
        "tweet.fields": "created_at,author_id,text",
        "expansions": "author_id",
        "user.fields": "username,name",
    }

    all_rows: list[dict[str, Any]] = []

    async with httpx.AsyncClient() as client:
        for page_num in range(1, MAX_PAGES + 1):
            data = await fetch_page(client, bearer_token, params)

            tweets = data.get("data", [])
            users = {u["id"]: u for u in data.get("includes", {}).get("users", [])}

            print(f"Fetched page {page_num}: {len(tweets)} tweets")

            for tweet in tweets:
                author_id = tweet.get("author_id")
                if not author_id or author_id not in users:
                    print(f"  warning: author_id {author_id!r} not in users lookup — skipping tweet {tweet.get('id')}")
                    continue

                user = users[author_id]
                all_rows.append({
                    "id": tweet["id"],
                    "author_handle": user["username"],
                    "author_name": user["name"],
                    "content": tweet["text"],
                    "posted_at": tweet["created_at"],
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

    return all_rows


async def upsert_batch(
    client: httpx.AsyncClient,
    supabase_url: str,
    service_key: str,
    rows: list[dict[str, Any]],
) -> None:
    resp = await client.post(
        f"{supabase_url}/rest/v1/tweets",
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
            print(f"Upserted batch of {len(batch)} tweets")
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

    if args.from_file:
        print(f"Loading rows from {args.from_file}…")
        with open(args.from_file, encoding="utf-8") as fh:
            rows: list[dict[str, Any]] = json.load(fh)
        print(f"Loaded {len(rows)} rows.")
    else:
        bearer_token: str = os.environ["X_BEARER_TOKEN"]
        rows = await scrape_tweets(bearer_token)
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

    if not rows:
        print("Done. Total fetched: 0. Total upserted: 0.")
        return

    total_upserted = await upsert_all(supabase_url, service_key, rows)
    print(f"Done. Total fetched: {total_fetched}. Total upserted: {total_upserted}.")


if __name__ == "__main__":
    asyncio.run(main())
