use serde::Deserialize;

#[derive(Clone, PartialEq, Deserialize)]
pub struct Tweet {
    pub id: String,
    pub author_handle: String,
    pub author_name: Option<String>,
    pub content: String,
    pub posted_at: String,
    pub category: Option<String>,
    pub confidence: Option<f64>,
    pub translated_content: Option<String>,
    pub scraped_at: String,
}

#[derive(Clone, PartialEq)]
pub struct AppState {
    pub tweets: Vec<Tweet>,
    pub filtered_category: Option<String>,
    pub search_query: String,
    pub loading: bool,
    pub dark_mode: bool,
}

pub fn format_ts(s: &str) -> String {
    chrono::DateTime::parse_from_rfc3339(s)
        .map(|dt| dt.format("%b %d, %H:%M").to_string())
        .unwrap_or_else(|_| s.get(..10).unwrap_or(s).to_string())
}
