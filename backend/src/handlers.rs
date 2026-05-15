use axum::{
    extract::{Path, Query, State},
    http::StatusCode,
    Json,
};
use base64::{engine::general_purpose::STANDARD as B64, Engine};
use serde::Deserialize;

use crate::{
    models::{CategoryStatRow, CmEvent, EventPage, Issue, IssueDetail, IssuePage, PageMeta, StatsPage, Tweet, TweetPage},
    AppState,
};

const TWEET_COLS: &str =
    "id,author_handle,author_name,content,posted_at,category,confidence,translated_content,issue_id,scraped_at";
const ISSUE_COLS: &str =
    "id,title,summary,category,location,department,status,voice_count,first_raised_at,last_updated_at,linked_event_id,resolution_note";
const EVENT_COLS: &str =
    "id,title,description,event_date,location,department,category,source_url,source_name,linked_issue_id,scraped_at";
const MAX_LIMIT: u32 = 100;
const DEFAULT_LIMIT: u32 = 50;

fn auth(req: reqwest::RequestBuilder, key: &str) -> reqwest::RequestBuilder {
    req.header("apikey", key)
        .header("Authorization", format!("Bearer {key}"))
}

pub async fn health() -> &'static str {
    "ok"
}

// ── Tweets ──────────────────────────────────────────────────────────────────

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
    let fetch_limit = limit + 1;

    let mut req = auth(
        state.client.get(format!("{}/rest/v1/tweets", state.supabase_url)),
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
    if let Some(cursor_b64) = &params.cursor {
        let decoded = B64.decode(cursor_b64).ok().and_then(|b| String::from_utf8(b).ok()).ok_or_else(|| {
            eprintln!("list_tweets: invalid cursor");
            StatusCode::BAD_REQUEST
        })?;
        req = req.query(&[("posted_at", format!("lt.{decoded}"))]);
    }

    let mut tweets = req.send().await.map_err(|e| { eprintln!("list_tweets: {e}"); StatusCode::INTERNAL_SERVER_ERROR })?
        .json::<Vec<Tweet>>().await.map_err(|e| { eprintln!("list_tweets json: {e}"); StatusCode::INTERNAL_SERVER_ERROR })?;

    let has_more = tweets.len() > limit as usize;
    if has_more { tweets.truncate(limit as usize); }
    let next_cursor = if has_more { tweets.last().map(|t| B64.encode(t.posted_at.to_rfc3339())) } else { None };
    let count = tweets.len();

    Ok(Json(TweetPage { data: tweets, meta: PageMeta { count, next_cursor, has_more } }))
}

pub async fn get_tweet(
    State(state): State<AppState>,
    Path(id): Path<String>,
) -> Result<Json<Tweet>, StatusCode> {
    let rows = auth(
        state.client.get(format!("{}/rest/v1/tweets", state.supabase_url)),
        &state.supabase_anon_key,
    )
    .query(&[("select", TWEET_COLS), ("id", &format!("eq.{id}"))])
    .send().await.map_err(|e| { eprintln!("get_tweet: {e}"); StatusCode::INTERNAL_SERVER_ERROR })?
    .json::<Vec<Tweet>>().await.map_err(|e| { eprintln!("get_tweet json: {e}"); StatusCode::INTERNAL_SERVER_ERROR })?;

    rows.into_iter().next().ok_or(StatusCode::NOT_FOUND).map(Json)
}

// ── Issues ───────────────────────────────────────────────────────────────────

#[derive(Deserialize)]
pub struct IssuesQuery {
    pub status: Option<String>,
    pub category: Option<String>,
    pub location: Option<String>,
    pub limit: Option<u32>,
    pub cursor: Option<String>,
}

pub async fn list_issues(
    State(state): State<AppState>,
    Query(params): Query<IssuesQuery>,
) -> Result<Json<IssuePage>, StatusCode> {
    let limit = params.limit.unwrap_or(DEFAULT_LIMIT).min(MAX_LIMIT);
    let fetch_limit = limit + 1;

    let mut req = auth(
        state.client.get(format!("{}/rest/v1/issues", state.supabase_url)),
        &state.supabase_anon_key,
    )
    .query(&[
        ("select", ISSUE_COLS),
        ("order", "last_updated_at.desc"),
        ("limit", &fetch_limit.to_string()),
    ]);

    if let Some(status) = &params.status {
        req = req.query(&[("status", format!("eq.{status}"))]);
    }
    if let Some(cat) = &params.category {
        req = req.query(&[("category", format!("eq.{cat}"))]);
    }
    if let Some(loc) = &params.location {
        req = req.query(&[("location", format!("ilike.*{loc}*"))]);
    }
    if let Some(cursor_b64) = &params.cursor {
        let decoded = B64.decode(cursor_b64).ok().and_then(|b| String::from_utf8(b).ok()).ok_or_else(|| {
            eprintln!("list_issues: invalid cursor");
            StatusCode::BAD_REQUEST
        })?;
        req = req.query(&[("last_updated_at", format!("lt.{decoded}"))]);
    }

    let mut issues = req.send().await.map_err(|e| { eprintln!("list_issues: {e}"); StatusCode::INTERNAL_SERVER_ERROR })?
        .json::<Vec<Issue>>().await.map_err(|e| { eprintln!("list_issues json: {e}"); StatusCode::INTERNAL_SERVER_ERROR })?;

    let has_more = issues.len() > limit as usize;
    if has_more { issues.truncate(limit as usize); }
    let next_cursor = if has_more {
        issues.last().map(|i| B64.encode(i.last_updated_at.to_rfc3339()))
    } else { None };
    let count = issues.len();

    Ok(Json(IssuePage { data: issues, meta: PageMeta { count, next_cursor, has_more } }))
}

