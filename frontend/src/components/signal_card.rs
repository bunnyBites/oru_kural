use dioxus::prelude::*;

use crate::models::Signal;
use super::app_shell::AppCtx;
use super::source_badge::SourceBadge;

#[component]
pub fn SignalCard(signal: Signal) -> Element {
    let ctx = use_context::<AppCtx>();
    let is_tamil = *ctx.tamil_mode.read();

    let content = if is_tamil {
        signal.content.clone()
    } else {
        signal.translated_content.as_deref().unwrap_or(&signal.content).to_string()
    };
    let use_tamil_font = is_tamil;
    let handle = signal
        .author_handle
        .as_deref()
        .unwrap_or("unknown")
        .to_string();
    let score = signal.score.unwrap_or(0);

    rsx! {
        div { class: "bg-tvk-surface border border-tvk-border rounded-lg p-4",
            div { class: "flex items-center gap-2 mb-2",
                SourceBadge { source: signal.source.clone() }
                span { class: "font-body text-sm font-medium text-tvk-text", "@{handle}" }
                span { class: "font-mono text-xs text-tvk-text-dim ml-auto", "{score} 👍" }
            }
            p {
                class: "text-sm text-tvk-text leading-relaxed",
                class: if use_tamil_font { "font-tamil" } else { "font-body" },
                "{content}"
            }
            if let Some(url) = &signal.url {
                a {
                    class: "text-xs font-body text-tvk-maroon hover:underline mt-2 block",
                    href: "{url}",
                    target: "_blank",
                    "View original →"
                }
            }
        }
    }
}
