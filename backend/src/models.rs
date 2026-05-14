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
    pub scraped_at: DateTime<Utc>,
}

#[derive(Debug, Serialize)]
pub struct CategoryStat {
    pub category: String,
    pub count: i64,
}

#[derive(Debug, Serialize)]
pub struct Stats {
    pub total: i64,
    pub uncategorized: i64,
    pub categories: Vec<CategoryStat>,
    pub last_scraped_at: Option<DateTime<Utc>>,
}
