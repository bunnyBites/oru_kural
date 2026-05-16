mod handlers;
mod models;

use std::net::SocketAddr;
use std::sync::Arc;

use axum::{Router, http::Request, routing::get};
use tower_governor::{governor::GovernorConfigBuilder, GovernorLayer};
use tower_http::compression::CompressionLayer;
use tower_http::cors::{Any, CorsLayer};
use tower_http::request_id::{MakeRequestId, PropagateRequestIdLayer, RequestId, SetRequestIdLayer};
use axum::http::header::HeaderName;
use tower_http::trace::TraceLayer;
use tracing_subscriber::EnvFilter;

#[derive(Clone)]
pub struct AppState {
    pub client: reqwest::Client,
    pub supabase_url: String,
    pub supabase_key: String,
}

#[derive(Clone, Default)]
struct UuidRequestId;

impl MakeRequestId for UuidRequestId {
    fn make_request_id<B>(&mut self, _: &Request<B>) -> Option<RequestId> {
        let id = uuid::Uuid::new_v4().to_string();
        axum::http::HeaderValue::from_str(&id).ok().map(RequestId::new)
    }
}

#[tokio::main]
async fn main() {
    dotenvy::dotenv().ok();

    let filter = EnvFilter::try_from_default_env()
        .unwrap_or_else(|_| EnvFilter::new("info"));
    tracing_subscriber::fmt()
        .json()
        .with_env_filter(filter)
        .init();

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

    // 1 req/sec sustained, burst of 20 per IP
    let governor_conf = Arc::new(
        GovernorConfigBuilder::default()
            .per_second(1)
            .burst_size(20)
            .finish()
            .unwrap(),
    );

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
        // Layers applied inside-out; last .layer() = outermost (runs first on request).
        .layer(GovernorLayer { config: governor_conf })
        .layer(cors)
        .layer(CompressionLayer::new())
        .layer(PropagateRequestIdLayer::new(HeaderName::from_static("x-request-id")))
        .layer(
            TraceLayer::new_for_http().make_span_with(|req: &Request<_>| {
                let request_id = req
                    .headers()
                    .get("x-request-id")
                    .and_then(|v| v.to_str().ok())
                    .unwrap_or("-");
                tracing::info_span!(
                    "http",
                    method = %req.method(),
                    uri = %req.uri(),
                    request_id = request_id,
                )
            }),
        )
        .layer(SetRequestIdLayer::new(
            HeaderName::from_static("x-request-id"),
            UuidRequestId,
        ))
        .with_state(state);

    let listener = tokio::net::TcpListener::bind(("0.0.0.0", port))
        .await
        .unwrap();
    tracing::info!("Oru Kural backend listening on :{port}");
    axum::serve(listener, app.into_make_service_with_connect_info::<SocketAddr>())
        .await
        .unwrap();
}
