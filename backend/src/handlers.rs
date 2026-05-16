use axum::{
    extract::{Path, Query, State},
    http::StatusCode,
    Json,
};
use base64::{engine::general_purpose::STANDARD as B64, Engine};
use serde::Deserialize;

use crate::{
    models::{
        CategoryStat, CmEvent, HealthResponse, Issue, IssueDetailResponse, PageMeta,
        PagedResponse, Signal, StatsResponse,
    },
    AppState,
};

const MAX_LIMIT: u32 = 100;
const DEFAULT_LIMIT: u32 = 50;

const ISSUE_COLS: &str =
    "id,title,summary,category,location,department,status,voice_count,first_raised_at,last_updated_at,linked_event_id,resolution_note";
const SIGNAL_COLS: &str =
    "id,source,author_handle,author_name,content,translated_content,url,posted_at,category,confidence,issue_id,score,scraped_at";
const SIGNAL_DETAIL_COLS: &str =
    "id,source,author_handle,content,translated_content,url,score,posted_at,category";
const EVENT_COLS: &str =
    "id,title,description,event_date,location,department,category,source_url,source_name,linked_issue_id,scraped_at";

fn auth(req: reqwest::RequestBuilder, key: &str) -> reqwest::RequestBuilder {
    req.header("apikey", key)
        .header("Authorization", format!("Bearer {key}"))
        .header("Accept", "application/json")
}

