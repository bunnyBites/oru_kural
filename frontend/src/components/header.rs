use dioxus::prelude::*;
use crate::models::AppState;

#[component]
pub fn Header() -> Element {
    let state = use_context::<Signal<AppState>>();
    let mut displayed = use_signal(|| 0usize);
    let mut animated = use_signal(|| false);

    use_effect(move || {
        let target = state.read().tweets.len();
        if target > 0 && !*animated.read() {
            animated.set(true);
            spawn(async move {
                for i in 1..=20usize {
                    gloo_timers::future::sleep(std::time::Duration::from_millis(40)).await;
                    displayed.set(target * i / 20);
                }
            });
        }
    });

    rsx! {
        header {
            class: "bg-tvk-bg border-b border-tvk-border px-6 py-4 sticky top-0 z-10",
            div { class: "max-w-[1280px] mx-auto flex items-center justify-between",
                div { class: "animate-card-enter", style: "animation-duration: 600ms",
                    h1 {
                        class: "font-display italic text-tvk-text",
                        style: "font-size: clamp(2rem, 4vw, 3.5rem); line-height: 1.1;",
                        "ஒரு குரல்"
                    }
                    p { class: "font-body text-sm text-tvk-muted tracking-widest uppercase mt-1",
                        "One Voice — Tamil Nadu Public Discourse Tracker"
                    }
                }
                span {
                    class: "bg-tvk-surface border border-tvk-border rounded-full \
                             px-3 py-1 font-mono text-sm text-tvk-gold animate-count-glow",
                    "{displayed} voices"
                }
            }
        }
    }
}
