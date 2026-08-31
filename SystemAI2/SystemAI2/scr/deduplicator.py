from difflib import SequenceMatcher
from scr.models import CRMMatch, ExtractionResult
from scr.reference_data import load_crm


LEGAL_SUFFIXES = [" pty ltd", " pty. ltd.", " ltd", " limited", " inc", " llc"]


def normalize_company(name: str) -> str:
    n = name.lower().strip()
    for suffix in LEGAL_SUFFIXES:
        if n.endswith(suffix):
            n = n[: -len(suffix)].strip()
    return n


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def company_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize_company(a), normalize_company(b)).ratio()


def deduplicate(extraction: ExtractionResult) -> CRMMatch:
    crm_rows = load_crm()

    match = None
    # Separate passes per signal - an email match on one row must win even if
    # a different row happens to share a phone number (see C001 vs C002).
    for row in crm_rows:
        if extraction.email.value and row["email"] and extraction.email.value.lower() == row["email"].lower():
            match = (row, 0.95, "strong_match")
            break

    if not match:
        for row in crm_rows:
            if extraction.phone.value and row["phone"] and extraction.phone.value == row["phone"]:
                match = (row, 0.9, "strong_match")
                break

    if not match:
        for row in crm_rows:
            if extraction.contact_name.value and similarity(extraction.contact_name.value, row["contact"]) > 0.8:
                match = (row, 0.75, "possible_match")
                break
            if extraction.company.value and company_similarity(extraction.company.value, row["company"]) > 0.75:
                match = (row, 0.75, "possible_match")
                break

    if not match:
        return CRMMatch(record_id=None, confidence=0.0, status="no_match")

    row, confidence, status = match
    # Flag other CRM rows that look like the same company under a different
    # spelling/record (e.g. "Hume Logistics Pty Ltd" vs "Hume Logistic") -
    # these are candidates for merging, not just a match on this one email.
    duplicate_records = [
        r["id"] for r in crm_rows
        if r["id"] != row["id"] and company_similarity(r["company"], row["company"]) > 0.8
    ]

    return CRMMatch(record_id=row["id"], confidence=confidence, status=status, duplicate_records=duplicate_records)
