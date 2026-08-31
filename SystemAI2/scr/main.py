import json
from scr.models import ProcessingResult, ApprovalStatus, ResponseDraft, ExtractionField
from scr.classifier import classify_email
from scr.extractor import extract_fields
from scr.enricher import enrich
from scr.deduplicator import deduplicate
from scr.action_engine import recommend_action
from scr.router import route_action
from scr.responder import generate_response
from scr.audit import log_event, write_audit_log
from scr.correlator import find_contact_corrections

DATA_PATH = "data/emails.json"


def process_email(email: dict, llm_client=None) -> ProcessingResult:
    """
    llm_client: optional, forwarded to classify_email() - only consulted for
    text that matches no deterministic rule (legal_compliance included, which
    always wins first). Left as None by default: no LLM is called at runtime
    unless a caller explicitly configures one, matching this pipeline's
    no-external-calls-by-default design.
    """
    audit_log = []

    # Step 1: Classification - subject/body content only, never treated as instructions.
    classification = classify_email(email.get("subject", ""), email.get("body", ""), llm_client=llm_client)
    audit_log = log_event(
        audit_log, "classification", email["id"], classification.__dict__,
        reason=f"Matched category '{classification.category}' via {classification.method} keyword rules.",
    )

    # Step 2: Extraction
    extraction = extract_fields(email)
    audit_log = log_event(
        audit_log, "extraction", email["id"],
        {k: v.__dict__ for k, v in extraction.__dict__.items() if k not in ("evidence", "facts")},
        reason="Resolved contact/company/location/service from sender header, body text, and known CRM records.",
    )

    # Step 3: Enrichment (attachment-linked documents only)
    extraction = enrich(extraction, email)
    audit_log = log_event(
        audit_log, "enrichment", email["id"], {"facts": extraction.facts, "evidence": extraction.evidence},
        reason="Parsed the email's linked attachment (if any) for verifiable numeric facts.",
    )

    # Step 4: CRM match / duplicate detection
    crm_match = deduplicate(extraction)
    audit_log = log_event(
        audit_log, "crm_match", email["id"], crm_match.__dict__,
        reason=f"CRM status '{crm_match.status}' from email/phone/name/company similarity against crm.csv.",
    )

    # Step 5: Action recommendation
    action = recommend_action(classification, extraction, crm_match)
    audit_log = log_event(
        audit_log, "action_recommendation", email["id"], action.__dict__,
        reason=f"Category '{classification.category}' + CRM status '{crm_match.status}' mapped to '{action.recommended_action}'.",
    )

    # Step 6: Routing (derived from staff_directory.json "owns" fields)
    owner = route_action(classification.category)
    audit_log = log_event(
        audit_log, "routing", email["id"], {"owner": owner},
        reason="Owner resolved from staff_directory.json based on category ownership.",
    )

    # Step 7: Response draft (grounded only in verified facts, never auto-sent)
    response = generate_response(classification, extraction, action)
    audit_log = log_event(
        audit_log, "response_draft", email["id"], {"required": response.required, "confidence": response.confidence},
        reason="Draft grounded only in verified extraction/enrichment facts; missing facts are requested, not invented.",
    )

    # Step 8: Approval - required whenever a reply would go out. No auto-send path exists anywhere in this system.
    if classification.category == "LLM_UNCLASSIFIED":
        # Fail-safe: an LLM error/timeout on an ambiguous email must never be
        # treated as "nothing to do". Force a human review gate even though
        # response.required is False (no reply is drafted for this category).
        approval = ApprovalStatus(required=True, status="pending_manual_review")
        approval_reason = (
            "LLM classification failed or timed out on an ambiguous email; held for manual review "
            "as a precaution - no reply drafted, no CRM/status change made."
        )
    else:
        approval = ApprovalStatus(
            required=response.required,
            status="pending" if response.required else "not_applicable",
        )
        approval_reason = "All outbound replies require human admin approval before sending."
    audit_log = log_event(audit_log, "approval", email["id"], approval.__dict__, reason=approval_reason)

    return ProcessingResult(
        id=email["id"],
        classification=classification,
        extraction=extraction,
        crm_match=crm_match,
        recommended_action=action.recommended_action,
        owner=owner,
        response=response,
        approval=approval,
        audit_log=audit_log,
    )


