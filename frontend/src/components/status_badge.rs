use dioxus::prelude::*;

fn status_display(status: &str) -> (&'static str, &'static str) {
    match status {
        "open" => ("#B83227", "Open"),
        "acknowledged" => ("#C96A18", "Acknowledged"),
        "in_progress" => ("#1A6FA8", "In Progress"),
        "resolved" => ("#1E8A4A", "Resolved"),
        _ => ("#6B7280", "Unknown"),
    }
}

#[derive(Props, PartialEq, Clone)]
pub struct StatusBadgeProps {
    pub status: String,
}

#[component]
pub fn StatusBadge(props: StatusBadgeProps) -> Element {
    let (color, label) = status_display(&props.status);
    let bg = format!("{color}18");
    let border = format!("1px solid {color}40");
    rsx! {
        span {
            class: "inline-flex items-center px-2 py-0.5 rounded-full text-xs font-body font-medium whitespace-nowrap shrink-0",
            style: "color: {color}; background: {bg}; border: {border};",
            "{label}"
        }
    }
}
