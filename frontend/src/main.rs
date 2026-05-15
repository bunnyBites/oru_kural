mod api;
mod components;
mod models;

use dioxus::prelude::*;

use components::app_shell::AppShell;

fn main() {
    dioxus::launch(App);
}

#[allow(non_snake_case)]
fn App() -> Element {
    rsx! {
        document::Stylesheet { href: asset!("/assets/tailwind.css") }
        AppShell {}
    }
}
