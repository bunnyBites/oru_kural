use serde::Deserialize;

#[derive(Clone, PartialEq, Deserialize)]
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
    pub score: Option<i32>,
}

#[derive(Clone, PartialEq, Deserialize)]
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

#[derive(Clone, PartialEq, Deserialize)]
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
}

#[derive(Clone, PartialEq, Deserialize)]
pub struct CategoryStat {
    pub category: String,
    pub tweet_count: i32,
}

#[derive(Clone, PartialEq, Debug)]
pub enum Tab {
    Issues,
    Events,
    Stats,
}

pub fn format_date(s: &str) -> String {
    chrono::DateTime::parse_from_rfc3339(s)
        .map(|dt| dt.format("%b %d, %Y").to_string())
        .unwrap_or_else(|_| s.get(..10).unwrap_or(s).to_string())
}
