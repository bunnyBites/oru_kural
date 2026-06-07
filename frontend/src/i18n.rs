/// All UI strings in one place.
/// Add a new language by copying one of the two statics and updating the strings.
pub struct Translations {
    // ── Header ──────────────────────────────────────────────
    pub subtitle: &'static str,
    pub tab_issues: &'static str,
    pub tab_events: &'static str,
    pub tab_stats: &'static str,

    // ── Filter bar ──────────────────────────────────────────
    pub filter_all: &'static str,
    pub search_placeholder: &'static str,
    // status labels
    pub status_open: &'static str,
    pub status_acknowledged: &'static str,
    pub status_in_progress: &'static str,
    pub status_resolved: &'static str,
    // category labels
    pub cat_infrastructure: &'static str,
    pub cat_health: &'static str,
    pub cat_education: &'static str,
    pub cat_demand: &'static str,
    pub cat_complaint: &'static str,
    pub cat_public_event: &'static str,
    pub cat_welcome: &'static str,
    pub cat_criticism: &'static str,
    pub cat_welfare: &'static str,
    pub cat_other: &'static str,

    // ── Issues board ────────────────────────────────────────
    pub no_issues: &'static str,
    pub load_more_issues: &'static str,
    pub error_load_issues: &'static str,

    // ── Issue detail ────────────────────────────────────────
    pub citizen_voices: &'static str, // prefix: "Citizen voices (N)"
    pub voices: &'static str,         // suffix: "🗣 N voices"
    pub first_raised: &'static str,
    pub cm_response: &'static str,
    pub view_source: &'static str,

    // ── Events feed ─────────────────────────────────────────
    pub all_events: &'static str,
    pub linked_to_issues: &'static str,
    pub no_events: &'static str,
    pub load_more_events: &'static str,
    pub error_load_events: &'static str,
    pub read_more: &'static str,
    pub linked_badge: &'static str,

    // ── Stats panel ─────────────────────────────────────────
    pub stats_heading: &'static str,
    pub stats_hint: &'static str,
    pub signals: &'static str,
    pub issues: &'static str,
    pub open: &'static str,
    pub signals_only: &'static str,
    pub last_updated: &'static str,
}

static EN: Translations = Translations {
    subtitle: "Tamil Nadu Civic Accountability Tracker",
    tab_issues: "Issues Board",
    tab_events: "CM Activity",
    tab_stats: "Stats",

    filter_all: "All",
    search_placeholder: "Search issues…",
    status_open: "Open",
    status_acknowledged: "Acknowledged",
    status_in_progress: "In Progress",
    status_resolved: "Resolved",
    cat_infrastructure: "Infrastructure",
    cat_health: "Health",
    cat_education: "Education",
    cat_demand: "Demand",
    cat_complaint: "Complaint",
    cat_public_event: "Public Event",
    cat_welcome: "Welcome",
    cat_criticism: "Criticism",
    cat_welfare: "Welfare Scheme",
    cat_other: "Other",

    no_issues: "No issues found.",
    load_more_issues: "Load more issues",
    error_load_issues: "Could not load issues. Tap to retry.",

    citizen_voices: "Citizen voices",
    voices: "voices",
    first_raised: "First raised:",
    cm_response: "CM Response",
    view_source: "View source →",

    all_events: "All",
    linked_to_issues: "Linked to issues",
    no_events: "No events found.",
    load_more_events: "Load more",
    error_load_events: "Could not load events. Tap to retry.",
    read_more: "Read more →",
    linked_badge: "Linked",

    stats_heading: "Signal breakdown",
    stats_hint: "Cards with issues are clickable — opens the Issues Board filtered by category.",
    signals: "signals",
    issues: "issues",
    open: "open",
    signals_only: "signals only — no issues clustered",
    last_updated: "Last updated",
};

static TA: Translations = Translations {
    subtitle: "தமிழ்நாடு குடிமக்கள் பொறுப்புணர்வு தட்டகம்",
    tab_issues: "சிக்கல் பலகை",
    tab_events: "முதலமைச்சர் செயல்பாடு",
    tab_stats: "புள்ளிவிவரங்கள்",

    filter_all: "அனைத்தும்",
    search_placeholder: "சிக்கல்களைத் தேடுக…",
    status_open: "திறந்த",
    status_acknowledged: "அறியப்பட்டது",
    status_in_progress: "நடைபெறுகிறது",
    status_resolved: "தீர்க்கப்பட்டது",
    cat_infrastructure: "உள்கட்டமைப்பு",
    cat_health: "சுகாதாரம்",
    cat_education: "கல்வி",
    cat_demand: "கோரிக்கை",
    cat_complaint: "புகார்",
    cat_public_event: "பொது நிகழ்வு",
    cat_welcome: "வரவேற்பு",
    cat_criticism: "விமர்சனம்",
    cat_welfare: "நல திட்டம்",
    cat_other: "மற்றவை",

    no_issues: "சிக்கல்கள் எதுவும் இல்லை.",
    load_more_issues: "மேலும் சிக்கல்கள் காண்க",
    error_load_issues: "சிக்கல்களை ஏற்ற முடியவில்லை. மீண்டும் முயற்சிக்க தொடவும்.",

    citizen_voices: "குடிமக்கள் குரல்கள்",
    voices: "குரல்கள்",
    first_raised: "முதலில் எழுப்பப்பட்டது:",
    cm_response: "முதலமைச்சர் பதில்",
    view_source: "மூலத்தைக் காண்க →",

    all_events: "அனைத்தும்",
    linked_to_issues: "சிக்கல்களுடன் இணைக்கப்பட்டவை",
    no_events: "நிகழ்வுகள் எதுவும் இல்லை.",
    load_more_events: "மேலும் காண்க",
    error_load_events: "நிகழ்வுகளை ஏற்ற முடியவில்லை. மீண்டும் முயற்சிக்க தொடவும்.",
    read_more: "மேலும் படிக்க →",
    linked_badge: "இணைக்கப்பட்டது",

    stats_heading: "சமிக்ஞை பகுப்பு",
    stats_hint: "சிக்கல்கள் உள்ள அட்டைகள் கிளிக் செய்யத்தக்கவை — வகை வாரியாக சிக்கல் பலகை திறக்கும்.",
    signals: "சமிக்ஞைகள்",
    issues: "சிக்கல்கள்",
    open: "திறந்த",
    signals_only: "சமிக்ஞைகள் மட்டும் — சிக்கல்கள் கொத்தாக்கப்படவில்லை",
    last_updated: "கடைசியாக புதுப்பிக்கப்பட்டது",
};

/// Return the right translation set. Call once per component render.
pub fn get(tamil: bool) -> &'static Translations {
    if tamil { &TA } else { &EN }
}

impl Translations {
    /// Translate a category API value (e.g. "Infrastructure") to its display label.
    pub fn category_label(&self, val: &str) -> &'static str {
        match val {
            "Infrastructure"  => self.cat_infrastructure,
            "Health"          => self.cat_health,
            "Education"       => self.cat_education,
            "Demand"          => self.cat_demand,
            "Complaint"       => self.cat_complaint,
            "Public Event"    => self.cat_public_event,
            "Welcome"         => self.cat_welcome,
            "Criticism"       => self.cat_criticism,
            "Welfare Scheme"  => self.cat_welfare,
            "Other"           => self.cat_other,
            _                 => self.cat_other, // safe fallback
        }
    }
}
