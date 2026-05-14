"""
Categorize uncategorized tweets in Supabase using the LLM abstraction in llm.py.

Usage:
    python categorize_tweets.py
"""

import asyncio
import os
from typing import Any

import httpx
from dotenv import load_dotenv

from llm import classify_tweets

load_dotenv()

SUPABASE_URL: str = os.environ["SUPABASE_URL"]
SUPABASE_ANON_KEY: str = os.environ["SUPABASE_ANON_KEY"]
SUPABASE_SERVICE_ROLE_KEY: str = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

BATCH_SIZE = 40


async def fetch_uncategorized(client: httpx.AsyncClient) -> list[dict[str, Any]]:
    """Fetch tweets missing a translation (or category), newest first. Read — uses anon key."""
    resp = await client.get(
        f"{SUPABASE_URL}/rest/v1/tweets",
        params={
            "translated_content": "is.null",
            "order": "posted_at.desc",
            "select": "id,content",
        },
        headers={
            "apikey": SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()  # type: ignore[return-value]


async def update_tweet(
    client: httpx.AsyncClient,
    tweet_id: str,
    category: str,
    confidence: float,
    translated_content: str | None,
) -> None:
    """Patch a tweet's category, confidence, and translation. Write — uses service role key."""
    resp = await client.patch(
        f"{SUPABASE_URL}/rest/v1/tweets",
        params={"id": f"eq.{tweet_id}"},
        json={"category": category, "confidence": confidence, "translated_content": translated_content},
        headers={
            "apikey": SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
        timeout=15,
    )
    resp.raise_for_status()


async def process_batch(
    client: httpx.AsyncClient,
    batch: list[dict[str, Any]],
    batch_num: int,
) -> tuple[int, int]:
    """Classify one batch and write results. Returns (ok_count, err_count)."""
    print(f"batch {batch_num}: classifying {len(batch)} tweets…")
    try:
        results = await classify_tweets(batch)
    except Exception as exc:
        print(f"  batch {batch_num} LLM call failed — skipping: {exc}")
        return 0, len(batch)

    ok = err = 0
    for result in results:
        tweet_id = result.get("id")
        category = result.get("category")
        confidence = result.get("confidence")

        if not tweet_id or not category or confidence is None:
            print(f"  skipping incomplete result: {result}")
            err += 1
            continue

        translated_content = result.get("translated_content")
        if translated_content is None:
            print(f"  warning: translated_content missing for tweet {tweet_id}, setting to None")

        try:
            await update_tweet(client, str(tweet_id), str(category), float(confidence), translated_content)
            ok += 1
        except (httpx.HTTPStatusError, ValueError) as exc:
            print(f"  failed to update tweet {tweet_id}: {exc}")
            err += 1

    return ok, err


async def main() -> None:
    async with httpx.AsyncClient() as client:
        print("fetching uncategorized tweets…")
        tweets = await fetch_uncategorized(client)
        print(f"  found {len(tweets)} uncategorized tweets")

        if not tweets:
            print("nothing to categorize — exiting.")
            return

        total_ok = total_err = 0
        for i in range(0, len(tweets), BATCH_SIZE):
            batch = tweets[i : i + BATCH_SIZE]
            batch_num = i // BATCH_SIZE + 1
            ok, err = await process_batch(client, batch, batch_num)
            total_ok += ok
            total_err += err

    print(f"done. updated: {total_ok}, errors: {total_err}")


if __name__ == "__main__":
    asyncio.run(main())
