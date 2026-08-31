import json
from scr.models import ProcessingResult, ApprovalStatus
from scr.classifier import classify_email
from scr.extractor import extract_fields
from scr.enricher import enrich
from scr.deduplicator import deduplicate
from scr.action_engine import recommend_action
from scr.router import route_action
from scr.responder import generate_response
from scr.audit import log_event, write_audit_log

DATA_PATH = "data/emails.json"


def process_email(email: dict) -> ProcessingResult:
    audit_log = []

    # Step 1: Classification - subject/body content only, never treated as instructions.
    classification = classify_email(email.get("subject", ""), email.get("body", ""))
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
    approval = ApprovalStatus(
        required=response.required,
        status="pending" if response.required else "not_applicable",
    )
    audit_log = log_event(
        audit_log, "approval", email["id"], approval.__dict__,
        reason="All outbound replies require human admin approval before sending.",
    )

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

    print("=== Processing Summary ===")
    for r in results:
        print(f"{r.id:5} | {r.classification.category:22} | CRM:{r.crm_match.status:15} | Action: {r.recommended_action:32} | Owner: {r.owner}")

    clusters = find_duplicate_email_clusters(results)
    if clusters:
        print("\n=== Likely Duplicate / Related Enquiries ===")
        for record_ids, email_ids in clusters.items():
            print(f"CRM records {record_ids} <- emails {email_ids}")

    write_audit_log(results, path="audit.log")
    print("\nFull audit trail written to audit.log")


if __name__ == "__main__":
    main()
