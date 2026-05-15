use dioxus::prelude::*;

use crate::models::Signal;
use super::source_badge::SourceBadge;

#[component]
pub fn SignalCard(signal: Signal) -> Element {
    let content = signal
        .translated_content
        .as_deref()
        .unwrap_or(&signal.content)
        .to_string();
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
            p { class: "font-body text-sm text-tvk-text leading-relaxed", "{content}" }
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
