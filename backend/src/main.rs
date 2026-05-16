mod handlers;
mod models;

use axum::{Router, routing::get};
use tower_http::cors::{Any, CorsLayer};

#[derive(Clone)]
pub struct AppState {
    pub client: reqwest::Client,
    pub supabase_url: String,
    pub supabase_key: String,
}

#[tokio::main]
async fn main() {
    dotenvy::dotenv().ok();

    let supabase_url = std::env::var("SUPABASE_URL")
        .expect("SUPABASE_URL must be set")
        .trim_end_matches('/')
        .trim_end_matches("/rest/v1")
        .to_string();
    let supabase_key =
        std::env::var("SUPABASE_ANON_KEY").expect("SUPABASE_ANON_KEY must be set");
    let port: u16 = std::env::var("PORT")
        .unwrap_or_else(|_| "8080".to_string())
        .parse()
        .expect("PORT must be a valid number");

    let state = AppState {
        client: reqwest::Client::new(),
        supabase_url,
        supabase_key,
    };

    let cors = match std::env::var("FRONTEND_ORIGIN") {
        Ok(origin) => CorsLayer::new()
            .allow_origin(
                origin
                    .parse::<axum::http::HeaderValue>()
                    .expect("invalid FRONTEND_ORIGIN"),
            )
            .allow_methods([axum::http::Method::GET])
            .allow_headers(Any),
        Err(_) => CorsLayer::permissive(),
    };

    let app = Router::new()
        .route("/health", get(handlers::health))
        .route("/issues", get(handlers::list_issues))
        .route("/issues/:id", get(handlers::get_issue))
        .route("/signals", get(handlers::list_signals))
        .route("/events", get(handlers::list_events))
        .route("/stats", get(handlers::get_stats))
        .layer(cors)
        .with_state(state);

    let listener = tokio::net::TcpListener::bind(("0.0.0.0", port))
        .await
        .unwrap();
    println!("Oru Kural backend listening on :{port}");
    axum::serve(listener, app).await.unwrap();
}
