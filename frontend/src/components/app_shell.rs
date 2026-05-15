use dioxus::prelude::*;

use crate::models::Tab;
use super::header::Header;
use super::issues_board::IssuesBoard;
use super::events_feed::EventsFeed;
use super::stats_panel::StatsPanel;

#[derive(Clone, Copy)]
pub struct AppCtx {
    pub active_tab: Signal<Tab>,
    pub dark_mode: Signal<bool>,
}

#[component]
pub fn AppShell() -> Element {
    let active_tab = use_signal(|| Tab::Issues);
    let dark_mode = use_signal(|| false);

    use_context_provider(|| AppCtx { active_tab, dark_mode });

    use_effect(move || {
        let mut dm = dark_mode;
        spawn(async move {
            let mut ev = document::eval(
                "const s = localStorage.getItem('theme'); \
                 const d = s === 'dark'; \
                 if (d) document.documentElement.setAttribute('data-theme','dark'); \
                 dioxus.send(d);",
            );
            if let Ok(dark) = ev.recv::<bool>().await {
                if dark {
                    dm.set(true);
                }
            }
        });
    });

    let tab = active_tab.read().clone();

    rsx! {
        div { class: "min-h-screen bg-tvk-bg transition-colors duration-300",
            Header {}
            main { class: "max-w-[1280px] mx-auto px-4 sm:px-6 py-8",
                match tab {
                    Tab::Issues => rsx! { IssuesBoard {} },
                    Tab::Events => rsx! { EventsFeed {} },
                    Tab::Stats  => rsx! { StatsPanel {} },
                }
            }
        }
    }
}