pub async fn get_issue(
    State(state): State<AppState>,
    Path(id): Path<i64>,
) -> Result<Json<IssueDetail>, StatusCode> {
    let issue_rows = auth(
        state.client.get(format!("{}/rest/v1/issues", state.supabase_url)),
        &state.supabase_anon_key,
    )
    .query(&[("select", ISSUE_COLS), ("id", &format!("eq.{id}"))])
    .send().await.map_err(|e| { eprintln!("get_issue: {e}"); StatusCode::INTERNAL_SERVER_ERROR })?
    .json::<Vec<Issue>>().await.map_err(|e| { eprintln!("get_issue json: {e}"); StatusCode::INTERNAL_SERVER_ERROR })?;

    let issue = issue_rows.into_iter().next().ok_or(StatusCode::NOT_FOUND)?;

    // Fetch linked tweets via tweet_issue_map
    let tweets = auth(
        state.client.get(format!("{}/rest/v1/tweets", state.supabase_url)),
        &state.supabase_anon_key,
    )
    .query(&[("select", TWEET_COLS), ("issue_id", &format!("eq.{id}")), ("order", "posted_at.desc"), ("limit", "20")])
    .send().await.map_err(|e| { eprintln!("get_issue tweets: {e}"); StatusCode::INTERNAL_SERVER_ERROR })?
    .json::<Vec<serde_json::Value>>().await.map_err(|e| { eprintln!("get_issue tweets json: {e}"); StatusCode::INTERNAL_SERVER_ERROR })?;

    Ok(Json(IssueDetail {
        id: issue.id,
        title: issue.title,
        summary: issue.summary,
        category: issue.category,
        location: issue.location,
        department: issue.department,
        status: issue.status,
        voice_count: issue.voice_count,
        first_raised_at: issue.first_raised_at,
        last_updated_at: issue.last_updated_at,
        linked_event_id: issue.linked_event_id,
        resolution_note: issue.resolution_note,
        tweets,
    }))
}

// ── CM Events ────────────────────────────────────────────────────────────────

#[derive(Deserialize)]
pub struct EventsQuery {
    pub limit: Option<u32>,
    pub cursor: Option<String>,
}

pub async fn list_events(
    State(state): State<AppState>,
    Query(params): Query<EventsQuery>,
) -> Result<Json<EventPage>, StatusCode> {
    let limit = params.limit.unwrap_or(DEFAULT_LIMIT).min(MAX_LIMIT);
    let fetch_limit = limit + 1;

    let mut req = auth(
        state.client.get(format!("{}/rest/v1/cm_events", state.supabase_url)),
        &state.supabase_anon_key,
    )
    .query(&[
        ("select", EVENT_COLS),
        ("order", "event_date.desc"),
        ("limit", &fetch_limit.to_string()),
    ]);

    if let Some(cursor_b64) = &params.cursor {
        let decoded = B64.decode(cursor_b64).ok().and_then(|b| String::from_utf8(b).ok()).ok_or_else(|| {
            eprintln!("list_events: invalid cursor");
            StatusCode::BAD_REQUEST
        })?;
        req = req.query(&[("event_date", format!("lt.{decoded}"))]);
    }

    let mut events = req.send().await.map_err(|e| { eprintln!("list_events: {e}"); StatusCode::INTERNAL_SERVER_ERROR })?
        .json::<Vec<CmEvent>>().await.map_err(|e| { eprintln!("list_events json: {e}"); StatusCode::INTERNAL_SERVER_ERROR })?;

    let has_more = events.len() > limit as usize;
    if has_more { events.truncate(limit as usize); }
    let next_cursor = if has_more {
        events.last().and_then(|e| e.event_date.map(|d| B64.encode(d.to_rfc3339())))
    } else { None };
    let count = events.len();

    Ok(Json(EventPage { data: events, meta: PageMeta { count, next_cursor, has_more } }))
}

// ── Stats ────────────────────────────────────────────────────────────────────

pub async fn get_stats(State(state): State<AppState>) -> Result<Json<StatsPage>, StatusCode> {
    let rows = auth(
        state.client.get(format!("{}/rest/v1/category_stats", state.supabase_url)),
        &state.supabase_anon_key,
    )
    .query(&[
        ("select", "category,tweet_count,issue_count,open_count,resolved_count,last_updated"),
        ("order", "issue_count.desc"),
    ])
    .send().await.map_err(|e| { eprintln!("get_stats: {e}"); StatusCode::INTERNAL_SERVER_ERROR })?
    .json::<Vec<CategoryStatRow>>().await.map_err(|e| { eprintln!("get_stats json: {e}"); StatusCode::INTERNAL_SERVER_ERROR })?;

    Ok(Json(StatsPage { data: rows }))
}
