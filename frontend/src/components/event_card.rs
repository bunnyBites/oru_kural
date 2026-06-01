use dioxus::prelude::*;

use crate::i18n;
use crate::models::{CmEvent, format_date};
use super::app_shell::AppCtx;

#[component]
pub fn EventCard(event: CmEvent) -> Element {
    let ctx = use_context::<AppCtx>();
    let is_tamil = *ctx.tamil_mode.read();
    let t = i18n::get(is_tamil);

    rsx! {
        div {
            class: "bg-tvk-surface border border-tvk-border rounded-xl p-5 \
                    hover:border-tvk-border-hover hover:shadow-sm transition-all duration-150",

            div { class: "flex items-start justify-between gap-2 mb-3",
                p { class: "font-body font-semibold text-sm text-tvk-text leading-snug",
                    "{event.title}"
                }
                if event.linked_issue_id.is_some() {
                    span {
                        class: "badge-linked text-xs font-body shrink-0 px-2 py-0.5 rounded-full",
                        "{t.linked_badge}"
                    }
                }
            }

            div { class: "flex flex-wrap gap-3 text-xs font-body text-tvk-text-dim mb-3",
                if let Some(loc) = &event.location {
                    span { "📍 {loc}" }
                }
                if let Some(dept) = &event.department {
                    span { "🏛 {dept}" }
                }
                if let Some(date) = &event.event_date {
                    span { class: "font-mono", "{format_date(date)}" }
                }
            }

            if let Some(desc) = &event.description {
                p { class: "text-sm font-body text-tvk-text-secondary leading-relaxed line-clamp-3",
                    "{desc}"
                }
            }

            div { class: "flex items-center justify-between mt-3 pt-3 border-t border-tvk-border",
                span { class: "text-xs font-body text-tvk-text-dim",
                    "{event.source_name.as_deref().unwrap_or(\"\")}"
                }
                a {
                    class: "text-xs font-body text-tvk-maroon hover:underline",
                    href: "{event.source_url}",
                    target: "_blank",
                    "{t.read_more}"
                }
            }
        }
    }
}
