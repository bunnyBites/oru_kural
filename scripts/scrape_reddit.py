"""
Scrape Reddit posts mentioning the Tamil Nadu CM from r/Chennai and r/TamilNadu,
filter by score and recency, then upsert to Supabase signals table.

Usage:
    python scrape_reddit.py
"""

import asyncio
import os
import random
from datetime import datetime
from typing import Any

import httpx
import praw
from dotenv import load_dotenv

load_dotenv()

SUBREDDITS = ["Chennai", "TamilNadu"]
SEARCH_QUERY = 'CM OR "Chief Minister" OR CMOTamilnadu OR "Tamil Nadu government"'
MIN_SCORE = 10
LOOKBACK_DAYS = 7
BATCH_SIZE = 100


def create_reddit_client() -> praw.Reddit:
    return praw.Reddit(
        client_id=os.environ["REDDIT_CLIENT_ID"],
        client_secret=os.environ["REDDIT_CLIENT_SECRET"],
        user_agent=os.environ["REDDIT_USER_AGENT"],
    )


def _supa_headers(key: str) -> dict[str, str]:
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


async def fetch_subreddit_posts(
    reddit: praw.Reddit,
    subreddit_name: str,
    lookback_days: int,
) -> list[Any]:
    def _fetch() -> list[Any]:
        subreddit = reddit.subreddit(subreddit_name)
        cutoff = datetime.utcnow().timestamp() - (lookback_days * 86400)
        posts = []
        for post in subreddit.search(SEARCH_QUERY, sort="new", limit=100):
            if post.created_utc < cutoff:
                continue
            if post.score < MIN_SCORE:
                continue
            posts.append(post)
        return posts

    return await asyncio.to_thread(_fetch)


def map_post_to_signal(post: Any, subreddit: str) -> dict[str, Any]:
    return {
        "id": f"reddit_{post.id}",
        "source": "reddit",
        "author_handle": str(post.author) if post.author else "[deleted]",
        "author_name": str(post.author) if post.author else "[deleted]",
        "content": f"{post.title}\n\n{post.selftext}".strip(),
        "url": f"https://reddit.com{post.permalink}",
        "score": post.score,
        "posted_at": datetime.utcfromtimestamp(post.created_utc).isoformat() + "Z",
        "category": None,
        "confidence": None,
        "raw_json": {
            "id": post.id,
            "subreddit": subreddit,
            "title": post.title,
            "selftext": post.selftext,
            "score": post.score,
            "url": post.url,
            "permalink": post.permalink,
            "created_utc": post.created_utc,
        },
        "scraped_at": datetime.utcnow().isoformat() + "Z",
    }


async def upsert_signals(
    client: httpx.AsyncClient,
    supabase_url: str,
    service_key: str,
    rows: list[dict[str, Any]],
) -> int:
    total = 0
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i : i + BATCH_SIZE]
        resp = await client.post(
            f"{supabase_url}/rest/v1/signals",
            json=batch,
            headers={**_supa_headers(service_key), "Prefer": "resolution=merge-duplicates"},
            timeout=30,
        )
        if not resp.is_success:
            raise RuntimeError(f"Supabase upsert {resp.status_code}: {resp.text}")
        print(f"Upserted batch of {len(batch)} signals")
        total += len(batch)
    return total


async def main() -> None:
    supabase_url = os.environ["SUPABASE_URL"].rstrip("/").removesuffix("/rest/v1")
    service_key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

    run_id: int | None = None
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{supabase_url}/rest/v1/scrape_runs",
                json={"script": "scrape_reddit", "status": "running"},
                headers={**_supa_headers(service_key), "Prefer": "return=representation"},
                timeout=15,
            )
            resp.raise_for_status()
            run_id = resp.json()[0]["id"]
        except Exception as exc:
            print(f"warning: scrape_runs tracking unavailable: {exc}")

    try:
        reddit = create_reddit_client()
        all_rows: list[dict[str, Any]] = []

        for subreddit_name in SUBREDDITS:
            print(f"Fetching r/{subreddit_name}...")
            posts = await fetch_subreddit_posts(reddit, subreddit_name, LOOKBACK_DAYS)
            print(f"  Found {len(posts)} qualifying posts (score >= {MIN_SCORE}, last {LOOKBACK_DAYS} days)")
            for post in posts:
                all_rows.append(map_post_to_signal(post, subreddit_name))

        total_fetched = len(all_rows)

        if not all_rows:
            print("Done. Total fetched: 0. Total upserted: 0.")
            if run_id is not None:
                async with httpx.AsyncClient() as tc:
                    try:
                        await tc.patch(
                            f"{supabase_url}/rest/v1/scrape_runs",
                            params={"id": f"eq.{run_id}"},
                            json={
                                "status": "completed",
                                "completed_at": datetime.utcnow().isoformat() + "Z",
                                "tweets_fetched": 0,
                                "tweets_upserted": 0,
                            },
                            headers={**_supa_headers(service_key), "Prefer": "return=minimal"},
                            timeout=15,
                        )
                    except Exception as exc:
                        print(f"warning: failed to complete scrape_run: {exc}")
            return

        async with httpx.AsyncClient() as client:
            total_upserted = await upsert_signals(client, supabase_url, service_key, all_rows)

        print(f"Done. Total fetched: {total_fetched}. Total upserted: {total_upserted}.")

        if run_id is not None:
            async with httpx.AsyncClient() as tc:
                try:
                    await tc.patch(
                        f"{supabase_url}/rest/v1/scrape_runs",
                        params={"id": f"eq.{run_id}"},
                        json={
                            "status": "completed",
                            "completed_at": datetime.utcnow().isoformat() + "Z",
                            "tweets_fetched": total_fetched,
                            "tweets_upserted": total_upserted,
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
