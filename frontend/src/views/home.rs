use dioxus::prelude::*;

use crate::{
    Route,
    api::{Tweet, fetch_stats, fetch_tweets},
};

const CATEGORIES: &[&str] = &[
    "Demand",
    "Complaint",
    "Public Event",
    "Welcome",
    "Infrastructure",
    "Health",
    "Education",
    "Criticism",
    "Other",
];

#[component]
pub fn Home() -> Element {
    let mut selected = use_signal::<Option<String>>(|| None);
    let stats = use_resource(|| async { fetch_stats().await });
    let tweets = use_resource(move || {
        let cat = selected.read().clone();
        async move { fetch_tweets(cat).await }
    });

    rsx! {
        div { class: "min-h-screen bg-gray-50",
            // ── header ──────────────────────────────────────────────────
            header { class: "bg-white border-b border-gray-200 px-6 py-4 sticky top-0 z-10",
                div { class: "max-w-4xl mx-auto flex items-center justify-between",
                    h1 { class: "text-xl font-bold text-gray-900",
                        "ஒரு குரல் "
                        span { class: "text-gray-400 font-normal text-sm", "Oru Kural" }
                    }
                    {match &*stats.read() {
                        Some(Ok(s)) => {
                            let total = s.total;
                            let ts = s.last_scraped_at
                                .map(|t| t.format("%b %d, %H:%M UTC").to_string());
                            rsx! {
                                div { class: "flex gap-4 text-sm text-gray-500",
                                    span { "{total} tweets" }
                                    if let Some(t) = ts {
                                        span { "updated {t}" }
                                    }
                                }
                            }
                        }
                        _ => rsx! { span { class: "text-sm text-gray-400", "…" } },
                    }}
                }
            }

            div { class: "max-w-4xl mx-auto px-6 py-6",
                // ── category pills ───────────────────────────────────────
                div { class: "flex flex-wrap gap-2 mb-6",
                    button {
                        class: if selected.read().is_none() {
                            "px-3 py-1 rounded-full text-sm font-medium bg-indigo-600 text-white"
                        } else {
                            "px-3 py-1 rounded-full text-sm font-medium bg-white border border-gray-300 text-gray-600 hover:border-indigo-400"
                        },
                        onclick: move |_| selected.set(None),
                        "All"
                    }
                    for cat in CATEGORIES {
                        CategoryPill {
                            label: cat,
                            active: selected.read().as_deref() == Some(cat),
                            onclick: move |_| selected.set(Some(cat.to_string())),
                        }
                    }
                }

                // ── tweet grid ───────────────────────────────────────────
                {match &*tweets.read() {
                    Some(Ok(list)) if list.is_empty() => rsx! {
                        p { class: "text-gray-400 text-sm", "No tweets found." }
                    },
                    Some(Ok(list)) => rsx! {
                        div { class: "grid gap-4 sm:grid-cols-2",
                            for tweet in list.clone() {
                                TweetCard { key: "{tweet.id}", tweet }
                            }
                        }
                    },
                    Some(Err(e)) => rsx! {
                        p { class: "text-red-500 text-sm", "Error: {e}" }
                    },
                    None => rsx! {
                        p { class: "text-gray-400 text-sm", "Loading…" }
                    },
                }}
            }
        }
    }
}

#[component]
fn CategoryPill(label: &'static str, active: bool, onclick: EventHandler<MouseEvent>) -> Element {
    let class = if active {
        "px-3 py-1 rounded-full text-sm font-medium bg-indigo-600 text-white"
    } else {
        "px-3 py-1 rounded-full text-sm font-medium bg-white border border-gray-300 text-gray-600 hover:border-indigo-400"
    };
    rsx! {
        button { class, onclick, "{label}" }
    }
}

#[component]
fn TweetCard(tweet: Tweet) -> Element {
    let nav = use_navigator();
    let id = tweet.id.clone();
    let posted = tweet.posted_at.format("%b %d").to_string();
    let conf_label = tweet.confidence.map(|c| format!("{:.0}%", c * 100.0));

    let (cat_bg, cat_text) = category_colors(tweet.category.as_deref());

    rsx! {
        div {
            class: "bg-white rounded-lg border border-gray-200 p-4 cursor-pointer hover:border-indigo-300 hover:shadow-sm transition-all",
            onclick: move |_| { nav.push(Route::Detail { id: id.clone() }); },

            div { class: "flex items-start justify-between gap-2 mb-2",
                span { class: "text-sm font-medium text-gray-900 truncate",
                    "@{tweet.author_handle}"
                }
                span { class: "text-xs text-gray-400 shrink-0", "{posted}" }
            }

            p { class: "text-sm text-gray-700 line-clamp-3 mb-3", "{tweet.content}" }

            div { class: "flex items-center gap-2",
                if let Some(cat) = &tweet.category {
                    span {
                        class: "px-2 py-0.5 rounded text-xs font-medium {cat_bg} {cat_text}",
                        "{cat}"
                    }
                }
                if let Some(pct) = conf_label {
                    span { class: "text-xs text-gray-400", "{pct}" }
                }
            }
        }
    }
}

fn category_colors(category: Option<&str>) -> (&'static str, &'static str) {
    match category {
        Some("Complaint") => ("bg-red-100", "text-red-700"),
        Some("Demand") => ("bg-orange-100", "text-orange-700"),
        Some("Infrastructure") => ("bg-blue-100", "text-blue-700"),
        Some("Health") => ("bg-green-100", "text-green-700"),
        Some("Education") => ("bg-purple-100", "text-purple-700"),
        Some("Welcome") => ("bg-yellow-100", "text-yellow-700"),
        Some("Public Event") => ("bg-pink-100", "text-pink-700"),
        Some("Criticism") => ("bg-gray-200", "text-gray-700"),
        _ => ("bg-gray-100", "text-gray-500"),
    }
}
