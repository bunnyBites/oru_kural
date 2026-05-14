use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

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
    pub scraped_at: DateTime<Utc>,
}


#[derive(Debug, Serialize, Deserialize)]
pub struct CategoryStatRow {
    pub category: String,
    pub tweet_count: i64,
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
