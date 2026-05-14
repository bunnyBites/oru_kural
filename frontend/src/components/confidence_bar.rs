use dioxus::prelude::*;

#[component]
pub fn ConfidenceBar(confidence: f64) -> Element {
    let fill_color = match confidence {
        c if c >= 0.8 => "var(--color-tvk-gold)",
        c if c >= 0.5 => "var(--color-tvk-gold-dim)",
        _             => "var(--color-tvk-dim)",
    };
    let width_pct = (confidence * 100.0) as u32;

    rsx! {
        div { class: "w-16 h-[3px] bg-tvk-border rounded-full overflow-hidden",
            div {
                class: "h-full rounded-full animate-bar-fill",
                style: "width: {width_pct}%; background-color: {fill_color};",
            }
        }
    }
}
