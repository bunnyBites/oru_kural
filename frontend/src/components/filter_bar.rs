use dioxus::prelude::*;
use crate::models::AppState;

const CATEGORIES: &[&str] = &[
    "Demand", "Complaint", "Public Event", "Welcome",
    "Infrastructure", "Health", "Education", "Criticism", "Other",
];

#[component]
pub fn FilterBar() -> Element {
    let mut ctx = use_context::<Signal<AppState>>();

    let all_active = ctx.read().filtered_category.is_none();
    let all_class = pill_class(all_active);
    let search_val = ctx.read().search_query.clone();

    rsx! {
        div { class: "py-4 space-y-3",
            div { class: "flex gap-2 overflow-x-auto pb-1",
                button {
                    class: "px-3 py-1 rounded-full border text-sm transition-all duration-150 whitespace-nowrap {all_class}",
                    onclick: move |_| ctx.write().filtered_category = None,
                    "All"
                }
                for &cat in CATEGORIES {
                    CategoryPill {
                        label: cat,
                        active: ctx.read().filtered_category.as_deref() == Some(cat),
                    }
                }
            }
            input {
                class: "w-full max-w-xs bg-tvk-surface border border-tvk-border rounded-lg \
                        px-3 py-2 text-sm text-tvk-text placeholder:text-tvk-dim \
                        focus:outline-none focus:border-tvk-maroon transition-colors duration-150",
                value: "{search_val}",
                placeholder: "Search tweets...",
                oninput: move |evt| ctx.write().search_query = evt.value(),
            }
        }
    }
}

fn pill_class(active: bool) -> &'static str {
    if active {
        "bg-tvk-maroon text-tvk-text border-transparent"
    } else {
        "bg-transparent text-tvk-muted border-tvk-border hover:bg-tvk-surface-2 hover:border-tvk-border-hover"
    }
}

#[component]
fn CategoryPill(label: &'static str, active: bool) -> Element {
    let mut ctx = use_context::<Signal<AppState>>();
    rsx! {
        button {
            class: "px-3 py-1 rounded-full border text-sm transition-all duration-150 whitespace-nowrap {pill_class(active)}",
            onclick: move |_| ctx.write().filtered_category = Some(label.to_string()),
            "{label}"
        }
    }
}
