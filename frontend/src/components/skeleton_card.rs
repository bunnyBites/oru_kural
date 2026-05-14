use dioxus::prelude::*;

#[component]
pub fn SkeletonCard() -> Element {
    rsx! {
        div { class: "bg-tvk-surface border border-tvk-border rounded-[10px] p-4",
            div { class: "animate-shimmer h-3 w-32 rounded mb-4" }
            div { class: "space-y-2 mb-4",
                div { class: "animate-shimmer h-3 w-full rounded" }
                div { class: "animate-shimmer h-3 w-full rounded" }
                div { class: "animate-shimmer h-3 w-3/4 rounded" }
            }
            div { class: "flex gap-2",
                div { class: "animate-shimmer h-5 w-20 rounded-full" }
                div { class: "animate-shimmer h-[3px] w-24 rounded mt-2 self-center" }
            }
        }
    }
}
