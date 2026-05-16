use dioxus::prelude::*;

use crate::models::Tab;
use super::app_shell::AppCtx;

#[component]
pub fn Header() -> Element {
    let ctx = use_context::<AppCtx>();
    let mut active_tab = ctx.active_tab;
    let mut dark_mode = ctx.dark_mode;

    let tab = active_tab.read().clone();
    let is_dark = *dark_mode.read();
    let toggle_icon = if is_dark { "☀" } else { "☾" };

    let active_cls = "px-4 py-2.5 font-body text-sm font-medium text-tvk-maroon \
                      border-b-2 border-tvk-maroon -mb-px bg-transparent transition-all";
    let inactive_cls = "px-4 py-2.5 font-body text-sm font-medium text-tvk-text-dim \
                        border-b-2 border-transparent -mb-px hover:text-tvk-text transition-all";

    rsx! {
        header {
            class: "bg-tvk-surface border-b border-tvk-border sticky top-0 z-10 backdrop-blur-sm",
            div { class: "max-w-[1280px] mx-auto px-4 sm:px-6",

                div { class: "flex items-center justify-between py-4",
                    div {
                        h1 { class: "flex items-baseline gap-3",
                            span {
                                class: "font-tamil font-semibold text-tvk-maroon leading-tight",
                                style: "font-size: clamp(1.4rem, 2.5vw, 2rem);",
                                "ஒரு குரல்"
                            }
                            span {
                                class: "font-display italic font-normal text-tvk-text-secondary",
                                style: "font-size: clamp(0.85rem, 1.5vw, 1.1rem);",
                                "Oru Kural"
                            }
                        }
                        p { class: "text-xs font-body text-tvk-text-dim tracking-widest uppercase mt-0.5",
                            "Tamil Nadu Civic Accountability Tracker"
                        }
                    }
                    button {
                        class: "w-9 h-9 rounded-full flex items-center justify-center \
                                bg-tvk-surface-2 border border-tvk-border \
                                hover:border-tvk-border-hover text-tvk-text-secondary \
                                hover:text-tvk-maroon transition-all duration-200",
                        "aria-label": "Toggle dark mode",
                        onclick: move |_| {
                            let now_dark = !*dark_mode.read();
                            dark_mode.set(now_dark);
                            let script = if now_dark {
                                "document.documentElement.setAttribute('data-theme','dark'); \
                                 localStorage.setItem('theme','dark');"
                            } else {
                                "document.documentElement.removeAttribute('data-theme'); \
                                 localStorage.setItem('theme','light');"
                            };
                            let _ = document::eval(script);
                        },
                        "{toggle_icon}"
                    }
                }

                div { class: "flex gap-1 border-t border-tvk-border",
                    button {
                        class: if tab == Tab::Issues { active_cls } else { inactive_cls },
                        "aria-label": "Issues Board tab",
                        onclick: move |_| active_tab.set(Tab::Issues),
                        "Issues Board"
                    }
                    button {
                        class: if tab == Tab::Events { active_cls } else { inactive_cls },
                        "aria-label": "CM Activity tab",
                        onclick: move |_| active_tab.set(Tab::Events),
                        "CM Activity"
                    }
                    button {
                        class: if tab == Tab::Stats { active_cls } else { inactive_cls },
                        "aria-label": "Stats tab",
                        onclick: move |_| active_tab.set(Tab::Stats),
                        "Stats"
                    }
                }
            }
        }
    }
}
