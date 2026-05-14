use dioxus::prelude::*;
use crate::components::AppShell;

#[component]
pub fn Home() -> Element {
    rsx! { AppShell {} }
}
