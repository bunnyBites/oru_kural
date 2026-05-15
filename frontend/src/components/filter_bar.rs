use dioxus::prelude::*;

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
    let cur_status = status_filter.read().clone();
    let cur_category = category_filter.read().clone();
    let search_val = search_query.read().clone();

    rsx! {
        div { class: "space-y-3 pb-2",

            div { class: "flex gap-2 overflow-x-auto scrollbar-hide pb-1",
                button {
                    class: pill_cls(cur_status.is_none()),
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
                    value: "{search_val}",
                    placeholder: "Search issues…",
                    oninput: move |evt| { search_query.set(evt.value()); },
                }
            }
        }
    }
}
