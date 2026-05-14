"""
Categorize uncategorized tweets in Supabase using the LLM abstraction in llm.py.

Usage:
    python categorize_tweets.py
"""

import asyncio
import json
import os
import random
from datetime import datetime
from typing import Any

import httpx
from dotenv import load_dotenv

from classifier_rules import classify_by_rules
from llm import classify_tweets

load_dotenv()

SUPABASE_URL: str = os.environ["SUPABASE_URL"]
SUPABASE_ANON_KEY: str = os.environ["SUPABASE_ANON_KEY"]
SUPABASE_SERVICE_ROLE_KEY: str = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

BATCH_SIZE = 40
MAX_GEMINI_RETRIES = 4


async def backoff_sleep(attempt: int, base: float = 2.0, cap: float = 60.0) -> None:
    """Exponential backoff with jitter. attempt is 0-indexed."""
    delay = min(base ** attempt + random.uniform(0, 1), cap)
    print(f"Backoff: sleeping {delay:.1f}s (attempt {attempt + 1})")
    await asyncio.sleep(delay)


async def insert_scrape_run(
    client: httpx.AsyncClient,
    script: str,
) -> int:
    resp = await client.post(
        f"{SUPABASE_URL}/rest/v1/scrape_runs",
        json={"script": script, "status": "running"},
        headers={
            "apikey": SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()[0]["id"]


async def complete_scrape_run(
    client: httpx.AsyncClient,
    run_id: int,
    tweets_upserted: int,
) -> None:
    resp = await client.patch(
        f"{SUPABASE_URL}/rest/v1/scrape_runs",
        params={"id": f"eq.{run_id}"},
        json={
            "status": "completed",
            "completed_at": datetime.utcnow().isoformat() + "Z",
            "tweets_upserted": tweets_upserted,
        },
        headers={
            "apikey": SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
        timeout=15,
    )
    resp.raise_for_status()


async def fail_scrape_run(
    client: httpx.AsyncClient,
    run_id: int,
    error: str,
) -> None:
    resp = await client.patch(
        f"{SUPABASE_URL}/rest/v1/scrape_runs",
        params={"id": f"eq.{run_id}"},
        json={
            "status": "failed",
            "completed_at": datetime.utcnow().isoformat() + "Z",
            "error_message": error,
        },
        headers={
            "apikey": SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
        timeout=15,
    )
    resp.raise_for_status()


async def log_categorization_failure(
    client: httpx.AsyncClient,
    tweet_ids: list[str],
    error_message: str,
) -> None:
    resp = await client.post(
        f"{SUPABASE_URL}/rest/v1/categorization_failures",
        json={
            "tweet_ids": tweet_ids,
            "error_message": error_message,
            "batch_size": len(tweet_ids),
        },
        headers={
            "apikey": SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
        timeout=15,
    )
    if not resp.is_success:
        print(f"  warning: failed to log categorization failure: {resp.status_code}: {resp.text}")


async def refresh_stats(client: httpx.AsyncClient) -> None:
    resp = await client.post(
        f"{SUPABASE_URL}/rest/v1/rpc/refresh_category_stats",
        headers={
            "apikey": SUPABASE_SERVICE_ROLE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        },
        timeout=15,
    )
    if not resp.is_success:
        print(f"  warning: refresh_category_stats RPC failed: {resp.status_code}")


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


async def classify_with_gemini_retry(
    client: httpx.AsyncClient,
    batch: list[dict[str, Any]],
    batch_num: int,
) -> list[dict[str, Any]] | None:
    """Calls classify_tweets with retry logic. Returns results or None on unrecoverable failure."""
    tweet_ids = [t["id"] for t in batch]

    for attempt in range(MAX_GEMINI_RETRIES):
        try:
            results = await classify_tweets(batch)
            return results
        except Exception as exc:
            exc_name = type(exc).__name__
            exc_str = str(exc)

            if "ResourceExhausted" in exc_name or "resource_exhausted" in exc_str.lower():
                print(f"  batch {batch_num}: Gemini quota exhausted — sleeping 60s before retry…")
                await asyncio.sleep(60)
            elif "ServiceUnavailable" in exc_name or "service_unavailable" in exc_str.lower():
                print(f"  batch {batch_num}: Gemini unavailable — {exc}")
                await backoff_sleep(attempt)
            elif "json" in exc_str.lower() or isinstance(exc, (json.JSONDecodeError, ValueError)):
                print(f"  batch {batch_num}: JSON parse failure from Gemini: {exc}")
                await log_categorization_failure(client, tweet_ids, f"JSON parse error: {exc_str}")
                return None
            else:
                print(f"  batch {batch_num}: Gemini call failed (attempt {attempt + 1}/{MAX_GEMINI_RETRIES}): {exc}")
                if attempt < MAX_GEMINI_RETRIES - 1:
                    await backoff_sleep(attempt)
                else:
                    await log_categorization_failure(client, tweet_ids, exc_str)
                    return None

    await log_categorization_failure(client, tweet_ids, "Max retries exceeded")
    return None


async def process_batch(
    client: httpx.AsyncClient,
    batch: list[dict[str, Any]],
    batch_num: int,
) -> tuple[int, int]:
    """Classify one batch and write results. Returns (ok_count, err_count)."""
    # Apply rules-based pre-classifier first
    rule_classified: list[dict[str, Any]] = []
    gemini_batch: list[dict[str, Any]] = []

    for tweet in batch:
        rule_result = classify_by_rules(tweet["id"], tweet["content"])
        if rule_result is not None:
            rule_classified.append(rule_result)
        else:
            gemini_batch.append(tweet)

    print(
        f"batch {batch_num}: Rules classified {len(rule_classified)} tweets. "
        f"Sending {len(gemini_batch)} to Gemini."
    )

    ok = err = 0

    # Upsert rule-classified tweets immediately
    for result in rule_classified:
        try:
            await update_tweet(
                client,
                str(result["id"]),
                str(result["category"]),
                float(result["confidence"]),
                None,
            )
            ok += 1
        except (httpx.HTTPStatusError, ValueError) as exc:
            print(f"  failed to update rule-classified tweet {result['id']}: {exc}")
            err += 1

    # Send remainder to Gemini
    if gemini_batch:
        results = await classify_with_gemini_retry(client, gemini_batch, batch_num)

        if results is None:
            err += len(gemini_batch)
        else:
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

    # Refresh stats after each successful batch
    if ok > 0:
        await refresh_stats(client)

    return ok, err


async def main() -> None:
    run_id: int | None = None
    async with httpx.AsyncClient() as client:
        try:
            run_id = await insert_scrape_run(client, script="categorize_tweets")
        except Exception as exc:
            print(f"warning: scrape_runs tracking unavailable (migration not applied?): {exc}")

    try:
        async with httpx.AsyncClient() as client:
            print("fetching uncategorized tweets…")
            tweets = await fetch_uncategorized(client)
            print(f"  found {len(tweets)} uncategorized tweets")

            if not tweets:
                print("nothing to categorize — exiting.")
                if run_id is not None:
                    async with httpx.AsyncClient() as tracking_client:
                        try:
                            await complete_scrape_run(tracking_client, run_id, tweets_upserted=0)
                        except Exception as exc:
                            print(f"warning: failed to complete scrape_run: {exc}")
                return

            total_ok = total_err = 0
            for i in range(0, len(tweets), BATCH_SIZE):
                batch = tweets[i : i + BATCH_SIZE]
                batch_num = i // BATCH_SIZE + 1
                ok, err = await process_batch(client, batch, batch_num)
                total_ok += ok
                total_err += err

        print(f"done. updated: {total_ok}, errors: {total_err}")

        if run_id is not None:
            async with httpx.AsyncClient() as tracking_client:
                try:
                    await complete_scrape_run(tracking_client, run_id, tweets_upserted=total_ok)
                except Exception as exc:
                    print(f"warning: failed to complete scrape_run: {exc}")

    except Exception as e:
        if run_id is not None:
            async with httpx.AsyncClient() as tracking_client:
                try:
                    await fail_scrape_run(tracking_client, run_id, error=str(e))
                except Exception as exc:
                    print(f"warning: failed to mark scrape_run as failed: {exc}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
