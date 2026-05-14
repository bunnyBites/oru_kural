use dioxus::prelude::*;

use crate::{Route, api::fetch_tweet};

#[component]
pub fn Detail(id: String) -> Element {
    let tweet = use_resource(move || fetch_tweet(id.clone()));

    rsx! {
        div { class: "min-h-screen bg-gray-50",
            div { class: "max-w-2xl mx-auto px-6 py-8",
                Link {
                    class: "inline-flex items-center gap-1 text-sm text-indigo-600 hover:underline mb-6",
                    to: Route::Home {},
                    "← Back"
                }

                {match &*tweet.read() {
                    Some(Ok(t)) => {
                        let posted = t.posted_at.format("%B %d, %Y at %H:%M UTC").to_string();
                        let conf_label = t.confidence.map(|c| format!("{:.0}%", c * 100.0));
                        let tweet_url = format!("https://x.com/i/status/{}", t.id);
                        rsx! {
                            div { class: "bg-white rounded-xl border border-gray-200 p-6",
                                // author row
                                div { class: "flex items-start justify-between mb-4",
                                    div {
                                        p { class: "font-semibold text-gray-900",
                                            "@{t.author_handle}"
                                        }
                                        if let Some(name) = &t.author_name {
                                            p { class: "text-sm text-gray-500", "{name}" }
                                        }
                                    }
                                    a {
                                        class: "text-xs text-indigo-500 hover:underline shrink-0",
                                        href: "{tweet_url}",
                                        target: "_blank",
                                        rel: "noopener noreferrer",
                                        "View on X ↗"
                                    }
                                }

                                // content
                                p { class: "text-gray-800 leading-relaxed whitespace-pre-wrap mb-6",
                                    "{t.content}"
                                }

                                // metadata row
                                div { class: "flex flex-wrap gap-4 text-sm text-gray-500 border-t border-gray-100 pt-4",
                                    if let Some(cat) = &t.category {
                                        span {
                                            "Category: "
                                            span { class: "font-medium text-gray-800", "{cat}" }
                                        }
                                    }
                                    if let Some(pct) = conf_label {
                                        span {
                                            "Confidence: "
                                            span { class: "font-medium text-gray-800", "{pct}" }
                                        }
                                    }
                                    span {
                                        "Posted: "
                                        span { class: "font-medium text-gray-800", "{posted}" }
                                    }
                                }
                            }
                        }
                    }
                    Some(Err(e)) => rsx! {
                        p { class: "text-red-500", "Error: {e}" }
                    },
                    None => rsx! {
                        p { class: "text-gray-400", "Loading…" }
                    },
                }}
            }
        }
    }
}