def apply_contact_corrections(results, emails_by_id):
    """
    Batch-level pass (mirrors find_duplicate_email_clusters below): consolidates
    emails that find_contact_corrections() recognises as the same opportunity,
    so exactly one reply goes out - using the newer, explicitly-corrected
    contact info - while the original value stays visible in each email's
    audit trail instead of being silently overwritten. Still requires human
    approval before that one reply is sent (approval on the later email is
    left untouched here), and never touches CRM directly - this only changes
    which action/response is *recommended*.
    """
    by_id = {r.id: r for r in results}
    corrections = find_contact_corrections(results, emails_by_id)

    for correction in corrections:
        earlier_id, later_id = correction.email_ids
        earlier = by_id[earlier_id]
        later = by_id[later_id]

        # The earlier enquiry is superseded by the correction - no separate
        # reply goes out for it (the later email's reply covers it), and
        # since there's nothing left to approve for it, approval is not
        # applicable rather than left dangling on "pending".
        earlier.recommended_action = "superseded_by_contact_correction"
        earlier.response = ResponseDraft(
            required=False, draft=None, confidence=1.0, grounded_sources=earlier.response.grounded_sources,
        )
        earlier.approval = ApprovalStatus(required=False, status="not_applicable")
        earlier.audit_log = log_event(
            earlier.audit_log, "contact_correction", earlier_id,
            {"superseded_by": later_id, "history": [h.__dict__ for h in correction.history]},
            reason=correction.reason,
        )

        # The later enquiry carries the single reply and the corrected
        # contact info - the original value isn't discarded, it's recorded
        # in this same audit entry's history. Approval stays exactly as
        # process_email() already set it (still required before sending).
        later.recommended_action = "resolve_contact_correction_then_reply"
        later.extraction.phone = ExtractionField(
            value=correction.preferred_phone, confidence=0.95, source=f"correction_stated_in_{later_id}",
        )
        later.audit_log = log_event(
            later.audit_log, "contact_correction", later_id,
            {
                "merged_with": earlier_id,
                "preferred_phone": correction.preferred_phone,
                "preferred_email": correction.preferred_email,
                "history": [h.__dict__ for h in correction.history],
            },
            reason=correction.reason,
        )

    return results, corrections


def find_duplicate_email_clusters(results):
    """Group processed emails that resolve to the same (possibly duplicated) CRM entity."""
    clusters = {}
    for r in results:
        cm = r.crm_match
        if not cm.record_id:
            continue
        key = tuple(sorted(set([cm.record_id] + cm.duplicate_records)))
        clusters.setdefault(key, []).append(r.id)
    return {k: v for k, v in clusters.items() if len(v) > 1}


def main():
    with open(DATA_PATH, encoding="utf-8") as f:
        emails = json.load(f)

    results = [process_email(email) for email in emails]
    emails_by_id = {e["id"]: e for e in emails}
    results, corrections = apply_contact_corrections(results, emails_by_id)

    print("=== Processing Summary ===")
    for r in results:
        print(f"{r.id:5} | {r.classification.category:22} | CRM:{r.crm_match.status:15} | Action: {r.recommended_action:32} | Owner: {r.owner}")

    clusters = find_duplicate_email_clusters(results)
    if clusters:
        print("\n=== Likely Duplicate / Related Enquiries ===")
        for record_ids, email_ids in clusters.items():
            print(f"CRM records {record_ids} <- emails {email_ids}")

    if corrections:
        print("\n=== Contact Corrections Detected (same opportunity) ===")
        for c in corrections:
            print(
                f"{c.email_ids[0]} -> {c.email_ids[1]}: preferred phone {c.preferred_phone}, "
                f"preferred email {c.preferred_email} (original values kept in audit_log history)"
            )

    write_audit_log(results, path="audit.log")
    print("\nFull audit trail written to audit.log")


if __name__ == "__main__":
    main()
