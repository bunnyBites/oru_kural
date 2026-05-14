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
    let tweets = sqlx::query_as::<_, Tweet>(
        "SELECT id, author_handle, author_name, content, posted_at, category, confidence, scraped_at
         FROM tweets
         WHERE ($1::text IS NULL OR category = $1)
         ORDER BY posted_at DESC
         LIMIT 200",
    )
    .bind(params.category)
    .fetch_all(&state.db)
    .await
    .map_err(|e| {
        eprintln!("list_tweets: {e}");
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    Ok(Json(tweets))
}

pub async fn get_tweet(
    State(state): State<AppState>,
    Path(id): Path<String>,
) -> Result<Json<Tweet>, StatusCode> {
    let tweet = sqlx::query_as::<_, Tweet>(
        "SELECT id, author_handle, author_name, content, posted_at, category, confidence, scraped_at
         FROM tweets
         WHERE id = $1",
    )
    .bind(id)
    .fetch_optional(&state.db)
    .await
    .map_err(|e| {
        eprintln!("get_tweet: {e}");
        StatusCode::INTERNAL_SERVER_ERROR
    })?
    .ok_or(StatusCode::NOT_FOUND)?;

    Ok(Json(tweet))
}

pub async fn get_stats(State(state): State<AppState>) -> Result<Json<Stats>, StatusCode> {
    let total = sqlx::query_scalar::<_, i64>("SELECT COUNT(*) FROM tweets")
        .fetch_one(&state.db)
        .await
        .map_err(|e| {
            eprintln!("get_stats total: {e}");
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    let uncategorized =
        sqlx::query_scalar::<_, i64>("SELECT COUNT(*) FROM tweets WHERE category IS NULL")
            .fetch_one(&state.db)
            .await
            .map_err(|e| {
                eprintln!("get_stats uncategorized: {e}");
                StatusCode::INTERNAL_SERVER_ERROR
            })?;

    let categories = sqlx::query_as::<_, CategoryStat>(
        "SELECT category, COUNT(*) AS count
         FROM tweets
         WHERE category IS NOT NULL
         GROUP BY category
         ORDER BY count DESC",
    )
    .fetch_all(&state.db)
    .await
    .map_err(|e| {
        eprintln!("get_stats categories: {e}");
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    let last_scraped_at =
        sqlx::query_scalar::<_, Option<DateTime<Utc>>>("SELECT MAX(scraped_at) FROM tweets")
            .fetch_one(&state.db)
            .await
            .map_err(|e| {
                eprintln!("get_stats last_scraped_at: {e}");
                StatusCode::INTERNAL_SERVER_ERROR
            })?;

    Ok(Json(Stats {
        total,
        uncategorized,
        categories,
        last_scraped_at,
    }))
}
