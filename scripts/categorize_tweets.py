"""
Categorize uncategorized tweets in Supabase using Gemini Flash 2.0.

Usage:
    python categorize_tweets.py
"""

import asyncio
import json
import os
from typing import Any

import httpx
from dotenv import load_dotenv
from google import generativeai as genai

load_dotenv()

SUPABASE_URL: str = os.environ["SUPABASE_URL"]
SUPABASE_ANON_KEY: str = os.environ["SUPABASE_ANON_KEY"]
GEMINI_API_KEY: str = os.environ["GEMINI_API_KEY"]

MODEL_NAME = "gemini-2.0-flash"
BATCH_SIZE = 40

CLASSIFICATION_PROMPT = """\
You are classifying Tamil Nadu political tweets mentioning the Chief Minister. \
Classify each tweet into EXACTLY ONE category from this list: \
[Demand, Complaint, Public Event, Welcome, Infrastructure, Health, Education, Criticism, Other]

Rules:
Demand: asking CM to do something
Complaint: reporting a problem or failure
Public Event: announcing or reporting an event
Welcome: greeting or felicitating the CM
Infrastructure: roads, water, power, transport
Health: hospitals, medicine, disease
Education: schools, colleges, scholarships
Criticism: negative political commentary
Other: anything that doesn't fit above

Return ONLY valid JSON. No explanation. No markdown. \
Format: [{{"id": "<tweet_id>", "category": "<category>", "confidence": <0.0-1.0>}}]

Tweets to classify: {tweets_json}\
"""


async def fetch_uncategorized(client: httpx.AsyncClient) -> list[dict[str, Any]]:
    """Fetch tweets with no category, newest first."""
    resp = await client.get(
        f"{SUPABASE_URL}/rest/v1/tweets",
        params={
            "category": "is.null",
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


def build_prompt(tweets: list[dict[str, Any]]) -> str:
    payload = [{"id": t["id"], "content": t["content"]} for t in tweets]
    return CLASSIFICATION_PROMPT.format(tweets_json=json.dumps(payload, ensure_ascii=False))


def call_gemini(model: genai.GenerativeModel, tweets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Send a batch to Gemini and parse the JSON response."""
    response = model.generate_content(build_prompt(tweets))
    text = response.text.strip()

    # Strip markdown fences if the model wraps its output anyway
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    results: list[dict[str, Any]] = json.loads(text)
    return results


async def update_tweet(
    client: httpx.AsyncClient, tweet_id: str, category: str, confidence: float
) -> None:
    """Patch a single tweet row with its category and confidence score."""
    resp = await client.patch(
        f"{SUPABASE_URL}/rest/v1/tweets",
        params={"id": f"eq.{tweet_id}"},
        json={"category": category, "confidence": confidence},
        headers={
            "apikey": SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
        timeout=15,
    )
    resp.raise_for_status()


async def process_batch(
    client: httpx.AsyncClient,
    model: genai.GenerativeModel,
    batch: list[dict[str, Any]],
    batch_num: int,
) -> tuple[int, int]:
    """Classify one batch and write results. Returns (ok_count, err_count)."""
    print(f"batch {batch_num}: classifying {len(batch)} tweets…")
    try:
        results = call_gemini(model, batch)
    except (json.JSONDecodeError, ValueError, Exception) as exc:
        print(f"  batch {batch_num} Gemini call failed — skipping: {exc}")
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

        try:
            await update_tweet(client, str(tweet_id), str(category), float(confidence))
            ok += 1
        except (httpx.HTTPStatusError, ValueError) as exc:
            print(f"  failed to update tweet {tweet_id}: {exc}")
            err += 1

    return ok, err


async def main() -> None:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(MODEL_NAME)

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
            ok, err = await process_batch(client, model, batch, batch_num)
            total_ok += ok
            total_err += err

    print(f"done. updated: {total_ok}, errors: {total_err}")


if __name__ == "__main__":
    asyncio.run(main())
