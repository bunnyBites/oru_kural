use dioxus::prelude::*;

#[component]
pub fn SkeletonCard() -> Element {
    rsx! {
        div {
            class: "flex flex-col bg-tvk-surface border border-tvk-border rounded-xl p-5 h-full",

            div { class: "flex justify-between mb-3",
                div { class: "animate-shimmer h-3 w-28 rounded-full" }
                div { class: "animate-shimmer h-3 w-12 rounded-full" }
            }

            div { class: "flex-1 space-y-2 mb-4",
                div { class: "animate-shimmer h-3 w-full rounded-full" }
                div { class: "animate-shimmer h-3 w-full rounded-full" }
                div { class: "animate-shimmer h-3 w-4/5 rounded-full" }
                div { class: "animate-shimmer h-3 w-3/5 rounded-full" }
            }

            div { class: "flex items-center gap-2 pt-3 border-t border-tvk-border mt-auto",
                div { class: "animate-shimmer h-5 w-20 rounded-full" }
                div { class: "animate-shimmer flex-1 h-[3px] rounded-full" }
            }
        }
    }
}
