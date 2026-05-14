use dioxus::prelude::*;
use crate::{api::fetch_tweets, components::{FilterBar, Header, StatsPanel, TweetGrid}, models::AppState};

#[component]
pub fn AppShell() -> Element {
    let mut state = use_context_provider(|| Signal::new(AppState {
        tweets: vec![],
        filtered_category: None,
        search_query: String::new(),
        loading: true,
    }));

    use_effect(move || {
        spawn(async move {
            match fetch_tweets(None).await {
                Ok(tweets) => state.write().tweets = tweets,
                Err(e) => eprintln!("fetch error: {e}"),
            }
            state.write().loading = false;
        });
    });

    rsx! {
        div { class: "min-h-screen bg-tvk-bg",
            Header {}
            main { class: "max-w-[1280px] mx-auto px-4 py-6",
                FilterBar {}
                StatsPanel {}
                TweetGrid {}
            }
        }
    }
}
