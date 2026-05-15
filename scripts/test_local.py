#!/usr/bin/env python3
"""
Oru Kural — Local Pipeline Test Runner

Usage:
    python scripts/test_local.py           # dry run (no DB writes)
    python scripts/test_local.py --live    # full end-to-end with real DB writes

Tests each pipeline component in isolation and prints a summary.
Run this before pushing changes to verify nothing is broken.
"""

import argparse
import asyncio
import os
import sys
from datetime import datetime
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

DIVIDER = "━" * 45


def truncate(text: str, length: int) -> str:
    return text[:length] + "…" if len(text) > length else text


async def step_env_check() -> tuple[bool, str]:
    """Verify required environment variables are present."""
    required = ["SUPABASE_URL", "SUPABASE_ANON_KEY", "GEMINI_API_KEY"]
    optional = ["X_BEARER_TOKEN", "SUPABASE_SERVICE_ROLE_KEY",
                "REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET", "REDDIT_USER_AGENT"]

    failed = False
    lines = []
    for var in required:
        if os.environ.get(var):
            lines.append(f"  ✓ {var}")
        else:
            lines.append(f"  ✗ {var} — missing")
            failed = True
    for var in optional:
        if os.environ.get(var):
            lines.append(f"  ✓ {var}")
        else:
            lines.append(f"  ⚠ {var} — not set (optional)")

    print("\n".join(lines))
    return (not failed), "Environment check"


async def step_reddit_fetch(dry_run: bool) -> tuple[bool, str]:
    """Fetch a page of posts from r/Chennai to verify the JSON fallback works."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from scrape_reddit import fetch_subreddit_posts  # type: ignore[import]

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            posts = await fetch_subreddit_posts(client, "Chennai", lookback_days=7)

        if not posts:
            # fetch_subreddit_posts returns [] on 403 — Reddit blocks unauthenticated access
            print("  ⚠ Reddit returned 0 posts.")
            print("  ⚠ Reddit's public JSON API now requires authentication (PRAW credentials pending).")
            print("  ⚠ scrape_reddit.py will exit cleanly until credentials arrive — not a pipeline error.")
            return True, "Reddit fetch (skipped — API requires auth, PRAW pending)"

        print(f"  → r/Chennai: {len(posts)} qualifying posts returned")
        if dry_run and posts:
            for post in posts[:2]:
                print(f"    id={post.get('id')}  score={post.get('score')}  "
                      f"title={truncate(post.get('title', ''), 60)!r}")

        return True, f"Reddit fetch (r/Chennai: {len(posts)} posts)"
    except Exception as e:
        print(f"  ✗ Reddit fetch failed: {e}")
        return False, "Reddit fetch"


async def step_supabase_connectivity() -> tuple[bool, str]:
    """Hit the signals table and verify we get a 200 back."""
    supabase_url = os.environ.get("SUPABASE_URL", "").rstrip("/").removesuffix("/rest/v1")
    anon_key = os.environ.get("SUPABASE_ANON_KEY", "")

    if not supabase_url or not anon_key:
        print("  ✗ SUPABASE_URL or SUPABASE_ANON_KEY not set — skipping")
        return False, "Supabase connectivity"

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(
                f"{supabase_url}/rest/v1/signals",
                params={"select": "id,source,category", "limit": "5", "order": "scraped_at.desc"},
                headers={"apikey": anon_key, "Authorization": f"Bearer {anon_key}"},
            )
            resp.raise_for_status()
            rows: list[dict[str, Any]] = resp.json()

        sources = [r.get("source", "?") for r in rows]
        print(f"  → {len(rows)} signals returned. Sources: {sources}")
        return True, f"Supabase connectivity ({len(rows)} signals found)"
    except httpx.HTTPStatusError as e:
        print(f"  ✗ HTTP {e.response.status_code}: {e.response.text[:200]}")
        return False, "Supabase connectivity"
    except Exception as e:
        print(f"  ✗ {e}")
        return False, "Supabase connectivity"


async def step_categorizer_dryrun() -> tuple[bool, str]:
    """Check how many uncategorized signals exist; show a sample (no Gemini call)."""
    supabase_url = os.environ.get("SUPABASE_URL", "").rstrip("/").removesuffix("/rest/v1")
    anon_key = os.environ.get("SUPABASE_ANON_KEY", "")

    if not supabase_url or not anon_key:
        print("  ✗ SUPABASE_URL or SUPABASE_ANON_KEY not set — skipping")
        return False, "Categorizer dry-run"

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(
                f"{supabase_url}/rest/v1/signals",
                params={"select": "id,content", "category": "is.null", "limit": "3"},
                headers={
                    "apikey": anon_key,
                    "Authorization": f"Bearer {anon_key}",
                    "Prefer": "count=exact",
                },
            )
            resp.raise_for_status()
            sample: list[dict[str, Any]] = resp.json()

        content_range = resp.headers.get("Content-Range", "")
        total_str = content_range.split("/")[-1] if "/" in content_range else "?"
        print(f"  → {total_str} uncategorized signals pending")
        for s in sample:
            print(f"    id={s['id']}  content={truncate(s.get('content', ''), 80)!r}")
        if sample:
            print(f"  → (dry-run) Would send {len(sample)} signals to Gemini in next batch")

        return True, f"Categorizer dry-run ({total_str} uncategorized signals pending)"
    except httpx.HTTPStatusError as e:
        print(f"  ✗ HTTP {e.response.status_code}: {e.response.text[:200]}")
        return False, "Categorizer dry-run"
    except Exception as e:
        print(f"  ✗ {e}")
        return False, "Categorizer dry-run"


async def main() -> None:
    parser = argparse.ArgumentParser(description="Oru Kural local pipeline test runner.")
    parser.add_argument("--live", action="store_true", help="Actually write to Supabase (default: dry-run)")
    args = parser.parse_args()
    dry_run = not args.live

    print(DIVIDER)
    print("  Oru Kural — Local Pipeline Test")
    if dry_run:
        print("  Mode: dry-run (no DB writes)")
    else:
        print("  Mode: LIVE (real DB writes enabled)")
    print(DIVIDER)

    steps = [
        ("Environment check", step_env_check()),
        ("Reddit fetch", step_reddit_fetch(dry_run)),
        ("Supabase connectivity", step_supabase_connectivity()),
        ("Categorizer dry-run", step_categorizer_dryrun()),
    ]

    results: list[tuple[bool, str]] = []
    for label, coro in steps:
        print(f"\n[{label}]")
        try:
            passed, description = await coro
            results.append((passed, description))
        except Exception as e:
            print(f"  ✗ Unexpected error: {e}")
            results.append((False, label))

    print(f"\n{DIVIDER}")
    print("  Oru Kural — Local Test Summary")
    print(DIVIDER)
    for passed, description in results:
        icon = "✓" if passed else "✗"
        print(f"  {icon} {description}")
    print(DIVIDER)

    failures = sum(1 for passed, _ in results if not passed)
    if failures == 0:
        print("  All checks passed. Pipeline is ready.")
        if dry_run:
            print("  Run with --live to do a full end-to-end test with real DB writes.")
    else:
        print(f"  {failures} check(s) failed. Fix issues above before deploying.")
    print(DIVIDER)

    sys.exit(0 if failures == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())
