use dioxus::prelude::*;
use std::collections::HashMap;
use crate::models::AppState;

#[component]
pub fn StatsPanel() -> Element {
    let state = use_context::<Signal<AppState>>();
    let s = state.read();
    if s.loading || s.tweets.is_empty() {
        return rsx! {};
    }

    let mut counts: HashMap<String, usize> = HashMap::new();
    for tweet in &s.tweets {
        if let Some(cat) = &tweet.category {
            *counts.entry(cat.clone()).or_insert(0) += 1;
        }
    }
    let total_categorized: usize = counts.values().sum();
    let mut sorted: Vec<(String, usize)> = counts.into_iter().collect();
    sorted.sort_by(|a, b| b.1.cmp(&a.1));
    sorted.truncate(4);

    rsx! {
        div { class: "grid grid-cols-2 sm:grid-cols-4 gap-3",
            for (index, (category, count)) in sorted.into_iter().enumerate() {
                StatCard {
                    key: "{category}",
                    category,
                    count,
                    total: total_categorized,
                    index,
                }
            }
        }
    }
}

#[component]
fn StatCard(category: String, count: usize, total: usize, index: usize) -> Element {
    let mut ctx = use_context::<Signal<AppState>>();
    let mut displayed = use_signal(|| 0usize);
    let mut animated = use_signal(|| false);

    use_effect(move || {
        if count > 0 && !*animated.read() {
            animated.set(true);
            let delay_ms = (index * 80) as u64;
            spawn(async move {
                gloo_timers::future::sleep(std::time::Duration::from_millis(delay_ms)).await;
                for i in 1..=15usize {
                    gloo_timers::future::sleep(std::time::Duration::from_millis(40)).await;
                    displayed.set(count * i / 15);
                }
            });
        }
    });

    let pct = if total > 0 { (count * 100 / total).min(100) } else { 0 };
    let cat = category.clone();

    rsx! {
        div {
            class: "bg-tvk-surface border border-tvk-border rounded-xl p-4 \
                    cursor-pointer hover:border-tvk-border-hover \
                    hover:shadow-sm transition-all duration-150",
            onclick: move |_| ctx.write().filtered_category = Some(cat.clone()),

            p { class: "text-xs font-body font-medium text-tvk-text-dim uppercase tracking-wider mb-2",
                "{category}"
            }
            p { class: "font-mono text-2xl font-normal text-tvk-gold leading-none mb-3",
                "{displayed}"
            }
            div { class: "w-full h-[3px] bg-tvk-border rounded-full overflow-hidden",
                div {
                    class: "h-full bg-tvk-gold rounded-full animate-bar-fill",
                    style: "width: {pct}%;",
                }
            }
            p { class: "text-xs font-body text-tvk-text-dim mt-2",
                "{pct}% of total"
            }
        }
    }
}
