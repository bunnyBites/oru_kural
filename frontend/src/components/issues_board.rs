use dioxus::prelude::*;

use crate::models::Issue;
use super::app_shell::AppCtx;
use super::filter_bar::FilterBar;
use super::skeleton_card::SkeletonCard;
use super::issue_card::IssueCard;
use super::issue_detail::IssueDetail;

#[component]
pub fn IssuesBoard() -> Element {
    let ctx = use_context::<AppCtx>();
    let category_filter = ctx.category_filter;

    let status_filter: Signal<Option<String>> = use_signal(|| None);
    let search_query: Signal<String> = use_signal(String::new);
    let mut issues: Signal<Vec<Issue>> = use_signal(Vec::new);
    let mut next_cursor: Signal<Option<String>> = use_signal(|| None);
    let mut has_more: Signal<bool> = use_signal(|| false);
    let mut loading: Signal<bool> = use_signal(|| true);
    let mut error: Signal<Option<String>> = use_signal(|| None);
    let mut selected_issue_id: Signal<Option<i64>> = use_signal(|| None);

    // Lock body scroll when drawer is open so the background doesn't scroll
    use_effect(move || {
        let locked = selected_issue_id.read().is_some();
        let script = if locked {
            "document.body.style.overflow = 'hidden';"
        } else {
            "document.body.style.overflow = '';"
        };
        let _ = document::eval(script);
    });

    use_effect(move || {
        let status = status_filter.read().clone();
        let category = category_filter.read().clone();

        spawn(async move {
            loading.set(true);
            error.set(None);
            selected_issue_id.set(None);
            match crate::api::fetch_issues(status, category, None).await {
                Ok((data, cursor)) => {
                    has_more.set(cursor.is_some());
                    next_cursor.set(cursor);
                    issues.set(data);
                }
                Err(e) => {
                    eprintln!("fetch_issues: {e}");
                    error.set(Some("Could not load issues. Tap to retry.".into()));
                }
            }
            loading.set(false);
        });
    });

    let search = search_query.read().to_lowercase();
    let all_issues = issues.read();
    let filtered: Vec<Issue> = all_issues
        .iter()
        .filter(|i| {
            if search.is_empty() {
                return true;
            }
            i.title.to_lowercase().contains(&search)
                || i.summary.as_deref().unwrap_or("").to_lowercase().contains(&search)
        })
        .cloned()
        .collect();
    drop(all_issues);

    let is_loading = *loading.read();
    let has_more_val = *has_more.read();
    let selected = *selected_issue_id.read();
    let error_msg = error.read().clone();

    rsx! {
        div { class: "space-y-6",
            FilterBar { status_filter, category_filter, search_query }

            if let Some(msg) = error_msg {
                div {
                    class: "flex items-center justify-between gap-3 rounded-lg border \
                            border-red-200 bg-red-50 px-4 py-3 text-sm font-body \
                            text-red-700 cursor-pointer",
                    style: "border-color: #B8322740; background-color: #B8322710; color: #B83227;",
                    onclick: move |_| {
                        let status = status_filter.read().clone();
                        let category = category_filter.read().clone();
                        error.set(None);
                        loading.set(true);
                        spawn(async move {
                            match crate::api::fetch_issues(status, category, None).await {
                                Ok((data, cursor)) => {
                                    has_more.set(cursor.is_some());
                                    next_cursor.set(cursor);
                                    issues.set(data);
                                }
                                Err(e) => {
                                    eprintln!("fetch_issues retry: {e}");
                                    error.set(Some("Could not load issues. Tap to retry.".into()));
                                }
                            }
                            loading.set(false);
                        });
                    },
                    span { "{msg}" }
                    span { class: "shrink-0 opacity-70", "↺ Retry" }
                }
            }

            if is_loading {
                div { class: "grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4",
                    for _ in 0..6usize {
                        SkeletonCard {}
                    }
                }
            } else if filtered.is_empty() {
                div { class: "py-20 text-center",
                    p { class: "font-body text-tvk-text-dim text-sm", "No issues found." }
                }
            } else {
                div { class: "grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4",
                    for (i, issue) in filtered.iter().enumerate() {
                        IssueCard {
                            key: "{issue.id}",
                            issue: issue.clone(),
                            index: i,
                            on_click: move |id| selected_issue_id.set(Some(id)),
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
                        "aria-label": "Load more issues",
                        onclick: move |_| {
                            let cursor = next_cursor.read().clone();
                            let status = status_filter.read().clone();
                            let category = category_filter.read().clone();
                            spawn(async move {
                                match crate::api::fetch_issues(status, category, cursor).await {
                                    Ok((mut data, new_cursor)) => {
                                        has_more.set(new_cursor.is_some());
                                        next_cursor.set(new_cursor);
                                        issues.write().append(&mut data);
                                    }
                                    Err(e) => eprintln!("load_more: {e}"),
                                }
                            });
                        },
                        "Load more issues"
                    }
                }
            }
        }

        // Drawer modal — rendered outside the scrolling content flow
        if let Some(id) = selected {
            div {
                class: "fixed inset-0 z-50 animate-fade-in",
                style: "background: rgba(0,0,0,0.45); backdrop-filter: blur(2px);",
                onclick: move |_| selected_issue_id.set(None),

                div {
                    class: "absolute right-0 top-0 h-full w-full max-w-2xl \
                            bg-tvk-surface border-l border-tvk-border shadow-2xl \
                            overflow-y-auto animate-drawer-in",
                    onclick: move |e| e.stop_propagation(),

                    IssueDetail {
                        key: "{id}",
                        id,
                        on_close: move |_| selected_issue_id.set(None),
                    }
                }
            }
        }
    }
}
