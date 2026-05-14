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
    let search_val = ctx.read().search_query.clone();

    rsx! {
        div { class: "space-y-3 pb-2",
            div { class: "flex gap-2 overflow-x-auto scrollbar-hide pb-1",
                button {
                    class: pill_class(all_active),
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
            div { class: "relative max-w-sm",
                span {
                    class: "absolute left-3 top-1/2 -translate-y-1/2 \
                            text-tvk-text-dim pointer-events-none",
                    "⌕"
                }
                input {
                    class: "w-full bg-tvk-surface border border-tvk-border rounded-lg \
                            pl-9 pr-4 py-2 text-sm font-body text-tvk-text \
                            placeholder:text-tvk-text-dim \
                            focus:outline-none focus:border-tvk-maroon \
                            transition-all duration-150",
                    value: "{search_val}",
                    placeholder: "Search tweets…",
                    oninput: move |evt| ctx.write().search_query = evt.value(),
                }
            }
        }
    }
}

fn pill_class(active: bool) -> &'static str {
    if active {
        "bg-tvk-maroon-soft text-tvk-maroon border border-tvk-maroon \
         font-body text-sm font-medium px-4 py-1.5 rounded-full \
         whitespace-nowrap transition-all duration-150"
    } else {
        "bg-transparent text-tvk-text-secondary border border-tvk-border \
         font-body text-sm font-medium px-4 py-1.5 rounded-full \
         whitespace-nowrap hover:bg-tvk-surface-2 \
         hover:border-tvk-border-hover hover:text-tvk-text \
         transition-all duration-150"
    }
}

#[component]
fn CategoryPill(label: &'static str, active: bool) -> Element {
    let mut ctx = use_context::<Signal<AppState>>();
    rsx! {
        button {
            class: pill_class(active),
            onclick: move |_| ctx.write().filtered_category = Some(label.to_string()),
            "{label}"
        }
    }
}
