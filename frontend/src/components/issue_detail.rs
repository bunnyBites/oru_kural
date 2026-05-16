use dioxus::prelude::*;

use crate::models::format_date;
use super::status_badge::StatusBadge;
use super::category_badge::CategoryBadge;
use super::signal_card::SignalCard;

#[component]
pub fn IssueDetail(id: i64, on_close: EventHandler<()>) -> Element {
    let detail = use_resource(move || async move {
        crate::api::fetch_issue_detail(id).await
    });

    rsx! {
        div { class: "p-6",
            match &*detail.read() {
                None => rsx! {
                    div { class: "animate-pulse space-y-3",
                        div { class: "animate-shimmer h-6 w-2/3 rounded-full" }
                        div { class: "animate-shimmer h-4 w-full rounded-full" }
                        div { class: "animate-shimmer h-4 w-5/6 rounded-full" }
                    }
                },
                Some(Err(e)) => rsx! {
                    p { class: "font-body text-sm text-status-open", "Error: {e}" }
                },
                Some(Ok((issue, signals, linked_event))) => rsx! {
                    div { class: "flex items-start justify-between gap-4 mb-4",
                        h2 { class: "font-display text-2xl font-bold text-tvk-text",
                            "{issue.title}"
                        }
                        button {
                            class: "shrink-0 w-8 h-8 flex items-center justify-center \
                                    rounded-full bg-tvk-surface-2 border border-tvk-border \
                                    text-tvk-text-dim hover:text-tvk-maroon \
                                    hover:border-tvk-border-hover transition-all",
                            onclick: move |_| on_close.call(()),
                            "✕"
                        }
                    }

                    div { class: "flex flex-wrap gap-2 mt-2",
                        StatusBadge { status: issue.status.clone() }
                        CategoryBadge { category: issue.category.clone() }
                        if let Some(loc) = &issue.location {
                            span { class: "text-sm font-body text-tvk-text-dim", "📍 {loc}" }
                        }
                        if let Some(dept) = &issue.department {
                            span { class: "text-sm font-body text-tvk-text-dim", "🏛 {dept}" }
                        }
                    }

                    if let Some(summary) = &issue.summary {
                        p { class: "font-body text-tvk-text-secondary mt-4 leading-relaxed",
                            "{summary}"
                        }
                    }

                    div { class: "flex flex-wrap gap-6 mt-4 font-mono text-sm text-tvk-text-dim",
                        span { "🗣 {issue.voice_count} voices" }
                        span { "📅 First raised: {format_date(&issue.first_raised_at)}" }
                    }

                    if let Some(event) = linked_event {
                        div { class: "mt-6 p-4 bg-tvk-gold-soft border border-tvk-border rounded-xl",
                            p { class: "text-xs font-body font-medium text-tvk-gold uppercase tracking-wider mb-1",
                                "CM Response"
                            }
                            p { class: "font-body font-semibold text-tvk-text", "{event.title}" }
                            if let Some(note) = &issue.resolution_note {
                                p { class: "text-sm text-tvk-text-secondary mt-1", "{note}" }
                            }
                            a {
                                class: "text-xs font-body text-tvk-maroon hover:underline mt-2 block",
                                href: "{event.source_url}",
                                target: "_blank",
                                "View source →"
                            }
                        }
                    }

                    h3 { class: "font-display text-lg mt-6 mb-3 text-tvk-text",
                        "Citizen voices ({signals.len()})"
                    }
                    div { class: "space-y-3",
                        for signal in signals {
                            SignalCard {
                                key: "{signal.id}",
                                signal: signal.clone(),
                            }
                        }
                    }
                },
            }
        }
    }
}
