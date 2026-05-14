"""
LLM abstraction layer for tweet classification.

All classification calls go through classify_tweets() — never call an LLM SDK
directly from categorize_tweets.py.

Current backend: Google Gemini via google-genai SDK.
Future option:   Set OPENROUTER_API_KEY (+ optionally OPENROUTER_MODEL) to switch
                 to OpenRouter's OpenAI-compatible API with no structural changes.
"""

import json
import os
from typing import Any

from dotenv import load_dotenv

load_dotenv()

_CLASSIFICATION_PROMPT = """\
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


def _build_prompt(tweets: list[dict[str, Any]]) -> str:
    payload = [{"id": t["id"], "content": t["content"]} for t in tweets]
    return _CLASSIFICATION_PROMPT.format(tweets_json=json.dumps(payload, ensure_ascii=False))


def _parse_response(text: str) -> list[dict[str, Any]]:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return json.loads(text)


async def _classify_gemini(tweets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from google import genai

    model_name = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    response = await client.aio.models.generate_content(
        model=model_name,
        contents=_build_prompt(tweets),
    )
    return _parse_response(response.text)


async def _classify_openrouter(tweets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    import httpx

    model_name = os.environ.get("OPENROUTER_MODEL", "google/gemini-2.5-flash")
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}",
                "Content-Type": "application/json",
            },
            json={
                "model": model_name,
                "messages": [{"role": "user", "content": _build_prompt(tweets)}],
            },
            timeout=60,
        )
        resp.raise_for_status()
        text = resp.json()["choices"][0]["message"]["content"]
        return _parse_response(text)


async def classify_tweets(tweets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Takes a list of tweet dicts with 'id' and 'content'.
    Returns list of {"id": ..., "category": ..., "confidence": ...}.
    Switch providers here without touching categorize_tweets.py.
    """
    if os.environ.get("OPENROUTER_API_KEY"):
        return await _classify_openrouter(tweets)
    return await _classify_gemini(tweets)
