use dioxus::prelude::*;

#[component]
pub fn CategoryBadge(category: String) -> Element {
    let color = category_color(&category);
    rsx! {
        span {
            class: "inline-flex items-center font-body text-xs font-medium \
                    px-2.5 py-0.5 rounded-full whitespace-nowrap shrink-0",
            style: "color: {color}; background-color: {color}18; border: 1px solid {color}40;",
            "{category}"
        }
    }
}

fn category_color(cat: &str) -> &'static str {
    match cat {
        "Demand"         => "#B83227",
        "Complaint"      => "#C96A18",
        "Public Event"   => "#7B3AA8",
        "Welcome"        => "#1E8A4A",
        "Infrastructure" => "#1A6FA8",
        "Health"         => "#0E7A68",
        "Education"      => "#C04A00",
        "Criticism"      => "#B83227",
        _                => "#6B7280",
    }
}
