use serde::Deserialize;

use crate::models::Tweet;

const BACKEND: &str = "https://oru-kural-backend.fly.dev";

#[derive(Deserialize)]
struct TweetPage {
    data: Vec<Tweet>,
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
        .json::<TweetPage>()
        .await
        .map(|p| p.data)
        .map_err(|e| e.to_string())
}

pub async fn fetch_tweet(id: String) -> Result<Tweet, String> {
    let resp = reqwest::get(format!("{BACKEND}/api/tweets/{id}"))
        .await
        .map_err(|e| e.to_string())?;
    if !resp.status().is_success() {
        return Err(format!("HTTP {}", resp.status()));
    }
    resp.json::<Tweet>().await.map_err(|e| e.to_string())
}