pub async fn health() -> Json<HealthResponse> {
    Json(HealthResponse {
        status: "ok",
        service: "oru-kural-backend",
    })
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
) -> Result<Json<PagedResponse<Issue>>, StatusCode> {
    let limit = params.limit.unwrap_or(DEFAULT_LIMIT).min(MAX_LIMIT);
    let fetch_limit = (limit + 1).to_string();

    let mut req = auth(
        state
            .client
            .get(format!("{}/rest/v1/issues", state.supabase_url)),
        &state.supabase_key,
    )
    .query(&[
        ("select", ISSUE_COLS),
        ("order", "last_updated_at.desc"),
        ("limit", &fetch_limit),
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
        let decoded = B64
            .decode(cursor_b64)
            .ok()
            .and_then(|b| String::from_utf8(b).ok())
            .ok_or_else(|| {
                eprintln!("list_issues: invalid cursor");
                StatusCode::BAD_REQUEST
            })?;
        req = req.query(&[("last_updated_at", format!("lt.{decoded}"))]);
    }

    let mut issues = req
        .send()
        .await
        .map_err(|e| {
            eprintln!("list_issues: {e}");
            StatusCode::INTERNAL_SERVER_ERROR
        })?
        .json::<Vec<Issue>>()
        .await
        .map_err(|e| {
            eprintln!("list_issues json: {e}");
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    let has_more = issues.len() > limit as usize;
    if has_more {
        issues.truncate(limit as usize);
    }
    let next_cursor = if has_more {
        issues
            .last()
            .and_then(|i| i.last_updated_at.as_deref())
            .map(|ts| B64.encode(ts))
    } else {
        None
    };

    Ok(Json(PagedResponse {
        meta: PageMeta {
            count: issues.len(),
            next_cursor,
            has_more,
        },
        data: issues,
    }))
}

pub async fn get_issue(
    State(state): State<AppState>,
    Path(id): Path<i64>,
) -> Result<Json<IssueDetailResponse>, StatusCode> {
    let issue_rows = auth(
        state
            .client
            .get(format!("{}/rest/v1/issues", state.supabase_url)),
        &state.supabase_key,
    )
    .query(&[("select", ISSUE_COLS), ("id", &format!("eq.{id}"))])
    .send()
    .await
    .map_err(|e| {
        eprintln!("get_issue: {e}");
        StatusCode::INTERNAL_SERVER_ERROR
    })?
    .json::<Vec<Issue>>()
    .await
    .map_err(|e| {
        eprintln!("get_issue json: {e}");
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    let issue = issue_rows
        .into_iter()
        .next()
        .ok_or(StatusCode::NOT_FOUND)?;

    let signals = auth(
        state
            .client
            .get(format!("{}/rest/v1/signals", state.supabase_url)),
        &state.supabase_key,
    )
    .query(&[
        ("select", SIGNAL_DETAIL_COLS),
        ("issue_id", &format!("eq.{id}")),
        ("order", "posted_at.desc"),
        ("limit", "20"),
    ])
    .send()
    .await
    .map_err(|e| {
        eprintln!("get_issue signals: {e}");
        StatusCode::INTERNAL_SERVER_ERROR
    })?
    .json::<Vec<Signal>>()
    .await
    .map_err(|e| {
        eprintln!("get_issue signals json: {e}");
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    let linked_event = if let Some(event_id) = issue.linked_event_id {
        auth(
            state
                .client
                .get(format!("{}/rest/v1/cm_events", state.supabase_url)),
            &state.supabase_key,
        )
        .query(&[("select", "*"), ("id", &format!("eq.{event_id}"))])
        .send()
        .await
        .map_err(|e| {
            eprintln!("get_issue event: {e}");
            StatusCode::INTERNAL_SERVER_ERROR
        })?
        .json::<Vec<CmEvent>>()
        .await
        .map_err(|e| {
            eprintln!("get_issue event json: {e}");
            StatusCode::INTERNAL_SERVER_ERROR
        })?
        .into_iter()
        .next()
    } else {
        None
    };

    Ok(Json(IssueDetailResponse {
        issue,
        signals,
        linked_event,
    }))
}

// ── Signals ──────────────────────────────────────────────────────────────────

#[derive(Deserialize)]
pub struct SignalsQuery {
    pub source: Option<String>,
    pub category: Option<String>,
    pub q: Option<String>,
    pub limit: Option<u32>,
    pub cursor: Option<String>,
}

pub async fn list_signals(
    State(state): State<AppState>,
    Query(params): Query<SignalsQuery>,
) -> Result<Json<PagedResponse<Signal>>, StatusCode> {
    let limit = params.limit.unwrap_or(DEFAULT_LIMIT).min(MAX_LIMIT);
    let fetch_limit = (limit + 1).to_string();

    let mut req = auth(
        state
            .client
            .get(format!("{}/rest/v1/signals", state.supabase_url)),
        &state.supabase_key,
    )
    .query(&[
        ("select", SIGNAL_COLS),
        ("order", "posted_at.desc"),
        ("limit", &fetch_limit),
    ]);

    if let Some(source) = &params.source {
        req = req.query(&[("source", format!("eq.{source}"))]);
    }
    if let Some(cat) = &params.category {
        req = req.query(&[("category", format!("eq.{cat}"))]);
    }
    if let Some(q) = &params.q {
        req = req.query(&[("content", format!("ilike.*{q}*"))]);
    }
    if let Some(cursor_b64) = &params.cursor {
        let decoded = B64
            .decode(cursor_b64)
            .ok()
            .and_then(|b| String::from_utf8(b).ok())
            .ok_or_else(|| {
                eprintln!("list_signals: invalid cursor");
                StatusCode::BAD_REQUEST
            })?;
        req = req.query(&[("posted_at", format!("lt.{decoded}"))]);
    }

    let mut signals = req
        .send()
        .await
        .map_err(|e| {
            eprintln!("list_signals: {e}");
            StatusCode::INTERNAL_SERVER_ERROR
        })?
        .json::<Vec<Signal>>()
        .await
        .map_err(|e| {
            eprintln!("list_signals json: {e}");
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    let has_more = signals.len() > limit as usize;
    if has_more {
        signals.truncate(limit as usize);
    }
    let next_cursor = if has_more {
        signals
            .last()
            .and_then(|s| s.posted_at.as_deref())
            .map(|ts| B64.encode(ts))
    } else {
        None
    };

    Ok(Json(PagedResponse {
        meta: PageMeta {
            count: signals.len(),
            next_cursor,
            has_more,
        },
        data: signals,
    }))
}

// ── CM Events ────────────────────────────────────────────────────────────────

#[derive(Deserialize)]
pub struct EventsQuery {
    pub category: Option<String>,
    pub linked: Option<bool>,
    pub limit: Option<u32>,
    pub cursor: Option<String>,
}

pub async fn list_events(
    State(state): State<AppState>,
    Query(params): Query<EventsQuery>,
) -> Result<Json<PagedResponse<CmEvent>>, StatusCode> {
    let limit = params.limit.unwrap_or(DEFAULT_LIMIT).min(MAX_LIMIT);
    let fetch_limit = (limit + 1).to_string();

    let mut req = auth(
        state
            .client
            .get(format!("{}/rest/v1/cm_events", state.supabase_url)),
        &state.supabase_key,
    )
    .query(&[
        ("select", EVENT_COLS),
        ("order", "event_date.desc"),
        ("limit", &fetch_limit),
    ]);

    if let Some(cat) = &params.category {
        req = req.query(&[("category", format!("eq.{cat}"))]);
    }
    if params.linked == Some(true) {
        req = req.query(&[("linked_issue_id", "not.is.null")]);
    }
    if let Some(cursor_b64) = &params.cursor {
        let decoded = B64
            .decode(cursor_b64)
            .ok()
            .and_then(|b| String::from_utf8(b).ok())
            .ok_or_else(|| {
                eprintln!("list_events: invalid cursor");
                StatusCode::BAD_REQUEST
            })?;
        req = req.query(&[("event_date", format!("lt.{decoded}"))]);
    }

    let mut events = req
        .send()
        .await
        .map_err(|e| {
            eprintln!("list_events: {e}");
            StatusCode::INTERNAL_SERVER_ERROR
        })?
        .json::<Vec<CmEvent>>()
        .await
        .map_err(|e| {
            eprintln!("list_events json: {e}");
            StatusCode::INTERNAL_SERVER_ERROR
        })?;

    let has_more = events.len() > limit as usize;
    if has_more {
        events.truncate(limit as usize);
    }
    let next_cursor = if has_more {
        events
            .last()
            .and_then(|e| e.event_date.as_deref())
            .map(|ts| B64.encode(ts))
    } else {
        None
    };

    Ok(Json(PagedResponse {
        meta: PageMeta {
            count: events.len(),
            next_cursor,
            has_more,
        },
        data: events,
    }))
}

// ── Stats ────────────────────────────────────────────────────────────────────

pub async fn get_stats(
    State(state): State<AppState>,
) -> Result<Json<StatsResponse>, StatusCode> {
    let rows = auth(
        state
            .client
            .get(format!("{}/rest/v1/category_stats", state.supabase_url)),
        &state.supabase_key,
    )
    .query(&[
        ("select", "category,tweet_count,issue_count,open_count,last_updated"),
        ("order", "tweet_count.desc"),
    ])
    .send()
    .await
    .map_err(|e| {
        eprintln!("get_stats: {e}");
        StatusCode::INTERNAL_SERVER_ERROR
    })?
    .json::<Vec<CategoryStat>>()
    .await
    .map_err(|e| {
        eprintln!("get_stats json: {e}");
        StatusCode::INTERNAL_SERVER_ERROR
    })?;

    Ok(Json(StatsResponse { data: rows }))
}
