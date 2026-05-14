use dioxus::prelude::*;

#[component]
pub fn CategoryBadge(category: String) -> Element {
    let color = category_color(&category);
    rsx! {
        span {
            class: "inline-block px-2.5 py-0.5 rounded-full text-xs font-medium animate-badge-shine",
            style: "color: {color}; background-color: {color}26; border: 1px solid {color}99;",
            "{category}"
        }
    }
}

fn category_color(cat: &str) -> &'static str {
    match cat {
        "Demand"         => "#C0392B",
        "Complaint"      => "#E67E22",
        "Public Event"   => "#8E44AD",
        "Welcome"        => "#27AE60",
        "Infrastructure" => "#2980B9",
        "Health"         => "#16A085",
        "Education"      => "#D35400",
        "Criticism"      => "#C0392B",
        _                => "#7F8C8D",
    }
}
