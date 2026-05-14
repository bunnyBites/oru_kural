use chrono::{DateTime, Utc};
use serde::Deserialize;

const BACKEND: &str = "http://localhost:3000";

#[derive(Debug, Clone, Deserialize, PartialEq)]
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

#[derive(Debug, Clone, Deserialize)]
pub struct CategoryStat {
    pub category: String,
    pub count: i64,
}

#[derive(Debug, Clone, Deserialize)]
pub struct Stats {
    pub total: i64,
    pub uncategorized: i64,
    pub categories: Vec<CategoryStat>,
    pub last_scraped_at: Option<DateTime<Utc>>,
}

pub async fn fetch_tweets(category: Option<String>) -> Result<Vec<Tweet>, String> {
    let client = reqwest::Client::new();
    let mut req = client.get(format!("{BACKEND}/api/tweets"));
    if let Some(cat) = category {
        req = req.query(&[("category", cat)]);
    }
    req.send()
        .await
        .map_err(|e| e.to_string())?
        .json::<Vec<Tweet>>()
        .await
        .map_err(|e| e.to_string())
}

pub async fn fetch_tweet(id: String) -> Result<Tweet, String> {
    reqwest::get(format!("{BACKEND}/api/tweets/{id}"))
        .await
        .map_err(|e| e.to_string())?
        .json::<Tweet>()
        .await
        .map_err(|e| e.to_string())
}

pub async fn fetch_stats() -> Result<Stats, String> {
    reqwest::get(format!("{BACKEND}/api/stats"))
        .await
        .map_err(|e| e.to_string())?
        .json::<Stats>()
        .await
        .map_err(|e| e.to_string())
}
