use std::future::Future;
use std::time::Duration;

use gloo_timers::future::sleep;
use serde::Deserialize;

use crate::models::{CategoryStat, CmEvent, Issue, Signal};

const API_BASE: &str = match option_env!("API_BASE_URL") {
    Some(url) => url,
    None => "http://localhost:3000",
};

#[derive(Deserialize)]
struct PagedData<T> {
    data: Vec<T>,
    meta: Meta,
}

#[derive(Deserialize)]
struct Meta {
    next_cursor: Option<String>,
}

#[derive(Deserialize)]
struct StatsData {
    data: Vec<CategoryStat>,
}

#[derive(Deserialize)]
struct IssueDetailData {
    issue: Issue,
    signals: Vec<Signal>,
    linked_event: Option<CmEvent>,
}

// Retries `f` up to 3 times with jittered exponential backoff (0 ms, 300 ms, 600 ms).
async fn with_retry<T, F, Fut>(mut f: F) -> Result<T, String>
where
    F: FnMut() -> Fut,
    Fut: Future<Output = Result<T, String>>,
{
    let delays_ms: [u64; 3] = [0, 300, 600];
    let mut last_err = String::new();
    for (attempt, &delay_ms) in delays_ms.iter().enumerate() {
        if attempt > 0 {
            sleep(Duration::from_millis(delay_ms)).await;
        }
        match f().await {
            Ok(v) => return Ok(v),
            Err(e) => last_err = e,
        }
    }
    Err(last_err)
}

pub async fn fetch_issues(
    status: Option<String>,
    category: Option<String>,
    cursor: Option<String>,
) -> Result<(Vec<Issue>, Option<String>), String> {
    with_retry(|| {
        let status = status.clone();
        let category = category.clone();
        let cursor = cursor.clone();
        async move {
            let client = reqwest::Client::new();
            let mut req = client.get(format!("{API_BASE}/issues"));
            if let Some(s) = status {
                req = req.query(&[("status", s)]);
            }
            if let Some(c) = category {
                req = req.query(&[("category", c)]);
            }
            if let Some(cur) = cursor {
                req = req.query(&[("cursor", cur)]);
            }
            let page = req
                .send()
                .await
                .map_err(|e| e.to_string())?
                .json::<PagedData<Issue>>()
                .await
                .map_err(|e| e.to_string())?;
            Ok((page.data, page.meta.next_cursor))
        }
    })
    .await
}

pub async fn fetch_issue_detail(
    id: i64,
) -> Result<(Issue, Vec<Signal>, Option<CmEvent>), String> {
    with_retry(|| async move {
        let resp = reqwest::get(format!("{API_BASE}/issues/{id}"))
            .await
            .map_err(|e| e.to_string())?
            .json::<IssueDetailData>()
            .await
            .map_err(|e| e.to_string())?;
        Ok((resp.issue, resp.signals, resp.linked_event))
    })
    .await
}

pub async fn fetch_events(
    cursor: Option<String>,
    linked_only: bool,
) -> Result<(Vec<CmEvent>, Option<String>), String> {
    with_retry(|| {
        let cursor = cursor.clone();
        async move {
            let client = reqwest::Client::new();
            let mut req = client.get(format!("{API_BASE}/events"));
            if linked_only {
                req = req.query(&[("linked", "true")]);
            }
            if let Some(cur) = cursor {
                req = req.query(&[("cursor", cur)]);
            }
            let page = req
                .send()
                .await
                .map_err(|e| e.to_string())?
                .json::<PagedData<CmEvent>>()
                .await
                .map_err(|e| e.to_string())?;
            Ok((page.data, page.meta.next_cursor))
        }
    })
    .await
}

pub async fn fetch_stats() -> Result<Vec<CategoryStat>, String> {
    with_retry(|| async move {
        let data = reqwest::get(format!("{API_BASE}/stats"))
            .await
            .map_err(|e| e.to_string())?
            .json::<StatsData>()
            .await
            .map_err(|e| e.to_string())?;
        Ok(data.data)
    })
    .await
}
