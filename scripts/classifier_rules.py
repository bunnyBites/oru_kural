"""
Rules-based pre-classifier for Tamil Nadu civic tweets.

Import and call classify_by_rules() before sending batches to Gemini.
This module has no runnable entry point.
"""

# Tamil and English keyword patterns per category
# Updated for 2026 TVK/Vijay government — new schemes and party keywords added
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
        # 2026 grievance channel keywords
        "cmhelpline", "1100", "mudhalvarin mugavari", "முதல்வரின் முகவரி",
    ],
    "Welcome": [
        "வாழ்த்துகிறோம்", "வரவேற்கிறோம்", "வணக்கம்", "welcome", "congratulations",
        "congrats", "felicitate", "greetings", "வாழ்த்துக்கள்", "நல்வரவு",
        # 2026: new CM oath / TVK victory
        "sworn in", "oath", "பதவியேற்பு", "வெற்றி", "tvk wins", "cm vijay",
        "விஜய் முதல்வர்",
    ],
    "Public Event": [
        "inaugurated", "launched", "திறந்து வைத்தார்", "திறக்கப்பட்டது",
        "நேரில் கலந்துகொண்டார்", "திறப்பு விழா", "கலந்துகொண்டனர்",
        "ceremony", "event", "விழா",
        # 2026: Vetri TN Super App & new scheme launches
        "vetri tn", "வெற்றி TN", "super app",
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
        # 2026: Tamizh Pudhalvan scholarship scheme (₹1000/month for male students)
        "tamizh pudhalvan", "தமிழ் புதல்வன்", "umis",
    ],
    "Welfare Scheme": [
        # 2026 TVK government flagship schemes
        "vetri nichayam", "வெற்றி நிச்சயம்", "naan mudhalvan", "நான் முதல்வன்",
        "neengal nalama", "நீங்கள் நலமா", "tamizh pudhalvan", "தமிழ் புதல்வன்",
        "citizen privilege card", "குடிமக்கள் சலுகை அட்டை",
        "mudhalvar makkal sevai nanbar", "முதல்வர் மக்கள் சேவை நண்பர்",
        "skill training", "திறன் பயிற்சி", "tnuwwb", "welfare board",
        # Legacy DMK schemes still active
        "kalaignar", "கலைஞர்", "magalir urimai", "மகளிர் உரிமை",
    ],
    "Criticism": [
        "shame", "வெட்கம்", "failure", "fails", "corrupt", "ஊழல்", "betrayed",
        "broken promise", "நம்பிக்கை துரோகம்", "resign", "ராஜினாமா",
        "incompetent", "useless",
        # 2026: opposition criticism keywords
        "கொள்கை துரோகம்", "aiadmk", "bjp protest", "வாக்குறுதி மீறல்",
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
