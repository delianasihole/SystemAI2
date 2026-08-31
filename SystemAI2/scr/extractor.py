import re
from typing import List
from scr.models import ExtractionField, ExtractionResult
from scr.reference_data import load_crm

PHONE_PATTERN = r"\b0\d{3}[- ]?\d{3}[- ]?\d{3}\b"

# Specific, self-declared correction phrasing only - broad enough to catch
# real corrections (see E009 -> E010 in data/emails.json), narrow enough that
# an unrelated email from the same domain won't accidentally trip it. Domain
# match alone is never treated as proof two emails are the same opportunity;
# this is the second of three required signals (see scr/correlator.py).
CORRECTION_PHRASES = [
    "correcting my number", "correcting the number", "correcting my details",
    "please correct", "correction:", "not the number i gave",
    "please use this number going forward", "please use this email address going forward",
    "please use this contact going forward", "supersedes my previous",
]


def find_all_phone_numbers(text: str) -> List[str]:
    """All phone-like numbers mentioned in text, in the order they appear - used
    by the correlator to check whether a 'correction' email restates a value
    already seen from an earlier email (signal 3), not just the first match."""
    return re.findall(PHONE_PATTERN, text)


def contains_correction_language(text: str) -> bool:
    text_l = text.lower()
    return any(phrase in text_l for phrase in CORRECTION_PHRASES)

# Cities that appear in this fictional dataset, mapped to a region label.
# Small fixed vocabulary is deliberate: it keeps location extraction
# deterministic and auditable instead of guessing from free text.
AU_LOCATIONS = {
    "truganina": "Melbourne VIC",
    "dandenong": "Melbourne VIC",
    "epping": "Melbourne VIC",
    "melbourne": "Melbourne VIC",
    "geelong": "Geelong VIC",
    "ballarat": "Ballarat VIC",
    "sydney": "Sydney NSW",
    "newcastle": "Newcastle NSW",
}

SERVICE_KEYWORDS = [
    ("solar", "Solar"),
    ("battery", "Battery"),
    ("batteries", "Battery"),
    ("led", "LED"),
    ("lighting", "LED"),
    ("energy efficiency", "Energy Efficiency"),
    ("installation", "Installation"),
    ("inverter", "Installation"),
]

INTENT_KEYWORDS = [
    ("quote", "commercial_enquiry"),
    ("proposal", "commercial_enquiry"),
    ("consider", "commercial_enquiry"),
    ("invoice", "invoice_dispute"),
    ("does not match", "invoice_dispute"),
    ("reconcil", "invoice_dispute"),
    ("harmonic", "technical_question"),
    ("specification", "technical_question"),
    ("thd", "technical_question"),
    ("crew", "logistics_confirmation"),
    ("confirm", "logistics_confirmation"),
    ("availability", "logistics_confirmation"),
    ("internship", "recruitment"),
    ("application", "recruitment"),
    ("cv", "recruitment"),
    ("sync failed", "system_alert"),
    ("error", "system_alert"),
    ("cryptocurrency", "suspicious"),
]

# Phrases that indicate a blocker/missing precondition. Surfaced rather than
# silently dropped, so downstream drafts don't promise something that can't
# proceed yet (e.g. a quote when the landlord hasn't approved roof works).
BLOCKER_PHRASES = [
    "has not yet agreed", "not yet agreed", "do not have", "no current fixture schedule",
    "no electricity invoice supplied", "have not agreed",
]


def _parse_from_header(from_header: str):
    from_header = (from_header or "").strip()
    m = re.match(r"^(.*?)<([^>]+)>$", from_header)
    if m:
        name = m.group(1).strip().strip('"') or None
        email = m.group(2).strip()
        return name, email
    if re.match(r"^[\w.+-]+@[\w.-]+$", from_header):
        return None, from_header
    return None, None


def _find_matched_crm_row(email_value):
    if not email_value:
        return None
    for row in load_crm():
        if row["email"] and row["email"].lower() == email_value.lower():
            return row
    return None


def extract_fields(email: dict) -> ExtractionResult:
    subject = email.get("subject", "")
    body = email.get("body", "")
    from_header = email.get("from", "")
    text = f"{subject}\n{body}"
    text_l = text.lower()

    header_name, header_email = _parse_from_header(from_header)

    body_email_match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", body)
    email_value = header_email or (body_email_match.group(0) if body_email_match else None)
    email_field = ExtractionField(
        value=email_value,
        confidence=1.0 if header_email else (0.7 if body_email_match else 0.0),
        source="from_header" if header_email else ("email_body" if body_email_match else None),
    )

    phone_match = re.search(PHONE_PATTERN, text)
    phone_field = ExtractionField(
        value=phone_match.group(0) if phone_match else None,
        confidence=0.9 if phone_match else 0.0,
        source="email_body" if phone_match else None,
    )

    matched_row = _find_matched_crm_row(email_value)

    # Contact name: prefer verified CRM record over the (unverified) header display name.
    if matched_row:
        name_field = ExtractionField(value=matched_row["contact"], confidence=0.95, source="crm.csv")
    elif header_name:
        name_field = ExtractionField(value=header_name, confidence=0.6, source="from_header")
    else:
        name_field = ExtractionField(value=None, confidence=0.0, source=None)

    # Company: prefer CRM record, then an explicit "Company: X" line, then a loose text match.
    if matched_row:
        company_field = ExtractionField(value=matched_row["company"], confidence=0.95, source="crm.csv")
    else:
        co_match = re.search(r"company:\s*(.+)", text, re.IGNORECASE)
        if co_match:
            company_field = ExtractionField(value=co_match.group(1).strip(), confidence=0.6, source="email_body")
        else:
            company_field = ExtractionField(value=None, confidence=0.0, source=None)
            for row in load_crm():
                if row["company"].lower() in text_l:
                    company_field = ExtractionField(value=row["company"], confidence=0.85, source="email_body")
                    break

    # Location: CRM record is authoritative (company HQ); otherwise scan for known cities.
    location_field = ExtractionField(value=None, confidence=0.0, source=None)
    if matched_row and matched_row.get("location"):
        location_field = ExtractionField(value=matched_row["location"], confidence=0.85, source="crm.csv")
    else:
        for city, region in AU_LOCATIONS.items():
            if city in text_l:
                location_field = ExtractionField(value=region, confidence=0.7, source="email_body")
                break

    # Service: CRM record is authoritative; otherwise the first keyword found in the text.
    service_field = ExtractionField(value=None, confidence=0.0, source=None)
    if matched_row and matched_row.get("service"):
        service_field = ExtractionField(value=matched_row["service"], confidence=0.85, source="crm.csv")
    else:
        for kw, label in SERVICE_KEYWORDS:
            if kw in text_l:
                service_field = ExtractionField(value=label, confidence=0.65, source="email_body")
                break

    intent_field = ExtractionField(value=None, confidence=0.0, source=None)
    for kw, label in INTENT_KEYWORDS:
        if kw in text_l:
            intent_field = ExtractionField(value=label, confidence=0.7, source="email_body")
            break

    facts = {}
    blockers = [phrase for phrase in BLOCKER_PHRASES if phrase in text_l]
    if blockers:
        facts["blockers"] = blockers

    evidence = []
    if header_email:
        evidence.append("from_header")
    if matched_row:
        evidence.append("crm.csv")

    return ExtractionResult(
        contact_name=name_field,
        email=email_field,
        phone=phone_field,
        company=company_field,
        location=location_field,
        service=service_field,
        intent=intent_field,
        evidence=evidence,
        facts=facts,
    )
