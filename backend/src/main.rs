mod handlers;
mod models;

use axum::{Router, routing::get};
use tower_http::cors::{Any, CorsLayer};

#[derive(Clone)]
pub struct AppState {
    pub client: reqwest::Client,
    pub supabase_url: String,
    pub supabase_anon_key: String,
}

#[tokio::main]
async fn main() {
    dotenvy::dotenv().ok();

    // Strip any trailing /rest/v1[/] so the value is always the bare project URL.
    let supabase_url = std::env::var("SUPABASE_URL")
        .expect("SUPABASE_URL must be set")
        .trim_end_matches('/')
        .trim_end_matches("/rest/v1")
        .to_string();
    let supabase_anon_key =
        std::env::var("SUPABASE_ANON_KEY").expect("SUPABASE_ANON_KEY must be set");
    let port: u16 = std::env::var("PORT")
        .unwrap_or_else(|_| "3000".to_string())
        .parse()
        .expect("PORT must be a valid number");

    let state = AppState {
        client: reqwest::Client::new(),
        supabase_url,
        supabase_anon_key,
    };

    let cors = CorsLayer::new()
        .allow_origin(Any)
        .allow_methods(Any)
        .allow_headers(Any);

    let app = Router::new()
        .route("/health", get(handlers::health))
        .route("/api/tweets", get(handlers::list_tweets))
        .route("/api/tweets/:id", get(handlers::get_tweet))
        .route("/api/issues", get(handlers::list_issues))
        .route("/api/issues/:id", get(handlers::get_issue))
        .route("/api/events", get(handlers::list_events))
        .route("/api/stats", get(handlers::get_stats))
        .layer(cors)
        .with_state(state);

    let listener = tokio::net::TcpListener::bind(("0.0.0.0", port))
        .await
        .unwrap();
    println!("listening on http://0.0.0.0:{port}");
    axum::serve(listener, app).await.unwrap();
}
