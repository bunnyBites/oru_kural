"""
Scrape tweets mentioning @CMOTamilnadu via twscrape (real-account web scraper).

Cost: Free — no X API subscription needed.
      Uses 2–3 throwaway X accounts stored as TWSCRAPE_ACCOUNTS secret.

Account format (JSON array):
  [{"username":"...", "password":"...", "email":"...", "email_password":"..."}]

  Also accepts a single-account JSON object (no surrounding array).

  GitHub Actions: add as a repository secret named TWSCRAPE_ACCOUNTS.
  Local dev:      set TWSCRAPE_ACCOUNTS in the root .env file.

Env vars:
    TWSCRAPE_ACCOUNTS       (required) JSON array of account dicts
    TWSCRAPE_LIMIT          max tweets to fetch, default 100
    SUPABASE_URL            Supabase project URL
    SUPABASE_SERVICE_ROLE_KEY

Usage:
    python scrape_tweets.py            # full run — scrape + upsert
    python scrape_tweets.py --from-file FILE  # skip scraping, upsert saved rows
"""

import argparse
import asyncio
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from typing import Any

import httpx
from dotenv import load_dotenv
from twscrape import API

load_dotenv()

TWSCRAPE_LIMIT: int = int(os.environ.get("TWSCRAPE_LIMIT", "100"))
MIN_LIKES = 50
MIN_REPLIES_WITH_TAG = 10
UPSERT_BATCH_SIZE = 100
CACHE_FILE = "last_fetch.json"


# ── Supabase helpers (unchanged from v3) ───────────────────────────────────────

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


# ── twscrape scraping ──────────────────────────────────────────────────────────

def has_engagement(tweet: Any) -> bool:
    """Return True if the tweet has enough public traction to be a civic signal."""
    likes = tweet.likeCount or 0
    replies = tweet.replyCount or 0
    text = tweet.rawContent or ""
    return likes >= MIN_LIKES or (replies >= MIN_REPLIES_WITH_TAG and "@CMOTamilnadu" in text)


async def scrape_with_twscrape(
    accounts: list[dict[str, str]],
    since_id: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """
    Scrape @CMOTamilnadu tweets using twscrape.
    Returns (rows, skipped_low_engagement_count).
    """
    # Each CI run gets a fresh temp db — no stale login state between runs
    db_path = os.path.join(tempfile.mkdtemp(), "tw.db")
    api = API(db_path)

    for acc in accounts:
        await api.pool.add_account(
            acc["username"],
            acc["password"],
            acc["email"],
            acc["email_password"],
        )
    print(f"Logging in {len(accounts)} account(s)…")
    await api.pool.login_all()

    # Build search query — operators match Twitter's advanced search
    query = "@CMOTamilnadu -filter:retweets -filter:replies (lang:ta OR lang:en)"
    if since_id:
        query += f" since_id:{since_id}"
        print(f"Incremental: fetching tweets newer than ID {since_id}")
    else:
        print("Full fetch — no prior X signals found, reading recent tweets")

    print(f"Query: {query!r}   limit={TWSCRAPE_LIMIT}")

    rows: list[dict[str, Any]] = []
    skipped = 0
    total = 0
    now_utc = datetime.now(timezone.utc).isoformat()

    async for tweet in api.search(query, limit=TWSCRAPE_LIMIT):
        total += 1
        if not has_engagement(tweet):
            skipped += 1
            continue

        tweet_id = str(tweet.id)

        # tweet.json() serialises datetimes; parse back to dict for raw_json column
        try:
            raw: Any = json.loads(tweet.json())
        except Exception:
            raw = {"id": tweet_id, "rawContent": tweet.rawContent}

        rows.append({
            "id": tweet_id,
            "source": "x",
            "author_handle": tweet.user.username,
            "author_name": tweet.user.displayname,
            "content": tweet.rawContent,
            "url": tweet.url,
            "posted_at": tweet.date.isoformat(),
            "score": tweet.likeCount or 0,
            "category": None,
            "confidence": None,
            "raw_json": raw,
            "scraped_at": now_utc,
        })

    print(
        f"Fetched {total} tweets, kept {len(rows)} with engagement, "
        f"skipped {skipped} low-traction"
    )
    return rows, skipped


# ── main ───────────────────────────────────────────────────────────────────────

async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scrape @CMOTamilnadu tweets via twscrape and store in Supabase."
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
            skipped_count = 0
        else:
            # ── parse TWSCRAPE_ACCOUNTS ────────────────────────────────────
            raw_accounts = os.environ.get("TWSCRAPE_ACCOUNTS", "").strip()
            if not raw_accounts:
                raise RuntimeError(
                    "TWSCRAPE_ACCOUNTS env var is not set.\n"
                    "Set it to a JSON array: "
                    '[{"username":"...","password":"...","email":"...","email_password":"..."}]'
                )
            try:
                accounts: Any = json.loads(raw_accounts)
                if isinstance(accounts, dict):
                    accounts = [accounts]  # single-account shorthand
            except json.JSONDecodeError as exc:
                raise RuntimeError(f"TWSCRAPE_ACCOUNTS is not valid JSON: {exc}") from exc
            if not accounts:
                raise RuntimeError("TWSCRAPE_ACCOUNTS array is empty — add at least one account")

            # ── incremental lookup ─────────────────────────────────────────
            async with httpx.AsyncClient() as lookup_client:
                since_id = await fetch_latest_x_signal_id(lookup_client, supabase_url, service_key)

            rows, skipped_count = await scrape_with_twscrape(accounts, since_id=since_id)

            # Persist before upsert so data is never lost if upsert fails
            with open(CACHE_FILE, "w", encoding="utf-8") as fh:
                json.dump(rows, fh, ensure_ascii=False, indent=2)
            print(f"Saved {len(rows)} rows to {CACHE_FILE}")

        total_fetched = len(rows)

        # Deduplicate by tweet id (API can return duplicates near page boundaries)
        seen: dict[str, dict[str, Any]] = {}
        for row in rows:
            seen[row["id"]] = row
        rows = list(seen.values())
        if total_fetched != len(rows):
            print(f"Deduplicated {total_fetched - len(rows)} duplicates → {len(rows)} unique")

        if skipped_count:
            print(f"Skipped {skipped_count} low-engagement tweets.")

        if not rows:
            print("Done. Total fetched: 0. Total upserted: 0.")
            await _complete(0, 0, 1)
            if not args.from_file:
                print("ERROR: 0 signals on a live run — failing the step.")
                sys.exit(1)
            return

        total_upserted = await upsert_all(supabase_url, service_key, rows)
        # Rough page-equivalent for scrape_runs tracking (1 page ≈ 25 tweets)
        page_equiv = max(1, total_fetched // 25)
        print(
            f"Done. Fetched: {total_fetched}. Upserted: {total_upserted}. "
            f"Skipped (low traction): {skipped_count}."
        )
        await _complete(total_fetched, total_upserted, page_equiv)

    except Exception as e:
        await _fail(str(e))
        raise


if __name__ == "__main__":
    asyncio.run(main())
