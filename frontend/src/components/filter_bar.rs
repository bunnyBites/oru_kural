use std::time::Duration;

use dioxus::prelude::*;
use gloo_timers::future::sleep;

const STATUSES: &[(&str, &str)] = &[
    ("open", "Open"),
    ("acknowledged", "Acknowledged"),
    ("in_progress", "In Progress"),
    ("resolved", "Resolved"),
];

const CATEGORIES: &[&str] = &[
    "Infrastructure",
    "Health",
    "Education",
    "Demand",
    "Complaint",
    "Public Event",
    "Welcome",
    "Criticism",
    "Other",
];

fn pill_cls(active: bool) -> &'static str {
    if active {
        "bg-tvk-maroon-soft text-tvk-maroon border border-tvk-maroon font-body text-sm \
         font-medium px-4 py-1.5 rounded-full whitespace-nowrap transition-all duration-150"
    } else {
        "bg-transparent text-tvk-text-secondary border border-tvk-border font-body text-sm \
         font-medium px-4 py-1.5 rounded-full whitespace-nowrap hover:bg-tvk-surface-2 \
         hover:border-tvk-border-hover hover:text-tvk-text transition-all duration-150"
    }
}

#[component]
pub fn FilterBar(
    status_filter: Signal<Option<String>>,
    category_filter: Signal<Option<String>>,
    search_query: Signal<String>,
) -> Element {
    // raw_input drives the text box immediately; search_query (parent signal) is
    // updated only after 300 ms of silence so the API isn't called on every keystroke.
    let mut raw_input: Signal<String> = use_signal(|| search_query.peek().clone());
    let mut debounce_ver: Signal<u32> = use_signal(|| 0u32);

    let cur_status = status_filter.read().clone();
    let cur_category = category_filter.read().clone();

    rsx! {
        div { class: "space-y-3 pb-2",

            div { class: "flex gap-2 overflow-x-auto scrollbar-hide pb-1",
                button {
                    class: pill_cls(cur_status.is_none()),
                    "aria-label": "Show all statuses",
                    onclick: move |_| { status_filter.set(None); },
                    "All"
                }
                for (val, label) in STATUSES {
                    {
                        let v = val.to_string();
                        let is_active = cur_status.as_deref() == Some(val);
                        rsx! {
                            button {
                                key: "{val}",
                                class: pill_cls(is_active),
                                "aria-label": "Filter by status: {label}",
                                onclick: move |_| { status_filter.set(Some(v.clone())); },
                                "{label}"
                            }
                        }
                    }
                }
            }

            div { class: "flex gap-2 overflow-x-auto scrollbar-hide pb-1",
                button {
                    class: pill_cls(cur_category.is_none()),
                    "aria-label": "Show all categories",
                    onclick: move |_| { category_filter.set(None); },
                    "All"
                }
                for cat in CATEGORIES {
                    {
                        let c = cat.to_string();
                        let is_active = cur_category.as_deref() == Some(cat);
                        rsx! {
                            button {
                                key: "{cat}",
                                class: pill_cls(is_active),
                                "aria-label": "Filter by category: {cat}",
                                onclick: move |_| { category_filter.set(Some(c.clone())); },
                                "{cat}"
                            }
                        }
                    }
                }
            }

            div { class: "relative max-w-sm",
                span {
                    class: "absolute left-3 top-1/2 -translate-y-1/2 text-tvk-text-dim pointer-events-none",
                    "⌕"
                }
                input {
                    class: "w-full bg-tvk-surface border border-tvk-border rounded-lg \
                            pl-9 pr-4 py-2 text-sm font-body text-tvk-text \
                            placeholder:text-tvk-text-dim focus:outline-none \
                            focus:border-tvk-maroon transition-all duration-150",
                    value: "{raw_input}",
                    placeholder: "Search issues…",
                    oninput: move |evt| {
                        let value = evt.value();
                        raw_input.set(value.clone());
                        let ver = *debounce_ver.peek() + 1;
                        debounce_ver.set(ver);
                        spawn(async move {
                            sleep(Duration::from_millis(300)).await;
                            if *debounce_ver.peek() == ver {
                                search_query.set(value);
                            }
                        });
                    },
                }
            }
        }
    }
}
