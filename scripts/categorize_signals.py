"""
Categorize uncategorized signals (from X and Reddit) using classifier_rules then Gemini.

Usage:
    python categorize_signals.py
"""

import asyncio
import json
import os
import random
import sys
from datetime import datetime, timezone
from typing import Any

import httpx
from dotenv import load_dotenv

load_dotenv()

BATCH_SIZE = 40
DEDUP_THRESHOLD = 0.85

_CATEGORIZE_PROMPT = """\
You are processing Tamil Nadu public posts mentioning the Chief Minister (@CMOTamilnadu).
Posts may be from X (Twitter) or Reddit — treat them identically.

For each post, do TWO things:
1. Classify into EXACTLY ONE category:
   [Demand, Complaint, Public Event, Welcome, Infrastructure, Health, Education, Criticism, Other]
2. Translate to English. If already in English, copy as-is.

Return ONLY valid JSON. No explanation. No markdown.
Format:
[{{
  "id": "<signal_id>",
  "category": "<category>",
  "confidence": <0.0-1.0>,
  "translated_content": "<English text>"
}}]

Posts:
{signals_json}\
"""


async def backoff_sleep(attempt: int, base: float = 2.0, cap: float = 60.0) -> None:
    delay = min(base ** attempt + random.uniform(0, 1), cap)
    print(f"  Backoff: sleeping {delay:.1f}s")
    await asyncio.sleep(delay)


def _supa_headers(key: str) -> dict[str, str]:
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def _word_set(text: str) -> set[str]:
    return set(text.lower().split())


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


