"""
Rules-based pre-classifier for Tamil Nadu civic tweets.

Import and call classify_by_rules() before sending batches to Gemini.
This module has no runnable entry point.
"""

# Tamil and English keyword patterns per category
RULES: dict[str, list[str]] = {
    "Demand": [
        "please", "request", "வேண்டுகிறோம்", "வேண்டுகிறேன்", "கோரிக்கை",
        "கோருகிறோம்", "நடவடிக்கை எடுக்க", "should", "must", "அவசியம்",
        "தயவுசெய்து", "கேட்டுக்கொள்கிறோம்",
    ],
    "Complaint": [
        "problem", "issue", "பிரச்சனை", "பிரச்சினை", "complaint", "not working",
        "broken", "failed", "failure", "சிரமம்", "கஷ்டம்", "அவதிப்படுகிறோம்",
        "நடக்கவில்லை", "இல்லை",
    ],
    "Welcome": [
        "வாழ்த்துகிறோம்", "வரவேற்கிறோம்", "வணக்கம்", "welcome", "congratulations",
        "congrats", "felicitate", "greetings", "வாழ்த்துக்கள்", "நல்வரவு",
    ],
    "Public Event": [
        "inaugurated", "launched", "திறந்து வைத்தார்", "திறக்கப்பட்டது",
        "நேரில் கலந்துகொண்டார்", "திறப்பு விழா", "கலந்துகொண்டனர்",
        "ceremony", "event", "விழா",
    ],
    "Infrastructure": [
        "road", "சாலை", "water", "தண்ணீர்", "power", "மின்சாரம்", "electricity",
        "bus", "பேருந்து", "metro", "மெட்ரோ", "bridge", "பாலம்", "transport",
        "போக்குவரத்து",
    ],
    "Health": [
        "hospital", "மருத்துவமனை", "medicine", "மருந்து", "doctor", "மருத்துவர்",
        "disease", "நோய்", "health", "சுகாதாரம்", "ambulance", "treatment",
        "சிகிச்சை",
    ],
    "Education": [
        "school", "பள்ளி", "college", "கல்லூரி", "scholarship", "உதவித்தொகை",
        "student", "மாணவர்", "education", "கல்வி", "university", "பல்கலைக்கழகம்",
        "exam", "தேர்வு",
    ],
    "Criticism": [
        "shame", "வெட்கம்", "failure", "fails", "corrupt", "ஊழல்", "betrayed",
        "broken promise", "நம்பிக்கை துரோகம்", "resign", "ராஜினாமா",
        "incompetent", "useless",
    ],
}

RULE_CONFIDENCE: float = 0.75


def classify_by_rules(tweet_id: str, content: str) -> dict | None:
    """
    Returns {"id": tweet_id, "category": str, "confidence": float}
    if a rule matches, else None.
    First-match wins — order of RULES dict is priority order.
    Matching is case-insensitive on the content.
    """
    content_lower = content.lower()
    for category, patterns in RULES.items():
        for pattern in patterns:
            if pattern.lower() in content_lower:
                return {"id": tweet_id, "category": category, "confidence": RULE_CONFIDENCE}
    return None
