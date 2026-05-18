"""
Scrape CM Helpline (cmhelpline.tnega.org) grievance category counts and store
them as signals in Supabase so the dashboard can surface citizen distress trends.

The CM Helpline portal ("Mudhalvarin Mugavari") is the official 2026 TVK government
grievance channel (1100 toll-free). Individual grievances are login-gated, but the
public landing page exposes aggregate category counts via its stats widget.

We store each category's count as a synthetic signal with source="cm_helpline"
so the existing clustering pipeline can surface which departments are overloaded.

Usage:
    python scrape_grievances.py

Environment:
    SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY (from .env at repo root)
"""

import asyncio
import json
import os
import re
from datetime import datetime, timezone
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

HELPLINE_URL = "https://cmhelpline.tnega.org/portal/en/home"
GCC_PGR_URL = "https://gccservices.in/pgr"


def _supa_headers(key: str) -> dict[str, str]:
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


async def fetch_helpline_stats(client: httpx.AsyncClient) -> list[dict[str, Any]]:
    """
    Scrape aggregate grievance stats from the CM Helpline public landing page.
    Returns a list of {category, count} dicts.
    Falls back to empty list if the page structure changes.
    """
    stats: list[dict[str, Any]] = []
    try:
        resp = await client.get(
            HELPLINE_URL,
            timeout=20,
            follow_redirects=True,
            headers={"User-Agent": "OruKural/2.0 civic-dashboard (research)"},
        )
        if not resp.is_success:
            print(f"  CM Helpline: HTTP {resp.status_code} — skipping")
            return stats

        html = resp.text

        # The portal renders department-wise counts in data-count or similar attrs.
        # Try multiple patterns since Oracle APEX apps vary their markup.
        # Pattern 1: data-value="NNN" near a department label
        count_blocks = re.findall(
            r'<[^>]+data-value=["\'](\d+)["\'][^>]*>.*?<[^>]+class=["\'][^"\']*label[^"\']*["\'][^>]*>(.*?)</[^>]+>',
            html, re.DOTALL | re.IGNORECASE
        )
        for count_str, label_raw in count_blocks:
            label = re.sub(r"<[^>]+>", "", label_raw).strip()
            if label and count_str.isdigit():
                stats.append({"category": label, "count": int(count_str)})

        # Pattern 2: number + label pairs in stat cards (common Bootstrap / APEX pattern)
        if not stats:
            card_pairs = re.findall(
                r'<(?:h\d|span|div)[^>]*class=["\'][^"\']*(?:count|stat|number)[^"\']*["\'][^>]*>(\d[\d,]*)</[^>]+>.*?'
                r'<(?:p|span|div)[^>]*>([\w\s/]+)</[^>]+>',
                html, re.DOTALL | re.IGNORECASE
            )
            for count_str, label_raw in card_pairs:
                label = re.sub(r"<[^>]+>", "", label_raw).strip()
                count = int(count_str.replace(",", ""))
                if label and count > 0:
                    stats.append({"category": label, "count": count})

        print(f"  CM Helpline: {len(stats)} category stats found")
    except Exception as exc:
        print(f"  warning: CM Helpline scrape failed: {exc}")
    return stats


async def fetch_gcc_pgr_stats(client: httpx.AsyncClient) -> list[dict[str, Any]]:
    """
    Scrape Chennai GCC Public Grievance Redressal summary counts.
    Returns [{category, count}] or empty list on failure.
    """
    stats: list[dict[str, Any]] = []
    try:
        resp = await client.get(
            GCC_PGR_URL,
            timeout=20,
            follow_redirects=True,
            headers={"User-Agent": "OruKural/2.0 civic-dashboard (research)"},
        )
        if not resp.is_success:
            print(f"  GCC PGR: HTTP {resp.status_code} — skipping")
            return stats

        html = resp.text
        pairs = re.findall(
            r'<(?:h\d|span|div|td)[^>]*>(\d[\d,]*)</[^>]+>\s*<(?:p|td|span|div)[^>]*>([\w\s/&;]+)</[^>]+>',
            html, re.DOTALL | re.IGNORECASE
        )
        for count_str, label_raw in pairs:
            label = re.sub(r"<[^>]+>", "", label_raw).strip()
            count = int(count_str.replace(",", ""))
            if label and 10 < len(label) < 80 and count > 0:
                stats.append({"category": f"GCC: {label}", "count": count})

        print(f"  GCC PGR: {len(stats)} category stats found")
    except Exception as exc:
        print(f"  warning: GCC PGR scrape failed: {exc}")
    return stats


