use dioxus::prelude::*;

use crate::models::Tab;
use super::app_shell::AppCtx;

#[component]
pub fn StatsPanel() -> Element {
    let mut ctx = use_context::<AppCtx>();
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
                    div {
                        h2 { class: "font-display text-xl font-bold text-tvk-text mb-1",
                            "Signal breakdown"
                        }
                        p { class: "text-xs font-body text-tvk-text-dim",
                            "Cards with issues are clickable — opens the Issues Board filtered by category."
                        }
                    }
                    div { class: "grid grid-cols-2 sm:grid-cols-4 gap-3",
                        for stat in rows {
                            {
                                let category = stat.category.clone();
                                let has_issues = stat.issue_count > 0;
                                let pct = if total > 0 {
                                    (stat.tweet_count * 100 / total).min(100)
                                } else {
                                    0
                                };

                                let card_cls = if has_issues {
                                    "bg-tvk-surface border border-tvk-border rounded-xl p-4 \
                                     cursor-pointer hover:border-tvk-maroon hover:-translate-y-0.5 \
                                     hover:shadow-md transition-all duration-200 group"
                                } else {
                                    "bg-tvk-surface border border-tvk-border rounded-xl p-4 \
                                     opacity-70 cursor-default transition-all duration-200 group"
                                };

                                rsx! {
                                    div {
                                        key: "{stat.category}",
                                        class: "{card_cls}",
                                        onclick: move |_| {
                                            if has_issues {
                                                ctx.category_filter.set(Some(category.clone()));
                                                ctx.active_tab.set(Tab::Issues);
                                            }
                                        },

                                        // Category label + clickable hint
                                        div { class: "flex items-start justify-between mb-2",
                                            p { class: "text-xs font-body font-medium text-tvk-text-dim \
                                                        uppercase tracking-wider group-hover:text-tvk-maroon \
                                                        transition-colors duration-200",
                                                "{stat.category}"
                                            }
                                            if has_issues {
                                                span { class: "text-xs text-tvk-maroon opacity-0 \
                                                               group-hover:opacity-100 transition-opacity duration-200",
                                                    "→"
                                                }
                                            }
                                        }

                                        // Signal count
                                        p { class: "font-mono text-2xl text-tvk-gold leading-none mb-1",
                                            "{stat.tweet_count}"
                                        }
                                        p { class: "text-xs font-body text-tvk-text-dim mb-3",
                                            "signals"
                                        }

                                        // Progress bar
                                        div { class: "w-full h-[3px] bg-tvk-border rounded-full overflow-hidden mb-2",
                                            div {
                                                class: "h-full bg-tvk-gold rounded-full animate-bar-fill",
                                                style: "width: {pct}%;",
                                            }
                                        }

                                        // Issue count or signal-only note
                                        if has_issues {
                                            p { class: "text-xs font-body text-tvk-text-dim",
                                                span { class: "text-status-progress font-medium",
                                                    "{stat.issue_count}"
                                                }
                                                " issues · {stat.open_count} open"
                                            }
                                        } else {
                                            p { class: "text-xs font-body text-tvk-text-dim italic",
                                                "signals only — no issues clustered"
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
}
