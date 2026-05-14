use std::collections::HashMap;

use axum::{
    extract::{Path, Query, State},
    http::StatusCode,
    Json,
};
use chrono::{DateTime, Utc};
use serde::Deserialize;

use crate::{
    models::{CategoryStat, Stats, Tweet},
    AppState,
};

const TWEET_COLS: &str =
    "id,author_handle,author_name,content,posted_at,category,confidence,translated_content,scraped_at";

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
}

pub async fn list_tweets(
    State(state): State<AppState>,
    Query(params): Query<TweetsQuery>,
) -> Result<Json<Vec<Tweet>>, StatusCode> {
    let mut req = auth(
        state
            .client
            .get(format!("{}/rest/v1/tweets", state.supabase_url)),
        &state.supabase_anon_key,
    )
    .query(&[
        ("select", TWEET_COLS),
        ("order", "posted_at.desc"),
        ("limit", "200"),
    ]);

    if let Some(cat) = params.category {
        req = req.query(&[("category", format!("eq.{cat}"))]);
    }

    let tweets = req
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

    Ok(Json(tweets))
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

#[derive(Deserialize)]
struct TweetMeta {
    category: Option<String>,
    scraped_at: DateTime<Utc>,
}

pub async fn get_stats(State(state): State<AppState>) -> Result<Json<Stats>, StatusCode> {
    // One lightweight query — aggregate entirely in Rust.
    // Fine at current scale (≤500 rows, two small columns).
    let metas = auth(
        state
            .client
            .get(format!("{}/rest/v1/tweets", state.supabase_url)),
        &state.supabase_anon_key,
    )
    .query(&[("select", "category,scraped_at")])
    .send()
    .await
    .map_err(|e| {
        eprintln!("get_stats: {e}");
        StatusCode::INTERNAL_SERVER_ERROR
    })?
    .json::<Vec<TweetMeta>>()
    .await
    .map_err(|e| {
        eprintln!("get_stats json: {e}");
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    let total = metas.len() as i64;
    let uncategorized = metas.iter().filter(|m| m.category.is_none()).count() as i64;

    let mut counts: HashMap<String, i64> = HashMap::new();
    let mut last_scraped_at: Option<DateTime<Utc>> = None;

    for meta in &metas {
        if let Some(cat) = &meta.category {
            *counts.entry(cat.clone()).or_insert(0) += 1;
        }
        if last_scraped_at.map_or(true, |ts| meta.scraped_at > ts) {
            last_scraped_at = Some(meta.scraped_at);
        }
    }

    let mut categories: Vec<CategoryStat> = counts
        .into_iter()
        .map(|(category, count)| CategoryStat { category, count })
        .collect();
    categories.sort_by(|a, b| b.count.cmp(&a.count));

    Ok(Json(Stats {
        total,
        uncategorized,
        categories,
        last_scraped_at,
    }))
}
