from scr.models import ClassificationResult

# Ordered priority list: first category whose keyword appears in the text wins.
# Order matters - e.g. a "spam" or "invoice" signal should win over a generic
# "solar" mention, so narrower/more specific categories are checked first.
RULES = [
    ("spam", ["cryptocurrency", "expires in 24 hours", "special price", "reply now", "act now", "lottery"]),
    ("internal_alert", ["sync failed", "oauth token", "unsynchronised", "retry disabled"]),
    ("recruitment", ["internship", "resume", "cv", "job application", "portfolio", "vacancy"]),
    ("invoice_dispute", ["invoice", "purchase order", "po ", "does not match", "reconcil"]),
    ("technical_query", ["harmonic", "thd", "specification", "point of common coupling", "inverter design"]),
    ("logistics_confirmation", ["crew", "confirm by", "availability", "proceeding"]),
    ("partner_engagement", ["partnership", "joint venture", "collaboration"]),
    ("commercial_enquiry", [
        "solar", "battery", "batteries", "led", "lighting upgrade", "energy efficiency",
        "electricity", "consumption", "kwh", "reduce operating cost", "quote",
    ]),
]

FALLBACK_CATEGORY = "general_enquiry"
FALLBACK_CONFIDENCE = 0.5


def classify_email(subject: str, body: str) -> ClassificationResult:
    text = f"{subject} {body}".lower()

    for category, keywords in RULES:
        for kw in keywords:
            if kw in text:
                return ClassificationResult(category=category, confidence=0.95, method="deterministic")

    # No rule matched - be honest about uncertainty rather than guessing a category.
    return ClassificationResult(category=FALLBACK_CATEGORY, confidence=FALLBACK_CONFIDENCE, method="deterministic_fallback")
