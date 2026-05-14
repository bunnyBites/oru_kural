"""
Scrape tweets mentioning @CMofTamilNadu via Apify and upsert to Supabase.

Usage:
    python scrape_tweets.py
    python scrape_tweets.py --dry-run sample_data.json
"""

import argparse
import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

APIFY_API_KEY: str = os.environ["APIFY_API_KEY"]
SUPABASE_URL: str = os.environ["SUPABASE_URL"]
SUPABASE_ANON_KEY: str = os.environ["SUPABASE_ANON_KEY"]

ACTOR_ID = "apidojo/tweet-scraper"
SEARCH_QUERY = "@CMofTamilNadu"
MAX_ITEMS = 500
POLL_INTERVAL_SECONDS = 10
UPSERT_BATCH_SIZE = 100


async def start_apify_run(client: httpx.AsyncClient) -> tuple[str, str]:
    """Trigger the Apify actor and return (run_id, dataset_id)."""
    resp = await client.post(
        f"https://api.apify.com/v2/acts/{ACTOR_ID}/runs",
        params={"token": APIFY_API_KEY},
        json={"searchTerms": [SEARCH_QUERY], "maxItems": MAX_ITEMS},
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()["data"]
    return data["id"], data["defaultDatasetId"]


async def poll_until_done(client: httpx.AsyncClient, run_id: str) -> None:
    """Block until the Apify run reaches a terminal state."""
    terminal_states = {"SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"}
    while True:
        resp = await client.get(
            f"https://api.apify.com/v2/actor-runs/{run_id}",
            params={"token": APIFY_API_KEY},
            timeout=30,
        )
        resp.raise_for_status()
        status: str = resp.json()["data"]["status"]
        print(f"  run status: {status}")
        if status == "SUCCEEDED":
            return
        if status in terminal_states:
            raise RuntimeError(f"Apify run {run_id} ended with status: {status}")
        await asyncio.sleep(POLL_INTERVAL_SECONDS)


async def fetch_dataset(client: httpx.AsyncClient, dataset_id: str) -> list[dict[str, Any]]:
    """Download all items from the Apify dataset."""
    resp = await client.get(
        f"https://api.apify.com/v2/datasets/{dataset_id}/items",
        params={"token": APIFY_API_KEY, "format": "json", "limit": MAX_ITEMS},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()  # type: ignore[return-value]


def map_item(item: dict[str, Any]) -> dict[str, Any] | None:
    """Map a raw Apify tweet item to the tweets table schema."""
    try:
        tweet_id = str(item["id"])

        # apidojo/tweet-scraper nests author under "author" or "user"
        author = item.get("author") or item.get("user") or {}
        author_handle: str | None = author.get("userName") or author.get("screen_name")
        author_name: str | None = author.get("name")
        content: str | None = item.get("text") or item.get("full_text")
        posted_at: str | None = item.get("createdAt") or item.get("created_at")

        if not all([tweet_id, author_handle, content, posted_at]):
            missing = [k for k, v in {"id": tweet_id, "author_handle": author_handle,
                                       "content": content, "posted_at": posted_at}.items() if not v]
            print(f"  skipping item — missing fields: {missing}")
            return None

        return {
            "id": tweet_id,
            "author_handle": author_handle,
            "author_name": author_name,
            "content": content,
            "posted_at": posted_at,
            "category": None,
            "confidence": None,
            "raw_json": item,
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        }
    except (KeyError, TypeError, ValueError) as exc:
        print(f"  skipping malformed item: {exc}")
        return None


async def upsert_batch(client: httpx.AsyncClient, rows: list[dict[str, Any]]) -> None:
    """Upsert a single batch to Supabase, merging on primary key."""
    resp = await client.post(
        f"{SUPABASE_URL}/rest/v1/tweets",
        json=rows,
        headers={
            "apikey": SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates",
        },
        timeout=30,
    )
    resp.raise_for_status()


async def upsert_all(client: httpx.AsyncClient, rows: list[dict[str, Any]]) -> None:
    """Upsert rows in batches of UPSERT_BATCH_SIZE."""
    for i in range(0, len(rows), UPSERT_BATCH_SIZE):
        batch = rows[i : i + UPSERT_BATCH_SIZE]
        end = i + len(batch)
        print(f"  upserting rows {i + 1}–{end} of {len(rows)}…")
        await upsert_batch(client, batch)


async def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape @CMofTamilNadu tweets and store in Supabase.")
    parser.add_argument(
        "--dry-run",
        metavar="FILE",
        help="Skip Apify; load raw dataset JSON from FILE instead (saves API credits during testing)",
    )
    args = parser.parse_args()

    async with httpx.AsyncClient() as client:
        if args.dry_run:
            print(f"[dry-run] loading dataset from {args.dry_run}")
            with open(args.dry_run, encoding="utf-8") as fh:
                raw_items: list[dict[str, Any]] = json.load(fh)
        else:
            print("starting Apify run…")
            run_id, dataset_id = await start_apify_run(client)
            print(f"  run_id={run_id}  dataset_id={dataset_id}")

            print("polling for completion…")
            await poll_until_done(client, run_id)

            print("fetching dataset…")
            raw_items = await fetch_dataset(client, dataset_id)

        print(f"mapping {len(raw_items)} raw items…")
        rows = [row for item in raw_items if (row := map_item(item)) is not None]
        skipped = len(raw_items) - len(rows)
        print(f"  {len(rows)} valid rows, {skipped} skipped")

        if not rows:
            print("nothing to upsert — exiting.")
            return

        print("upserting to Supabase…")
        await upsert_all(client, rows)

    print(f"done. {len(rows)} tweets upserted.")


if __name__ == "__main__":
    asyncio.run(main())