def build_signals(
    helpline_stats: list[dict[str, Any]],
    gcc_stats: list[dict[str, Any]],
    scraped_at: str,
) -> list[dict[str, Any]]:
    """
    Convert grievance category counts into synthetic signal rows.
    Each signal represents one category snapshot — content encodes the count
    so the NLP pipeline can read it, and source="cm_helpline" / "gcc_pgr"
    distinguishes them from X/Reddit signals.
    """
    signals: list[dict[str, Any]] = []
    for stat in helpline_stats:
        signals.append({
            "source": "cm_helpline",
            "external_id": f"helpline_{scraped_at[:10]}_{stat['category'][:40]}",
            "content": f"CM Helpline grievance category '{stat['category']}': {stat['count']} pending petitions as of {scraped_at[:10]}.",
            "author": "cm_helpline_bot",
            "scraped_at": scraped_at,
            "category": "Complaint",
            "confidence": 1.0,
            "metadata": json.dumps({"count": stat["count"], "portal": "cmhelpline.tnega.org"}),
        })
    for stat in gcc_stats:
        signals.append({
            "source": "gcc_pgr",
            "external_id": f"gcc_{scraped_at[:10]}_{stat['category'][:40]}",
            "content": f"GCC Chennai grievance '{stat['category']}': {stat['count']} cases as of {scraped_at[:10]}.",
            "author": "gcc_pgr_bot",
            "scraped_at": scraped_at,
            "category": "Complaint",
            "confidence": 1.0,
            "metadata": json.dumps({"count": stat["count"], "portal": "gccservices.in/pgr"}),
        })
    return signals


async def upsert_signals(
    client: httpx.AsyncClient,
    supabase_url: str,
    service_key: str,
    signals: list[dict[str, Any]],
) -> int:
    if not signals:
        return 0
    resp = await client.post(
        f"{supabase_url}/rest/v1/signals",
        json=signals,
        headers={
            **_supa_headers(service_key),
            "Prefer": "resolution=merge-duplicates",
        },
        timeout=30,
    )
    if not resp.is_success:
        raise RuntimeError(f"Supabase upsert signals {resp.status_code}: {resp.text}")
    return len(signals)


async def main() -> None:
    supabase_url = os.environ["SUPABASE_URL"].rstrip("/").removesuffix("/rest/v1")
    service_key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    scraped_at = datetime.now(timezone.utc).isoformat()

    run_id: int | None = None
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{supabase_url}/rest/v1/scrape_runs",
                json={"script": "scrape_grievances", "status": "running"},
                headers={**_supa_headers(service_key), "Prefer": "return=representation"},
                timeout=15,
            )
            resp.raise_for_status()
            run_id = resp.json()[0]["id"]
        except Exception as exc:
            print(f"warning: scrape_runs tracking unavailable: {exc}")

    try:
        async with httpx.AsyncClient() as client:
            print("Fetching CM Helpline stats…")
            helpline_stats = await fetch_helpline_stats(client)

            print("Fetching GCC PGR stats…")
            gcc_stats = await fetch_gcc_pgr_stats(client)

        signals = build_signals(helpline_stats, gcc_stats, scraped_at)
        print(f"  built {len(signals)} synthetic signals")

        if signals:
            async with httpx.AsyncClient() as client:
                upserted = await upsert_signals(client, supabase_url, service_key, signals)
            print(f"Done. Upserted: {upserted} grievance signals.")
        else:
            print("No grievance data scraped — portals may have changed markup. No signals written.")
            upserted = 0

        if run_id is not None:
            async with httpx.AsyncClient() as tc:
                try:
                    await tc.patch(
                        f"{supabase_url}/rest/v1/scrape_runs",
                        params={"id": f"eq.{run_id}"},
                        json={
                            "status": "completed",
                            "completed_at": scraped_at,
                            "tweets_fetched": len(helpline_stats) + len(gcc_stats),
                            "tweets_upserted": upserted,
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
                            "completed_at": datetime.now(timezone.utc).isoformat(),
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
