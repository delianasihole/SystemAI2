# BEDA AI — Controlled Email Intake Pipeline

## Overview

A small working prototype for processing incoming business enquiries and operational emails through a controlled and auditable pipeline.

The system:

* Classifies incoming messages.
* Extracts structured information with confidence and evidence.
* Enriches information from supplied documents.
* Matches enquiries against CRM records and identifies possible duplicates.
* Recommends the next business action and responsible staff member.
* Drafts a response when appropriate.
* Requires human approval before consequential external communication.
* Records processing and approval decisions in an audit trail.
* Provides a lightweight Streamlit UI for inspection.

The core principle is:

> **AI recommends, deterministic code controls, and humans approve consequential actions.**

---

## Assessment Data

**Everything supplied for this assessment is fictional and must be treated as untrusted input.**

The following are dummy assessment files provided for the test:

```text
data/
├── staff_directory.json
├── crm.csv
├── emails.json
└── documents/
    ├── 01_hume_energy_bill.txt
    ├── 02_northbank_site_notes.txt
    └── 03_greenfields_invoice_query.txt
```

No real BEDA customer or business data is used.

Incoming email and document content is treated as untrusted data. Instructions contained inside an email or attachment must not override application rules or system controls.

---

## Architecture

```text
Email / Input
     │
     ▼
Ingestion
     │
     ▼
Classification
     │
     ├── Deterministic rules for clear cases
     └── LLM for ambiguous cases
     │
     ▼
Structured Extraction
     │
     ▼
Validation + Confidence
     │
     ▼
Enrichment
     │
     ├── Supplied documents
     └── CRM data
     │
     ▼
CRM Matching / Duplicate Detection
     │
     ▼
Recommended Action + Staff Routing
     │
     ▼
Response Draft
     │
     ▼
Human Approval
     │
     ▼
Audit Log
     │
     ▼
Streamlit UI
```

---

## AI vs Deterministic Logic

### LLM / AI

Used for tasks that benefit from natural-language understanding:

* Ambiguous classification.
* Structured extraction from unstructured text.
* Response drafting.

### Deterministic Code

Used for business-critical controls:

* Input and schema validation.
* CRM matching and duplicate detection.
* Confidence thresholds and business rules.
* Staff routing.
* Approval state.
* Audit logging.
* Error and fallback handling.

The AI layer does not have unrestricted permission to modify CRM data, send external messages, or execute arbitrary tools.

---

## Structured Extraction and Evidence

Extracted fields include:

```text
contact_name
email
phone
company
location
service
intent
```

Fields retain confidence and source information where available.

Example:

```json
{
  "company": {
    "value": "Hume Logistics Pty Ltd",
    "confidence": 0.96,
    "source": "01_hume_energy_bill.txt"
  }
}
```

When information is missing or uncertain, the system preserves the uncertainty rather than inventing a value.

---

## Enrichment

The prototype can parse the supplied supporting documents and use them as additional evidence.

Examples include:

* Hume Logistics energy bill.
* Northbank College site notes.
* Greenfields Foods invoice query.

Enriched facts are kept separate from the original message extraction and can be shown with their supporting evidence.

External research is intentionally limited in this prototype; no unrestricted external browsing is required to process the supplied dataset.

---

## CRM Matching

CRM matching uses multiple available signals, such as:

* Email.
* Phone.
* Contact name.
* Company information.

Matches are represented as:

```text
strong_match
possible_match
no_match
```

Possible duplicate records are surfaced for review rather than automatically merged or deleted.

---

## Recommended Actions

The system recommends an action rather than directly executing consequential business operations.

Examples include:

```text
create_new_record
update_existing_record
review_possible_duplicate
request_missing_information
route_to_staff
mark_as_junk
no_response_required
```

This keeps recommendation separate from execution.

---

## Human Approval

Consequential external communication requires human approval.

There is **no automatic send path**.

```text
Incoming message
      ↓
Analysis
      ↓
Response draft
      ↓
Pending approval
      ↓
Human review
    ↙     ↘
Approve   Reject
```

