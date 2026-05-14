use dioxus::prelude::*;

use crate::{Route, api::fetch_tweet, models::format_ts};

#[component]
pub fn Detail(id: String) -> Element {
    let tweet = use_resource(move || fetch_tweet(id.clone()));

    rsx! {
        div { class: "min-h-screen bg-tvk-bg",
            div { class: "max-w-2xl mx-auto px-6 py-8",
                Link {
                    class: "inline-flex items-center gap-1 text-sm text-tvk-muted \
                            hover:text-tvk-text transition-colors mb-6",
                    to: Route::Home {},
                    "← Back"
                }

                {match &*tweet.read() {
                    Some(Ok(t)) => {
                        let posted = format_ts(&t.posted_at);
                        let conf_label = t.confidence.map(|c| format!("{:.0}%", c * 100.0));
                        let tweet_url = format!("https://x.com/i/status/{}", t.id);
                        rsx! {
                            div {
                                class: "bg-tvk-surface border border-tvk-border rounded-[10px] p-6",
                                div { class: "flex items-start justify-between mb-4",
                                    div {
                                        p { class: "font-semibold text-tvk-text",
                                            "@{t.author_handle}"
                                        }
                                        if let Some(name) = &t.author_name {
                                            p { class: "text-sm text-tvk-muted", "{name}" }
                                        }
                                    }
                                    a {
                                        class: "text-xs text-tvk-gold hover:underline shrink-0",
                                        href: "{tweet_url}",
                                        target: "_blank",
                                        rel: "noopener noreferrer",
                                        "View on X ↗"
                                    }
                                }

                                p { class: "text-tvk-text leading-relaxed whitespace-pre-wrap mb-6",
                                    "{t.content}"
                                }

                                if let Some(translated) = &t.translated_content {
                                    div { class: "border-t border-tvk-border pt-4 mb-4",
                                        p { class: "text-xs text-tvk-muted uppercase tracking-wider mb-2",
                                            "English translation"
                                        }
                                        p { class: "text-tvk-text leading-relaxed", "{translated}" }
                                    }
                                }

                                div {
                                    class: "flex flex-wrap gap-4 text-sm text-tvk-muted \
                                            border-t border-tvk-border pt-4",
                                    if let Some(cat) = &t.category {
                                        span {
                                            "Category: "
                                            span { class: "font-medium text-tvk-text", "{cat}" }
                                        }
                                    }
                                    if let Some(pct) = conf_label {
                                        span {
                                            "Confidence: "
                                            span { class: "font-medium text-tvk-text", "{pct}" }
                                        }
                                    }
                                    span {
                                        "Posted: "
                                        span { class: "font-medium text-tvk-text", "{posted}" }
                                    }
                                }
                            }
                        }
                    }
                    Some(Err(e)) => rsx! {
                        p { class: "text-red-400", "Error: {e}" }
                    },
                    None => rsx! {
                        p { class: "text-tvk-muted", "Loading…" }
                    },
                }}
            }
        }
    }
}
