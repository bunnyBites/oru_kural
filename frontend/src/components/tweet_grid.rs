use dioxus::prelude::*;
use crate::{components::{SkeletonCard, TweetCard}, models::AppState};

#[component]
pub fn TweetGrid() -> Element {
    let state = use_context::<Signal<AppState>>();
    let s = state.read();

    let loading = s.loading;
    let search = s.search_query.to_lowercase();

    let filtered: Vec<_> = s.tweets.iter()
        .filter(|t| match &s.filtered_category {
            None => true,
            Some(cat) => t.category.as_deref() == Some(cat.as_str()),
        })
        .filter(|t| {
            if search.is_empty() { return true; }
            t.content.to_lowercase().contains(&search) ||
            t.author_handle.to_lowercase().contains(&search)
        })
        .cloned()
        .collect();

    rsx! {
        div {
            if loading {
                div { class: "grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4",
                    for _ in 0..6 {
                        SkeletonCard {}
                    }
                }
            } else if filtered.is_empty() {
                div { class: "flex items-center justify-center py-24",
                    p { class: "font-display italic text-tvk-dim text-xl",
                        "No voices found"
                    }
                }
            } else {
                div { class: "grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4",
                    for (index, tweet) in filtered.into_iter().enumerate() {
                        TweetCard { key: "{tweet.id}", tweet, index }
                    }
                }
            }
        }
    }
}
