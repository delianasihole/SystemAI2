from scr.models import ResponseDraft, ActionRecommendation, ClassificationResult, ExtractionResult

# Every draft below only states facts that came from extraction/enrichment
# (extraction.facts, CRM-sourced fields). Where a fact wasn't verified, the
# draft asks for it instead of inventing a number. Drafts are never sent -
# they always require human approval (see main.py / ApprovalStatus).

SIGNATURE = "BEDA TEAM"


def generate_response(
    classification: ClassificationResult,
    extraction: ExtractionResult,
    action: ActionRecommendation,
) -> ResponseDraft:
    if not action.response_required:
        return ResponseDraft(required=False, draft=None, confidence=1.0, grounded_sources=extraction.evidence)

    category = classification.category
    name = extraction.contact_name.value or "there"
    facts = extraction.facts
    blockers = facts.get("blockers", [])

    if category == "commercial_enquiry":
        lines = [f"Hi {name},", "", "Thank you for reaching out about your energy requirements."]
        if extraction.location.value:
            lines.append(f"We understand you're based in {extraction.location.value}.")
        if facts.get("consumption_kwh"):
            lines.append(f"We've noted your estimated consumption of {facts['consumption_kwh']} kWh from the attached bill.")
        else:
            lines.append("To prepare an accurate proposal, could you share your most recent electricity bill or approximate annual consumption?")
        if blockers:
            lines.append("We've also noted an open item on your side that may need resolving before we can proceed (see notes) - happy to advise once that's clear.")
        lines += ["", "One of our team will follow up shortly to discuss next steps.", "", "Regards,", SIGNATURE]
        confidence = 0.85 if facts.get("consumption_kwh") else 0.6

    elif category == "invoice_dispute":
        lines = [f"Hi {name},", "", "Thanks for flagging the invoice discrepancy."]
        if facts.get("invoice_variance"):
            lines.append(f"We can confirm a variance of {facts['invoice_variance']} between the purchase order and invoice, and our accounts team is reviewing it.")
        else:
            lines.append("Our accounts team is reviewing the purchase order and invoice values and will confirm shortly.")
        lines += ["", "Regards,", SIGNATURE]
        confidence = 0.85 if facts.get("invoice_variance") else 0.6

    elif category == "technical_query":
        lines = [
            f"Hi {name},", "",
            "Thank you for the technical question. Our engineering team will review the specification "
            "and confirm the required limits/study directly.",
            "", "Regards,", SIGNATURE,
        ]
        confidence = 0.6  # no technical claim made in the draft itself

    elif category == "logistics_confirmation":
        lines = [
            f"Hi {name},", "",
            "Thanks for the update. We will confirm the project status by the date you requested.",
            "", "Regards,", SIGNATURE,
        ]
        confidence = 0.6

    elif category == "recruitment":
        lines = [
            f"Hi {name},", "",
            "Thank you for your application. We've forwarded your details to our Marketing team for review.",
            "", "Regards,", SIGNATURE,
        ]
        confidence = 0.8

    elif category == "partner_engagement":
        lines = [
            f"Hi {name},", "",
            "Thank you for your interest in partnering with us. Our team will review and follow up.",
            "", "Regards,", SIGNATURE,
        ]
        confidence = 0.7

    else:  # general_enquiry fallback - deliberately generic, no invented details
        lines = [
            f"Hi {name},", "",
            "Thank you for your message. Our team will review the details and respond shortly.",
            "", "Regards,", SIGNATURE,
        ]
        confidence = 0.5

    return ResponseDraft(required=True, draft="\n".join(lines), confidence=confidence, grounded_sources=extraction.evidence)
