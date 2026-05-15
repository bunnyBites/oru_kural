use dioxus::prelude::*;

fn source_display(source: &str) -> (&'static str, &'static str, &'static str) {
    match source {
        "x" => ("𝕏", "#000000", "#FFFFFF"),
        "reddit" => ("Reddit", "#FF4500", "#FFFFFF"),
        _ => ("?", "#6B7280", "#FFFFFF"),
    }
}

#[component]
pub fn SourceBadge(source: String) -> Element {
    let (label, bg, text) = source_display(&source);
    rsx! {
        span {
            class: "inline-flex items-center px-2 py-0.5 rounded-full text-xs font-body font-medium whitespace-nowrap shrink-0",
            style: "background: {bg}; color: {text};",
            "{label}"
        }
    }
}
