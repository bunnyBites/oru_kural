use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Signal {
    pub id: String,
    pub source: String,
    pub author_handle: Option<String>,
    pub author_name: Option<String>,
    pub content: String,
    pub translated_content: Option<String>,
    pub url: Option<String>,
    pub posted_at: Option<String>,
    pub category: Option<String>,
    pub confidence: Option<f64>,
    pub issue_id: Option<i64>,
    pub score: Option<i32>,
    pub scraped_at: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Issue {
    pub id: i64,
    pub title: String,
    pub summary: Option<String>,
    pub category: String,
    pub location: Option<String>,
    pub department: Option<String>,
    pub status: String,
    pub voice_count: i32,
    pub first_raised_at: String,
    pub last_updated_at: Option<String>,
    pub linked_event_id: Option<i64>,
    pub resolution_note: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CmEvent {
    pub id: i64,
    pub title: String,
    pub description: Option<String>,
    pub event_date: Option<String>,
    pub location: Option<String>,
    pub department: Option<String>,
    pub category: Option<String>,
    pub source_url: String,
    pub source_name: Option<String>,
    pub linked_issue_id: Option<i64>,
    pub scraped_at: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CategoryStat {
    pub category: String,
    pub tweet_count: i32,
    pub issue_count: i32,
    pub open_count: i32,
    pub last_updated: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct PageMeta {
    pub count: usize,
    pub next_cursor: Option<String>,
    pub has_more: bool,
}

#[derive(Debug, Serialize)]
pub struct PagedResponse<T: Serialize> {
    pub data: Vec<T>,
    pub meta: PageMeta,
}

#[derive(Debug, Serialize)]
pub struct IssueDetailResponse {
    pub issue: Issue,
    pub signals: Vec<Signal>,
    pub linked_event: Option<CmEvent>,
}

#[derive(Debug, Serialize)]
pub struct StatsResponse {
    pub data: Vec<CategoryStat>,
}

#[derive(Debug, Serialize)]
pub struct HealthResponse {
    pub status: &'static str,
    pub service: &'static str,
}