async def fetch_uncategorized_signals(
    client: httpx.AsyncClient,
    anon_key: str,
    supabase_url: str,
) -> list[dict[str, Any]]:
    resp = await client.get(
        f"{supabase_url}/rest/v1/signals",
        params={
            "select": "id,content,source",
            "category": "is.null",
            "duplicate_of": "is.null",
            "order": "scraped_at.asc",
            "limit": "500",
        },
        headers={
            "apikey": anon_key,
            "Authorization": f"Bearer {anon_key}",
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


async def mark_duplicates(
    client: httpx.AsyncClient,
    service_key: str,
    supabase_url: str,
    duplicate_rows: list[dict[str, str]],
) -> None:
    for row in duplicate_rows:
        resp = await client.patch(
            f"{supabase_url}/rest/v1/signals",
            params={"id": f"eq.{row['id']}"},
            json={"duplicate_of": row["duplicate_of"]},
            headers={**_supa_headers(service_key), "Prefer": "return=minimal"},
            timeout=15,
        )
        if not resp.is_success:
            print(f"  warning: failed to mark duplicate {row['id']}: {resp.text}")


async def upsert_classified(
    client: httpx.AsyncClient,
    service_key: str,
    supabase_url: str,
    rows: list[dict[str, Any]],
) -> None:
    for row in rows:
        signal_id = row.get("id")
        if not signal_id:
            continue
        payload: dict[str, Any] = {"category": row.get("category"), "confidence": row.get("confidence")}
        if "translated_content" in row:
            payload["translated_content"] = row["translated_content"]
        resp = await client.patch(
            f"{supabase_url}/rest/v1/signals",
            params={"id": f"eq.{signal_id}"},
            json=payload,
            headers={**_supa_headers(service_key), "Prefer": "return=minimal"},
            timeout=15,
        )
        if not resp.is_success:
            print(f"  warning: failed to patch signal {signal_id}: {resp.text}")


async def categorize_with_gemini(
    signals: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    from google import genai

    model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    payload = [{"id": s["id"], "content": s["content"]} for s in signals]
    prompt = _CATEGORIZE_PROMPT.format(signals_json=json.dumps(payload, ensure_ascii=False))

    for attempt in range(4):
        try:
            response = await client.aio.models.generate_content(model=model_name, contents=prompt)
            text = response.text.strip()
            if text.startswith("```"):
                lines = text.splitlines()
                text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
            return json.loads(text)
        except Exception as exc:
            exc_str = str(exc)
            if "ResourceExhausted" in type(exc).__name__ or "resource_exhausted" in exc_str.lower():
                print("  Gemini quota exhausted — sleeping 60s…")
                await asyncio.sleep(60)
            else:
                print(f"  Gemini categorize call failed (attempt {attempt + 1}): {exc}")
                if attempt < 3:
                    await backoff_sleep(attempt)
                else:
                    raise

    raise RuntimeError("Gemini categorization failed after 4 attempts")


async def main() -> None:
    supabase_url = os.environ["SUPABASE_URL"].rstrip("/").removesuffix("/rest/v1")
    service_key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    anon_key = os.environ["SUPABASE_ANON_KEY"]

    run_id: int | None = None
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{supabase_url}/rest/v1/scrape_runs",
                json={"script": "categorize_signals", "status": "running"},
                headers={**_supa_headers(service_key), "Prefer": "return=representation"},
                timeout=15,
            )
            resp.raise_for_status()
            run_id = resp.json()[0]["id"]
        except Exception as exc:
            print(f"warning: scrape_runs tracking unavailable: {exc}")

    try:
        # Add scripts/ to sys.path so we can import classifier_rules
        scripts_dir = os.path.dirname(os.path.abspath(__file__))
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        from classifier_rules import classify_by_rules  # type: ignore[import]

        async with httpx.AsyncClient() as client:
            signals = await fetch_uncategorized_signals(client, anon_key, supabase_url)

        if not signals:
            print("No uncategorized signals found. Exiting.")
            if run_id is not None:
                async with httpx.AsyncClient() as tc:
                    await tc.patch(
                        f"{supabase_url}/rest/v1/scrape_runs",
                        params={"id": f"eq.{run_id}"},
                        json={"status": "completed", "completed_at": datetime.now(timezone.utc).isoformat(),
                              "tweets_fetched": 0, "tweets_upserted": 0},
                        headers={**_supa_headers(service_key), "Prefer": "return=minimal"},
                        timeout=15,
                    )
            return

        # Deduplicate within the batch using Jaccard similarity on word sets.
        # Signals above the threshold are flagged in-DB and excluded from Gemini.
        reference_sets: list[tuple[str, set[str]]] = []
        unique_signals: list[dict[str, Any]] = []
        duplicate_rows: list[dict[str, str]] = []

        for signal in signals:
            ws = _word_set(signal["content"])
            best_sim = 0.0
            best_ref_id: str | None = None
            for ref_id, ref_ws in reference_sets:
                sim = _jaccard(ws, ref_ws)
                if sim > best_sim:
                    best_sim = sim
                    best_ref_id = ref_id
            if best_sim >= DEDUP_THRESHOLD and best_ref_id:
                duplicate_rows.append({"id": signal["id"], "duplicate_of": best_ref_id})
            else:
                reference_sets.append((signal["id"], ws))
                unique_signals.append(signal)

        if duplicate_rows:
            async with httpx.AsyncClient() as dup_client:
                await mark_duplicates(dup_client, service_key, supabase_url, duplicate_rows)
            print(f"Marked {len(duplicate_rows)} near-duplicate signals (threshold={DEDUP_THRESHOLD}).")

        rule_classified: list[dict[str, Any]] = []
        gemini_batch: list[dict[str, Any]] = []

        for signal in unique_signals:
            result = classify_by_rules(signal["id"], signal["content"])
            if result:
                rule_classified.append(result)
            else:
                gemini_batch.append(signal)

        print(f"Rules classified {len(rule_classified)} signals. Sending {len(gemini_batch)} to Gemini.")

        total_upserted = 0

        if rule_classified:
            async with httpx.AsyncClient() as client:
                await upsert_classified(client, service_key, supabase_url, rule_classified)
            total_upserted += len(rule_classified)
            print(f"Upserted {len(rule_classified)} rule-classified signals.")

        total_batches = (len(gemini_batch) + BATCH_SIZE - 1) // BATCH_SIZE

        async with httpx.AsyncClient() as client:
            for i in range(0, len(gemini_batch), BATCH_SIZE):
                batch = gemini_batch[i : i + BATCH_SIZE]
                batch_num = i // BATCH_SIZE + 1
                print(f"Gemini batch {batch_num}/{total_batches} ({len(batch)} signals)...")

                try:
                    results = await categorize_with_gemini(batch)
                except Exception as exc:
                    print(f"  batch {batch_num} failed — skipping: {exc}")
                    continue

                valid_results = []
                for r in results:
                    if not r.get("id"):
                        print(f"  warning: Gemini result missing id — skipping: {r}")
                        continue
                    valid_results.append(r)

                if valid_results:
                    await upsert_classified(client, service_key, supabase_url, valid_results)
                    total_upserted += len(valid_results)

                try:
                    await client.post(
                        f"{supabase_url}/rest/v1/rpc/refresh_category_stats",
                        headers=_supa_headers(service_key),
                        timeout=15,
                    )
                except Exception as exc:
                    print(f"  warning: refresh_category_stats failed: {exc}")

        print(f"Done. Total signals: {len(signals)}. Total categorized: {total_upserted}.")

        if run_id is not None:
            async with httpx.AsyncClient() as tc:
                try:
                    await tc.patch(
                        f"{supabase_url}/rest/v1/scrape_runs",
                        params={"id": f"eq.{run_id}"},
                        json={
                            "status": "completed",
                            "completed_at": datetime.now(timezone.utc).isoformat(),
                            "tweets_fetched": len(signals),
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
