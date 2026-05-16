# Reddit signal scraper — JSON fallback (no auth required)
#
# STATUS: Using public Reddit JSON endpoints while PRAW API approval is pending.
#
# TO SWAP TO PRAW when credentials arrive:
#   1. pip install praw  (add to requirements.txt)
#   2. Replace ONLY the body of fetch_subreddit_posts() with the PRAW implementation
#   3. Add REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT to .env
#   4. Everything else in this file stays unchanged
#
# PRAW implementation to use (drop-in replacement for fetch_subreddit_posts body):
#
#   import praw
#   reddit = praw.Reddit(
#       client_id=os.environ["REDDIT_CLIENT_ID"],
#       client_secret=os.environ["REDDIT_CLIENT_SECRET"],
#       user_agent=os.environ["REDDIT_USER_AGENT"],
#   )
#   def _fetch() -> list[dict]:
#       subreddit_obj = reddit.subreddit(subreddit)
#       cutoff = datetime.utcnow().timestamp() - (lookback_days * 86400)
#       posts = []
#       for post in subreddit_obj.search(SEARCH_QUERY, sort="new", limit=100):
#           if post.created_utc < cutoff: continue
#           if post.score < MIN_SCORE: continue
#           posts.append(vars(post))   # convert PRAW object to dict
#       return posts
#   return await asyncio.to_thread(_fetch)
"""
Scrape Reddit posts mentioning the Tamil Nadu CM from r/Chennai and r/TamilNadu,
filter by score and recency, then upsert to Supabase signals table.

Usage:
    python scrape_reddit.py
"""

import asyncio
import os
from datetime import datetime
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

SUBREDDITS: list[str] = ["Chennai", "TamilNadu"]
SEARCH_QUERY: str = 'CM OR "Chief Minister" OR CMOTamilnadu OR "Tamil Nadu government"'
MIN_SCORE: int = 10
LOOKBACK_DAYS: int = 7
BATCH_SIZE: int = 100
MAX_PAGES_PER_SUBREDDIT: int = 5  # Reddit JSON returns 25/page max


def supabase_headers(anon_key: str) -> dict[str, str]:
    return {
        "apikey": anon_key,
        "Authorization": f"Bearer {anon_key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates",
    }


