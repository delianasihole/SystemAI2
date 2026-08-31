from scr.models import ActionRecommendation, ClassificationResult, ExtractionResult, CRMMatch

# Categories with a fixed action regardless of CRM match state.
FIXED_ACTIONS = {
    "spam": ("mark_as_spam", False),
    "internal_alert": ("escalate_system_issue", False),
    "recruitment": ("forward_application", True),
    "invoice_dispute": ("escalate_invoice_reconciliation", True),
    "technical_query": ("escalate_technical_review", True),
    "logistics_confirmation": ("confirm_logistics_and_reply", True),
    "partner_engagement": ("review_partnership", True),
}


def recommend_action(
    classification: ClassificationResult,
    extraction: ExtractionResult,
    crm_match: CRMMatch,
) -> ActionRecommendation:
    category = classification.category

    if category in FIXED_ACTIONS:
        action, response_required = FIXED_ACTIONS[category]
        return ActionRecommendation(recommended_action=action, response_required=response_required)

    # commercial_enquiry / general_enquiry: next action depends on CRM state.
    if crm_match.duplicate_records:
        return ActionRecommendation(recommended_action="resolve_duplicate_crm_record_then_reply", response_required=True)
    if crm_match.status == "strong_match":
        return ActionRecommendation(recommended_action="update_existing_crm_record", response_required=True)
    if crm_match.status == "possible_match":
        return ActionRecommendation(recommended_action="review_possible_match_before_reply", response_required=True)
    return ActionRecommendation(recommended_action="create_new_crm_record", response_required=True)
