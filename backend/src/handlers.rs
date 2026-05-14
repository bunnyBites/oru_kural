use axum::{
    extract::{Path, Query, State},
    http::StatusCode,
    Json,
};
use base64::{engine::general_purpose::STANDARD as B64, Engine};
use serde::Deserialize;

use crate::{
    models::{CategoryStatRow, PageMeta, StatsPage, Tweet, TweetPage},
    AppState,
};

const TWEET_COLS: &str =
    "id,author_handle,author_name,content,posted_at,category,confidence,translated_content,scraped_at";
const MAX_LIMIT: u32 = 100;
const DEFAULT_LIMIT: u32 = 50;

fn auth(req: reqwest::RequestBuilder, key: &str) -> reqwest::RequestBuilder {
    req.header("apikey", key)
        .header("Authorization", format!("Bearer {key}"))
}

pub async fn health() -> &'static str {
    "ok"
}

#[derive(Deserialize)]
pub struct TweetsQuery {
    pub category: Option<String>,
    pub q: Option<String>,
    pub limit: Option<u32>,
    pub cursor: Option<String>,
}

pub async fn list_tweets(
    State(state): State<AppState>,
    Query(params): Query<TweetsQuery>,
) -> Result<Json<TweetPage>, StatusCode> {
    let limit = params.limit.unwrap_or(DEFAULT_LIMIT).min(MAX_LIMIT);
    // Fetch one extra to detect whether more pages exist
    let fetch_limit = limit + 1;

    let mut req = auth(
        state
            .client
            .get(format!("{}/rest/v1/tweets", state.supabase_url)),
        &state.supabase_anon_key,
    )
    .query(&[
        ("select", TWEET_COLS),
        ("order", "posted_at.desc"),
        ("limit", &fetch_limit.to_string()),
    ]);

    if let Some(cat) = &params.category {
        req = req.query(&[("category", format!("eq.{cat}"))]);
    }

    if let Some(q) = &params.q {
        req = req.query(&[("content", format!("ilike.*{q}*"))]);
    }

    // Decode cursor (base64 of posted_at ISO timestamp) for keyset pagination
    if let Some(cursor_b64) = &params.cursor {
        let decoded = B64
            .decode(cursor_b64)
            .ok()
            .and_then(|b| String::from_utf8(b).ok())
            .ok_or_else(|| {
                eprintln!("list_tweets: invalid cursor");
                StatusCode::BAD_REQUEST
            })?;
        req = req.query(&[("posted_at", format!("lt.{decoded}"))]);
    }

    let mut tweets = req
        .send()
        .await
        .map_err(|e| {
            eprintln!("list_tweets: {e}");
            StatusCode::INTERNAL_SERVER_ERROR
        })?
        .json::<Vec<Tweet>>()
        .await
        .map_err(|e| {
            eprintln!("list_tweets json: {e}");
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    let has_more = tweets.len() > limit as usize;
    if has_more {
        tweets.truncate(limit as usize);
    }

    let next_cursor = if has_more {
        tweets
            .last()
            .map(|t| B64.encode(t.posted_at.to_rfc3339()))
    } else {
        None
    };

    let count = tweets.len();
    Ok(Json(TweetPage {
        data: tweets,
        meta: PageMeta {
            count,
            next_cursor,
            has_more,
        },
    }))
}

pub async fn get_tweet(
    State(state): State<AppState>,
    Path(id): Path<String>,
) -> Result<Json<Tweet>, StatusCode> {
    let rows = auth(
        state
            .client
            .get(format!("{}/rest/v1/tweets", state.supabase_url)),
        &state.supabase_anon_key,
    )
    .query(&[("select", TWEET_COLS), ("id", &format!("eq.{id}"))])
    .send()
    .await
    .map_err(|e| {
        eprintln!("get_tweet: {e}");
        StatusCode::INTERNAL_SERVER_ERROR
    })?
    .json::<Vec<Tweet>>()
    .await
    .map_err(|e| {
        eprintln!("get_tweet json: {e}");
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    rows.into_iter().next().ok_or(StatusCode::NOT_FOUND).map(Json)
}

pub async fn get_stats(State(state): State<AppState>) -> Result<Json<StatsPage>, StatusCode> {
    let rows = auth(
        state
            .client
            .get(format!("{}/rest/v1/category_stats", state.supabase_url)),
        &state.supabase_anon_key,
    )
    .query(&[
        ("select", "category,tweet_count,last_updated"),
        ("order", "tweet_count.desc"),
    ])
    .send()
    .await
    .map_err(|e| {
        eprintln!("get_stats: {e}");
        StatusCode::INTERNAL_SERVER_ERROR
    })?
    .json::<Vec<CategoryStatRow>>()
    .await
    .map_err(|e| {
        eprintln!("get_stats json: {e}");
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    Ok(Json(StatsPage { data: rows }))
}
