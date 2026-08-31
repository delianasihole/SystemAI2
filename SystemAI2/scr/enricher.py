import os
import re
from scr.models import ExtractionResult

DATA_PATH = "data"
DOCS_PATH = os.path.join(DATA_PATH, "documents")

FACT_PATTERNS = {
    "consumption_kwh": re.compile(r"Consumption:\s*([\d,]+)\s*kWh", re.IGNORECASE),
    "max_demand_kw": re.compile(r"Maximum demand:\s*([\d,]+)\s*kW", re.IGNORECASE),
    "bill_amount": re.compile(r"Total bill:\s*\$([\d,]+)", re.IGNORECASE),
    "po_amount": re.compile(r"Approved value:\s*\$([\d,]+)", re.IGNORECASE),
    "invoice_amount": re.compile(r"Invoice \d+:\s*\$([\d,]+)", re.IGNORECASE),
}

BLOCKER_PHRASES = [
    "no current fixture schedule", "no electricity invoice supplied",
]


def _parse_document(content: str) -> dict:
    facts = {}
    for key, pattern in FACT_PATTERNS.items():
        m = pattern.search(content)
        if m:
            facts[key] = m.group(1).replace(",", "")
    return facts


def enrich_with_document(extraction: ExtractionResult, attachment: str) -> ExtractionResult:
    if not attachment:
        return extraction

    filepath = os.path.join(DOCS_PATH, attachment)
    if not os.path.exists(filepath):
        extraction.evidence.append(f"missing_attachment:{attachment}")
        return extraction

    with open(filepath, encoding="utf-8") as f:
        content = f.read()

    facts = _parse_document(content)
    extraction.facts.update(facts)

    if "po_amount" in facts and "invoice_amount" in facts:
        variance = int(facts["invoice_amount"]) - int(facts["po_amount"])
        extraction.facts["invoice_variance"] = f"${variance:,} ex GST"

    content_l = content.lower()
    doc_blockers = [phrase for phrase in BLOCKER_PHRASES if phrase in content_l]
    if doc_blockers:
        extraction.facts["blockers"] = sorted(set(extraction.facts.get("blockers", []) + doc_blockers))

    extraction.evidence.append(attachment)
    return extraction


def enrich(extraction: ExtractionResult, email: dict) -> ExtractionResult:
    return enrich_with_document(extraction, email.get("attachment"))
