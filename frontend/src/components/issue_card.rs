use dioxus::prelude::*;

use crate::models::Issue;
use super::status_badge::StatusBadge;
use super::category_badge::CategoryBadge;

#[component]
pub fn IssueCard(issue: Issue, index: usize, on_click: EventHandler<i64>) -> Element {
    let delay = (index * 60).min(600);
    let voice_count = issue.voice_count;
    let issue_id = issue.id;
    let has_linked_event = issue.linked_event_id.is_some();

    rsx! {
        div {
            class: "animate-card-enter flex flex-col bg-tvk-surface border border-tvk-border \
                    rounded-xl p-5 h-full hover:border-tvk-border-hover hover:-translate-y-0.5 \
                    hover:shadow-md transition-all duration-200 cursor-pointer",
            style: "animation-delay: {delay}ms",
            onclick: move |_| on_click.call(issue_id),

            div { class: "flex items-start justify-between gap-2 mb-3",
                div { class: "min-w-0",
                    p { class: "font-body font-semibold text-sm text-tvk-text leading-snug line-clamp-2",
                        "{issue.title}"
                    }
                    if let Some(loc) = &issue.location {
                        p { class: "text-xs font-body text-tvk-text-dim mt-0.5", "📍 {loc}" }
                    }
                }
                StatusBadge { status: issue.status.clone() }
            }

            div { class: "flex-1 mb-4",
                if let Some(summary) = &issue.summary {
                    p { class: "font-body text-sm text-tvk-text-secondary leading-relaxed line-clamp-3",
                        "{summary}"
                    }
                }
            }

            div { class: "flex items-center justify-between gap-2 pt-3 border-t border-tvk-border mt-auto",
                div { class: "flex items-center gap-2",
                    CategoryBadge { category: issue.category.clone() }
                }
                div { class: "flex items-center gap-3",
                    span { class: "font-mono text-xs text-tvk-gold", "🗣 {voice_count}" }
                    if has_linked_event {
                        span { class: "text-xs font-body text-status-progress", "↔ CM action" }
                    }
                }
            }
        }
    }
}