async def insert_scrape_run(
    client: httpx.AsyncClient,
    supabase_url: str,
    anon_key: str,
    script: str,
) -> int:
    resp = await client.post(
        f"{supabase_url}/rest/v1/scrape_runs",
        json={"script": script, "status": "running"},
        headers={
            "apikey": anon_key,
            "Authorization": f"Bearer {anon_key}",
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
    anon_key: str,
    run_id: int,
    items_fetched: int,
    items_processed: int,
) -> None:
    resp = await client.patch(
        f"{supabase_url}/rest/v1/scrape_runs",
        params={"id": f"eq.{run_id}"},
        json={
            "status": "completed",
            "completed_at": datetime.utcnow().isoformat() + "Z",
            "tweets_fetched": items_fetched,
            "tweets_upserted": items_processed,
        },
        headers={
            "apikey": anon_key,
            "Authorization": f"Bearer {anon_key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
        timeout=15,
    )
    resp.raise_for_status()


async def fail_scrape_run(
    client: httpx.AsyncClient,
    supabase_url: str,
    anon_key: str,
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
            "apikey": anon_key,
            "Authorization": f"Bearer {anon_key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
        timeout=15,
    )
    resp.raise_for_status()


async def fetch_subreddit_posts(
    client: httpx.AsyncClient,
    subreddit: str,
    lookback_days: int,
) -> list[dict[str, Any]]:
    """
    Fetch recent qualifying posts from a subreddit using Reddit's public JSON API.
    No authentication required.

    NOTE: When PRAW credentials are approved, replace only this function body
    with a PRAW implementation. All callers and downstream code stay unchanged.

    Returns a list of raw Reddit post dicts (Reddit's 'data' field per child).
    """
    cutoff_ts = datetime.utcnow().timestamp() - (lookback_days * 86400)
    base_url = f"https://www.reddit.com/r/{subreddit}/search.json"
    headers = {
        "User-Agent": "oru-kural/1.0 (civic research, non-commercial, read-only)",
    }

    all_posts: list[dict[str, Any]] = []
    after: str | None = None
    page = 0

    while page < MAX_PAGES_PER_SUBREDDIT:
        params: dict[str, str | int] = {
            "q": SEARCH_QUERY,
            "sort": "new",
            "limit": 25,
            "t": "week",
            "restrict_sr": "true",
        }
        if after:
            params["after"] = after

        try:
            r = await client.get(base_url, params=params, headers=headers)
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403:
                print(
                    f"  Reddit public JSON API returned 403 for r/{subreddit}.\n"
                    f"  Reddit has restricted unauthenticated access — PRAW credentials required.\n"
                    f"  Skipping Reddit scrape until API access is approved."
                )
                return []
            elif e.response.status_code == 429:
                print(f"  Rate limited on r/{subreddit}. Sleeping 60s...")
                await asyncio.sleep(60)
                r = await client.get(base_url, params=params, headers=headers)
                r.raise_for_status()
            else:
                raise RuntimeError(
                    f"Reddit JSON fetch failed for r/{subreddit}: HTTP {e.response.status_code}"
                ) from None

        data = r.json().get("data", {})
        children = data.get("children", [])

        if not children:
            break

        stop_early = False
        for child in children:
            post = child.get("data", {})
            created_utc = post.get("created_utc", 0)

            if created_utc < cutoff_ts:
                stop_early = True
                break

            if post.get("score", 0) >= MIN_SCORE:
                all_posts.append(post)

        after = data.get("after")
        page += 1

        if stop_early or not after:
            break

        await asyncio.sleep(2)

    return all_posts


def map_post_to_signal(post: dict[str, Any], subreddit: str) -> dict[str, Any]:
    """
    Map a raw Reddit post dict to the signals table schema.
    ID is prefixed with 'reddit_' to avoid collision with X tweet IDs.
    """
    author = post.get("author", "[deleted]")
    title = post.get("title", "").strip()
    selftext = post.get("selftext", "").strip()
    content = f"{title}\n\n{selftext}".strip() if selftext else title

    return {
        "id": f"reddit_{post['id']}",
        "source": "reddit",
        "author_handle": author,
        "author_name": author,
        "content": content,
        "url": f"https://reddit.com{post.get('permalink', '')}",
        "score": post.get("score", 0),
        "posted_at": datetime.utcfromtimestamp(post.get("created_utc", 0)).isoformat() + "Z",
        "category": None,
        "confidence": None,
        "translated_content": None,
        "raw_json": {
            "id": post.get("id"),
            "subreddit": subreddit,
            "title": title,
            "selftext": selftext,
            "score": post.get("score", 0),
            "url": post.get("url", ""),
            "permalink": post.get("permalink", ""),
            "created_utc": post.get("created_utc", 0),
            "num_comments": post.get("num_comments", 0),
            "upvote_ratio": post.get("upvote_ratio", 0.0),
        },
        "scraped_at": datetime.utcnow().isoformat() + "Z",
    }


async def upsert_signals(
    client: httpx.AsyncClient,
    supabase_url: str,
    anon_key: str,
    signals: list[dict[str, Any]],
) -> int:
    """Upsert signals in batches. Returns total rows upserted."""
    if not signals:
        return 0

    total = 0
    headers = supabase_headers(anon_key)

    for i in range(0, len(signals), BATCH_SIZE):
        batch = signals[i : i + BATCH_SIZE]
        r = await client.post(
            f"{supabase_url}/rest/v1/signals",
            headers=headers,
            json=batch,
        )
        r.raise_for_status()
        print(f"  Upserted batch of {len(batch)} signals")
        total += len(batch)

    return total


async def main() -> None:
    supabase_url = os.environ["SUPABASE_URL"].rstrip("/").removesuffix("/rest/v1")
    anon_key = os.environ["SUPABASE_ANON_KEY"]

    async with httpx.AsyncClient(timeout=30.0) as client:
        run_id = await insert_scrape_run(client, supabase_url, anon_key, script="scrape_reddit")

        try:
            all_signals: list[dict[str, Any]] = []

            for subreddit in SUBREDDITS:
                print(f"Fetching r/{subreddit}...")
                posts = await fetch_subreddit_posts(client, subreddit, LOOKBACK_DAYS)
                signals = [map_post_to_signal(p, subreddit) for p in posts]
                print(
                    f"  Found {len(signals)} qualifying posts "
                    f"(score >= {MIN_SCORE}, last {LOOKBACK_DAYS} days)"
                )
                all_signals.extend(signals)

            total_upserted = await upsert_signals(client, supabase_url, anon_key, all_signals)

            print(f"Done. Total fetched: {len(all_signals)}. Total upserted: {total_upserted}.")

            await complete_scrape_run(
                client, supabase_url, anon_key, run_id,
                items_fetched=len(all_signals),
                items_processed=total_upserted,
            )

        except Exception as e:
            await fail_scrape_run(client, supabase_url, anon_key, run_id, error=str(e))
            raise


if __name__ == "__main__":
    asyncio.run(main())
