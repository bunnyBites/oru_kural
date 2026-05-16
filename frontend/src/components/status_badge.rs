use dioxus::prelude::*;

fn status_display(status: &str) -> (&'static str, &'static str) {
    match status {
        "open"         => ("badge-status-open", "Open"),
        "acknowledged" => ("badge-status-ack", "Acknowledged"),
        "in_progress"  => ("badge-status-progress", "In Progress"),
        "resolved"     => ("badge-status-resolved", "Resolved"),
        _              => ("badge-other", "Unknown"),
    }
}

#[derive(Props, PartialEq, Clone)]
pub struct StatusBadgeProps {
    pub status: String,
}

#[component]
pub fn StatusBadge(props: StatusBadgeProps) -> Element {
    let (badge_class, label) = status_display(&props.status);
    rsx! {
        span {
            class: "inline-flex items-center px-2 py-0.5 rounded-full text-xs font-body \
                    font-medium whitespace-nowrap shrink-0 {badge_class}",
            "{label}"
        }
    }
}
