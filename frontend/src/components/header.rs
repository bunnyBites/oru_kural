use dioxus::prelude::*;
use crate::models::AppState;

#[component]
pub fn Header() -> Element {
    let mut ctx = use_context::<Signal<AppState>>();
    let mut displayed = use_signal(|| 0usize);
    let mut animated = use_signal(|| false);

    use_effect(move || {
        let target = ctx.read().tweets.len();
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

    let dark = ctx.read().dark_mode;
    let toggle_icon = if dark { "☀" } else { "☾" };

    let toggle_theme = move |_| {
        let is_dark = !ctx.read().dark_mode;
        ctx.write().dark_mode = is_dark;
        let script = if is_dark {
            "document.documentElement.setAttribute('data-theme','dark'); localStorage.setItem('theme','dark');"
        } else {
            "document.documentElement.removeAttribute('data-theme'); localStorage.setItem('theme','light');"
        };
        let _ = document::eval(script);
    };

    rsx! {
        header {
            class: "bg-tvk-surface border-b border-tvk-border sticky top-0 z-10 backdrop-blur-sm",
            div {
                class: "max-w-[1280px] mx-auto px-4 sm:px-6 py-4 flex items-center justify-between gap-4",

                div {
                    h1 { class: "flex items-baseline gap-3",
                        span {
                            class: "font-tamil font-semibold text-tvk-maroon leading-tight",
                            style: "font-size: clamp(1.6rem, 3vw, 2.4rem);",
                            "ஒரு குரல்"
                        }
                        span {
                            class: "font-display italic font-normal text-tvk-text-secondary",
                            style: "font-size: clamp(0.9rem, 1.8vw, 1.2rem);",
                            "Oru Kural"
                        }
                    }
                    p { class: "text-xs font-body text-tvk-text-dim tracking-widest uppercase mt-1",
                        "Tamil Nadu Public Discourse Tracker"
                    }
                }

                div { class: "flex items-center gap-3",
                    span {
                        class: "font-mono text-sm text-tvk-gold bg-tvk-gold-soft \
                                border border-tvk-border px-3 py-1 rounded-full",
                        "{displayed} voices"
                    }
                    button {
                        class: "w-9 h-9 rounded-full flex items-center justify-center \
                                bg-tvk-surface-2 border border-tvk-border \
                                hover:border-tvk-border-hover \
                                text-tvk-text-secondary hover:text-tvk-maroon \
                                transition-all duration-200",
                        "aria-label": "Toggle dark mode",
                        onclick: toggle_theme,
                        "{toggle_icon}"
                    }
                }
            }
        }
    }
}