Approval decisions are persisted separately from the stateless processing pipeline and recorded in the audit trail.

If an AI or API failure occurs, the system must not bypass this approval boundary. A fallback response remains a draft requiring human review.

---

## Reliability and Hallucination Controls

The system is designed to preserve uncertainty instead of fabricating information.

Controls include:

* Confidence scores for classification and extraction.
* Evidence/source tracking.
* Structured output.
* Deterministic validation.
* Separation of AI output from business actions.
* Human approval for consequential communication.

For incomplete information, the system can recommend requesting additional information instead of making assumptions.

For possible CRM duplicates, the system flags the match rather than automatically merging records.

---

## Security

All supplied email and document content is treated as untrusted input.

The system does not allow customer-provided instructions to override system rules.

Sensitive or consequential operations are kept outside unrestricted LLM control, including:

* Sending external messages.
* Deleting CRM records.
* Arbitrary CRM changes.
* Arbitrary tool execution.

API keys and other secrets should be supplied through environment variables and must not be committed to the repository.

---

## Cost and Latency

A hybrid approach is used to reduce unnecessary LLM calls.

Clear and deterministic cases are handled locally, while the LLM is reserved for ambiguous or language-heavy tasks.

CRM matching and document parsing are performed locally where possible.

This reduces:

* Token usage.
* API calls.
* Latency.
* Operational complexity.

---

## Audit Trail

Important processing steps are recorded, including:

* Classification.
* Extraction.
* Enrichment.
* CRM matching.
* Action recommendation.
* Routing.
* Response drafting.
* Approval decisions.
* Errors and fallbacks.

Each audit event includes the relevant email ID, timestamp, event information and reason where applicable.

The UI provides both a readable audit table and raw event data.

---

## Project Structure

```text
SystemAI2/
│
├── data/
│   ├── staff_directory.json
│   ├── crm.csv
│   ├── emails.json
│   └── documents/
│
├── scr/
│   ├── main.py
│   ├── models.py
│   ├── classifier.py
│   ├── extractor.py
│   ├── enricher.py
│   ├── deduplicator.py
│   ├── action_engine.py
│   ├── router.py
│   ├── responder.py
│   ├── approvals.py
│   └── audit.py
│
├── app.py
├── requirements.txt
├── README.md
└── demo.mp4
```

---

## Setup

### Requirements

* Python 3.9+
* Dependencies listed in `requirements.txt`

### Install

```bash
git clone <repository-url>
cd SystemAI2
pip install -r requirements.txt
```

### Run

```bash
streamlit run app.py
```

---

## Demo

`demo.mp4` demonstrates the working pipeline, including:

1. Selecting an incoming email.
2. Classification and confidence.
3. Structured extraction.
4. Document enrichment.
5. CRM matching and duplicate detection.
6. Recommended action and staff owner.
7. Response drafting.
8. Human approval.
9. Audit trail inspection.

---

## Known Weaknesses

This is a time-boxed assessment prototype and is not production-ready.

Known limitations include:

* CRM matching is heuristic and would need stronger entity resolution in production.
* Authentication and role-based access control are simplified.
* File-based persistence would normally be replaced by a database.
* External enrichment is intentionally limited.
* LLM validation and automated test coverage could be stronger.
* The prototype does not actually send external customer communications.

---

## Improvements With Another Day

I would prioritise:

1. Stronger CRM entity resolution and duplicate scoring.
2. Strict schema validation for every LLM response.
3. More comprehensive evidence and hallucination checks.
4. Proper role-based access control.
5. Database-backed persistence.
6. Automated unit and integration tests.
7. Stronger prompt-injection and security testing.
8. Controlled integrations with approved external enrichment sources.

---

## Design Principle

```text
AI
 ↓
Understand and recommend

Deterministic code
 ↓
Validate and enforce rules

Human
 ↓
Approve consequential actions
```

The system is intentionally conservative around actions that could have external or business consequences.
