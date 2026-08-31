from scr.models import ClassificationResult

# Ordered priority list: first category whose keyword appears in the text wins.
# Order matters - e.g. a "spam" or "invoice" signal should win over a generic
# "solar" mention, so narrower/more specific categories are checked first.
#
# "legal_compliance" is deliberately the very first rule checked: it's a
# deterministic, non-negotiable gate that must win over every other category
# (including spam) and must be evaluated before any LLM classification is
# even attempted - a legal/compliance signal is never something we hand to a
# probabilistic model or let fall through to the ambiguous-case path below.
RULES = [
    ("legal_compliance", [
        "cease and desist", "legal action", "lawsuit", "litigation", "subpoena",
        "breach of contract", "regulatory breach", "compliance breach", "non-compliance",
        "regulator", "solicitor", "attorney", "court order", "legal notice",
        "data breach", "privacy breach", "gdpr", "defamation",
    ]),
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

# Category returned when an LLM classification attempt errors or times out.
# Never guess a business category from a failed/partial LLM response -
# fail safe instead (see main.py, which holds these for manual review,
# suppresses any reply, and makes no CRM/status change).
LLM_UNCLASSIFIED_CATEGORY = "LLM_UNCLASSIFIED"


def classify_email(subject: str, body: str, llm_client=None) -> ClassificationResult:
    """
    llm_client: optional object with a `.classify(text) -> (category, confidence)` method.
    Only ever consulted for genuinely ambiguous text (nothing matched a
    deterministic rule, including the legal_compliance gate above, which is
    always checked first and never deferred to the LLM). If llm_client is
    None (the default - no LLM configured), behaviour is unchanged from
    before: ambiguous text falls back to `general_enquiry`.
    """
    text = f"{subject} {body}".lower()

    for category, keywords in RULES:
        for kw in keywords:
            if kw in text:
                return ClassificationResult(category=category, confidence=0.95, method="deterministic")

    if llm_client is not None:
        try:
            category, confidence = llm_client.classify(text)
            return ClassificationResult(category=category, confidence=confidence, method="llm")
        except Exception:
            # Any LLM error or timeout is a fail-safe case, not a guess.
            return ClassificationResult(category=LLM_UNCLASSIFIED_CATEGORY, confidence=0.0, method="llm_error")

    # No rule matched and no LLM configured - be honest about uncertainty rather than guessing a category.
    return ClassificationResult(category=FALLBACK_CATEGORY, confidence=FALLBACK_CONFIDENCE, method="deterministic_fallback")
