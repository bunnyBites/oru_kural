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
            "px-2 py-0.5 rounded-full border text-xs transition-all duration-150 \
             border-tvk-maroon text-tvk-maroon hover:bg-tvk-maroon hover:text-tvk-text",
        )
    } else {
        (
            "EN ↗",
            "px-2 py-0.5 rounded-full border text-xs transition-all duration-150 \
             border-tvk-border text-tvk-dim hover:border-tvk-border-hover hover:text-tvk-muted",
        )
    };

    rsx! {
        div {
            class: "animate-card-enter bg-tvk-surface border border-tvk-border \
                    rounded-[10px] p-4 \
                    hover:border-tvk-border-hover hover:-translate-y-0.5 \
                    hover:shadow-[0_4px_20px_rgba(139,26,43,0.15)] \
                    transition-all duration-200 cursor-pointer",
            style: "animation-delay: {delay_ms}ms",
            onclick: move |evt| {
                // Don't navigate if the EN toggle button was clicked
                evt.stop_propagation();
                nav.push(Route::Detail { id: id.clone() });
            },

            div { class: "flex justify-between items-start mb-3",
                div {
                    span { class: "font-semibold text-tvk-text text-sm",
                        "@{tweet.author_handle}"
                    }
                    if let Some(name) = &tweet.author_name {
                        span { class: "text-tvk-muted text-sm ml-2", "{name}" }
                    }
                }
                span { class: "font-mono text-xs text-tvk-dim shrink-0", "{posted}" }
            }

            p { class: "text-sm text-tvk-text leading-relaxed mb-4", "{content}" }

            div { class: "flex justify-between items-center",
                div { class: "flex items-center gap-2",
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
                            let v = *show_translation.read();
                            show_translation.set(!v);
                        },
                        "{toggle_label}"
                    }
                }
            }
        }
    }
}
