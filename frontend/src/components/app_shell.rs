use dioxus::prelude::*;
use crate::{api::fetch_tweets, components::{FilterBar, Header, StatsPanel, TweetGrid}, models::AppState};

#[component]
pub fn AppShell() -> Element {
    let mut state = use_context_provider(|| Signal::new(AppState {
        tweets: vec![],
        filtered_category: None,
        search_query: String::new(),
        loading: true,
        dark_mode: false,
    }));

    // Restore dark mode preference from localStorage on mount
    use_effect(move || {
        spawn(async move {
            let mut ev = document::eval("
                const saved = localStorage.getItem('theme');
                const isDark = saved === 'dark';
                if (isDark) document.documentElement.setAttribute('data-theme','dark');
                dioxus.send(isDark);
            ");
            if let Ok(dark) = ev.recv::<bool>().await {
                if dark {
                    state.write().dark_mode = true;
                }
            }
        });
    });

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
        div { class: "min-h-screen bg-tvk-bg transition-colors duration-300",
            Header {}
            main { class: "max-w-[1280px] mx-auto px-4 sm:px-6 py-8 space-y-6",
                FilterBar {}
                StatsPanel {}
                TweetGrid {}
            }
        }
    }
}
