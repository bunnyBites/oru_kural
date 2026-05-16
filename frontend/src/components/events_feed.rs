use dioxus::prelude::*;

use crate::models::CmEvent;
use super::event_card::EventCard;
use super::skeleton_card::SkeletonCard;

#[component]
pub fn EventsFeed() -> Element {
    let mut linked_only: Signal<bool> = use_signal(|| false);
    let mut events: Signal<Vec<CmEvent>> = use_signal(Vec::new);
    let mut next_cursor: Signal<Option<String>> = use_signal(|| None);
    let mut has_more: Signal<bool> = use_signal(|| false);
    let mut loading: Signal<bool> = use_signal(|| true);

    use_effect(move || {
        let lo = *linked_only.read();

        spawn(async move {
            loading.set(true);
            match crate::api::fetch_events(None, lo).await {
                Ok((data, cursor)) => {
                    has_more.set(cursor.is_some());
                    next_cursor.set(cursor);
                    events.set(data);
                }
                Err(e) => eprintln!("fetch_events: {e}"),
            }
            loading.set(false);
        });
    });

    let is_loading = *loading.read();
    let has_more_val = *has_more.read();
    let lo = *linked_only.read();

    let active_pill = "bg-tvk-maroon-soft text-tvk-maroon border border-tvk-maroon font-body \
                       text-sm font-medium px-4 py-1.5 rounded-full transition-all duration-150";
    let inactive_pill = "bg-transparent text-tvk-text-secondary border border-tvk-border font-body \
                         text-sm font-medium px-4 py-1.5 rounded-full hover:bg-tvk-surface-2 \
                         hover:border-tvk-border-hover hover:text-tvk-text transition-all duration-150";

    rsx! {
        div { class: "space-y-4",
            div { class: "flex gap-2 mb-4",
                button {
                    class: if !lo { active_pill } else { inactive_pill },
                    onclick: move |_| linked_only.set(false),
                    "All"
                }
                button {
                    class: if lo { active_pill } else { inactive_pill },
                    onclick: move |_| linked_only.set(true),
                    "Linked to issues"
                }
            }

            if is_loading {
                for _ in 0..4usize {
                    SkeletonCard {}
                }
            } else if events.read().is_empty() {
                div { class: "py-20 text-center",
                    p { class: "font-body text-tvk-text-dim text-sm", "No events found." }
                }
            } else {
                div { class: "space-y-4",
                    for event in events.read().iter() {
                        EventCard {
                            key: "{event.id}",
                            event: event.clone(),
                        }
                    }
                }
            }

            if has_more_val && !is_loading {
                div { class: "flex justify-center",
                    button {
                        class: "font-body text-sm text-tvk-text-secondary border border-tvk-border \
                                rounded-lg px-6 py-2 hover:border-tvk-border-hover \
                                transition-all duration-150",
                        onclick: move |_| {
                            let cursor = next_cursor.read().clone();
                            let lo_val = *linked_only.read();
                            spawn(async move {
                                match crate::api::fetch_events(cursor, lo_val).await {
                                    Ok((mut data, new_cursor)) => {
                                        has_more.set(new_cursor.is_some());
                                        next_cursor.set(new_cursor);
                                        events.write().append(&mut data);
                                    }
                                    Err(e) => eprintln!("load_more events: {e}"),
                                }
                            });
                        },
                        "Load more"
                    }
                }
            }
        }
    }
}
