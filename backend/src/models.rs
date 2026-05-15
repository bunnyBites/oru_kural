use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use serde_json::Value;

#[derive(Debug, Serialize, Deserialize)]
pub struct Tweet {
    pub id: String,
    pub author_handle: String,
    pub author_name: Option<String>,
    pub content: String,
    pub posted_at: DateTime<Utc>,
    pub category: Option<String>,
    pub confidence: Option<f32>,
    pub translated_content: Option<String>,
    pub issue_id: Option<i64>,
    pub scraped_at: DateTime<Utc>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct Issue {
    pub id: i64,
    pub title: String,
    pub summary: Option<String>,
    pub category: String,
    pub location: Option<String>,
    pub department: Option<String>,
    pub status: String,
    pub voice_count: i32,
    pub first_raised_at: DateTime<Utc>,
    pub last_updated_at: DateTime<Utc>,
    pub linked_event_id: Option<i64>,
    pub resolution_note: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct IssueDetail {
    pub id: i64,
    pub title: String,
    pub summary: Option<String>,
    pub category: String,
    pub location: Option<String>,
    pub department: Option<String>,
    pub status: String,
    pub voice_count: i32,
    pub first_raised_at: DateTime<Utc>,
    pub last_updated_at: DateTime<Utc>,
    pub linked_event_id: Option<i64>,
    pub resolution_note: Option<String>,
    pub tweets: Vec<Value>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct CmEvent {
    pub id: i64,
    pub title: String,
    pub description: Option<String>,
    pub event_date: Option<DateTime<Utc>>,
    pub location: Option<String>,
    pub department: Option<String>,
    pub category: Option<String>,
    pub source_url: String,
    pub source_name: Option<String>,
    pub linked_issue_id: Option<i64>,
    pub scraped_at: DateTime<Utc>,
}

#[derive(Debug, Serialize)]
pub struct IssuePage {
    pub data: Vec<Issue>,
    pub meta: PageMeta,
}

#[derive(Debug, Serialize)]
pub struct EventPage {
    pub data: Vec<CmEvent>,
    pub meta: PageMeta,
}


#[derive(Debug, Serialize, Deserialize)]
pub struct CategoryStatRow {
    pub category: String,
    pub tweet_count: i64,
    pub issue_count: Option<i64>,
    pub open_count: Option<i64>,
    pub resolved_count: Option<i64>,
    pub last_updated: DateTime<Utc>,
}

#[derive(Debug, Serialize)]
pub struct PageMeta {
    pub count: usize,
    pub next_cursor: Option<String>,
    pub has_more: bool,
}

#[derive(Debug, Serialize)]
pub struct TweetPage {
    pub data: Vec<Tweet>,
    pub meta: PageMeta,
}

#[derive(Debug, Serialize)]
pub struct StatsPage {
    pub data: Vec<CategoryStatRow>,
}
