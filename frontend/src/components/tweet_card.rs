use dioxus::prelude::*;
use crate::{
    Route,
    components::{CategoryBadge, ConfidenceBar},
    models::{Tweet, format_ts},
};

#[component]
pub fn TweetCard(tweet: Tweet, index: usize) -> Element {
    let nav = use_navigator();
    let id = tweet.id.clone();
    let mut show_translation = use_signal(|| false);
    let delay_ms = (index * 60).min(600);

    let content = if *show_translation.read() {
        tweet.translated_content.as_deref().unwrap_or(&tweet.content)
    } else {
        &tweet.content
    };
    let posted = format_ts(&tweet.posted_at);
    let has_translation = tweet.translated_content.is_some();

    let (toggle_label, toggle_class) = if *show_translation.read() {
        (
            "தமிழ் ↗",
            "shrink-0 px-2.5 py-1 rounded-full border text-xs font-body font-medium \
             transition-all duration-150 \
             border-tvk-maroon text-tvk-maroon bg-tvk-maroon-soft \
             hover:bg-tvk-maroon hover:text-white",
        )
    } else {
        (
            "EN ↗",
            "shrink-0 px-2.5 py-1 rounded-full border text-xs font-body font-medium \
             transition-all duration-150 \
             border-tvk-border text-tvk-text-dim bg-transparent \
             hover:border-tvk-border-hover hover:text-tvk-text-secondary",
        )
    };

    rsx! {
        div {
            class: "animate-card-enter flex flex-col \
                    bg-tvk-surface border border-tvk-border rounded-xl \
                    p-5 h-full \
                    hover:border-tvk-border-hover hover:-translate-y-0.5 \
                    hover:shadow-md \
                    transition-all duration-200 cursor-pointer",
            style: "animation-delay: {delay_ms}ms",
            onclick: move |evt| {
                evt.stop_propagation();
                nav.push(Route::Detail { id: id.clone() });
            },

            div { class: "flex items-start justify-between gap-2 mb-3",
                div { class: "min-w-0",
                    span { class: "font-body font-semibold text-sm text-tvk-text truncate block",
                        "@{tweet.author_handle}"
                    }
                    if let Some(name) = &tweet.author_name {
                        span { class: "font-body text-xs text-tvk-text-secondary ml-1", "{name}" }
                    }
                }
                span { class: "font-mono text-xs text-tvk-text-dim shrink-0 mt-0.5",
                    "{posted}"
                }
            }

            div { class: "flex-1 mb-4",
                p { class: "font-body text-sm text-tvk-text leading-relaxed", "{content}" }
            }

            div {
                class: "flex items-center justify-between gap-2 pt-3 \
                        border-t border-tvk-border mt-auto",
                div { class: "flex items-center gap-2 min-w-0",
                    if let Some(cat) = &tweet.category {
                        CategoryBadge { category: cat.clone() }
                    }
                    if let Some(conf) = tweet.confidence {
                        ConfidenceBar { confidence: conf }
                    }
                }
                if has_translation {
                    button {
                        class: "{toggle_class}",
                        onclick: move |evt| {
                            evt.stop_propagation();
                            show_translation.toggle();
                        },
                        "{toggle_label}"
                    }
                }
            }
        }
    }
}
