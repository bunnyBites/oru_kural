use dioxus::prelude::*;

#[component]
pub fn CategoryBadge(category: String) -> Element {
    let badge_class = category_class(&category);
    rsx! {
        span {
            class: "inline-flex items-center font-body text-xs font-medium \
                    px-2.5 py-0.5 rounded-full whitespace-nowrap shrink-0 {badge_class}",
            "{category}"
        }
    }
}

fn category_class(cat: &str) -> &'static str {
    match cat {
        "Demand"         => "badge-demand",
        "Complaint"      => "badge-complaint",
        "Public Event"   => "badge-public-event",
        "Welcome"        => "badge-welcome",
        "Infrastructure" => "badge-infrastructure",
        "Health"         => "badge-health",
        "Education"      => "badge-education",
        "Criticism"      => "badge-criticism",
        _                => "badge-other",
    }
}
