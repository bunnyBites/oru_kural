use dioxus::prelude::*;

#[component]
pub fn StatsPanel() -> Element {
    let stats = use_resource(|| async move { crate::api::fetch_stats().await });

    match &*stats.read() {
        None => rsx! {
            div { class: "grid grid-cols-2 sm:grid-cols-4 gap-3",
                for _ in 0..8usize {
                    div { class: "bg-tvk-surface border border-tvk-border rounded-xl p-4",
                        div { class: "animate-shimmer h-3 w-20 rounded-full mb-3" }
                        div { class: "animate-shimmer h-7 w-12 rounded-full mb-3" }
                        div { class: "animate-shimmer h-[3px] w-full rounded-full" }
                    }
                }
            }
        },
        Some(Err(e)) => rsx! {
            p { class: "font-body text-sm text-status-open py-8", "Error loading stats: {e}" }
        },
        Some(Ok(rows)) => {
            let total: i32 = rows.iter().map(|r| r.tweet_count).sum();
            rsx! {
                div { class: "space-y-6",
                    h2 { class: "font-display text-xl font-bold text-tvk-text mb-4",
                        "Signal breakdown"
                    }
                    div { class: "grid grid-cols-2 sm:grid-cols-4 gap-3",
                        for stat in rows {
                            {
                                let pct = if total > 0 {
                                    (stat.tweet_count * 100 / total).min(100)
                                } else {
                                    0
                                };
                                rsx! {
                                    div {
                                        key: "{stat.category}",
                                        class: "bg-tvk-surface border border-tvk-border rounded-xl p-4",
                                        p { class: "text-xs font-body font-medium text-tvk-text-dim uppercase tracking-wider mb-2",
                                            "{stat.category}"
                                        }
                                        p { class: "font-mono text-2xl text-tvk-gold leading-none mb-3",
                                            "{stat.tweet_count}"
                                        }
                                        div { class: "w-full h-[3px] bg-tvk-border rounded-full overflow-hidden",
                                            div {
                                                class: "h-full bg-tvk-gold rounded-full animate-bar-fill",
                                                style: "width: {pct}%;",
                                            }
                                        }
                                        p { class: "text-xs font-body text-tvk-text-dim mt-2",
                                            "{pct}% of signals"
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
