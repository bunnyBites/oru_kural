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
        div { class: "flex gap-3 overflow-x-auto pb-2 mb-6",
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
            let delay_ms = (index * 80) as u32;
            spawn(async move {
                gloo_timers::future::sleep(std::time::Duration::from_millis(delay_ms as u64)).await;
                for i in 1..=15usize {
                    gloo_timers::future::sleep(std::time::Duration::from_millis(40)).await;
                    displayed.set(count * i / 15);
                }
            });
        }
    });

    let width_pct = if total > 0 { (count * 100 / total).min(100) } else { 0 };
    let cat = category.clone();

    rsx! {
        div {
            class: "bg-tvk-surface border border-tvk-border rounded-lg p-4 min-w-[140px] \
                    cursor-pointer hover:border-tvk-border-hover transition-colors duration-150",
            onclick: move |_| ctx.write().filtered_category = Some(cat.clone()),
            p { class: "text-xs text-tvk-muted mb-1", "{category}" }
            p { class: "text-2xl font-mono text-tvk-gold animate-count-glow", "{displayed}" }
            div { class: "mt-2 w-full h-[3px] bg-tvk-border rounded-full overflow-hidden",
                div {
                    class: "h-full bg-tvk-gold rounded-full animate-bar-fill",
                    style: "width: {width_pct}%;",
                }
            }
        }
    }
}
