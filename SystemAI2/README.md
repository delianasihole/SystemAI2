# BEDA Test 2 - Controlled Build

Deterministic email intake pipeline: classify -> extract -> enrich -> match/dedupe CRM -> recommend action -> route -> draft response -> require human approval -> audit.

## Setup

```bash
pip install -r requirements.txt   # only needed for the Streamlit UI; the CLI has no dependencies
```

Data lives in `data/` (`emails.json`, `crm.csv`, `staff_directory.json`, `documents/`) - untrusted fictional input, already in the repo.

## Running it

**CLI** (no dependencies, processes all 12 emails, writes a full audit trail):

```bash
python -m scr.main
```

Prints a per-email summary table, flags likely duplicate/related enquiries across emails, and writes `audit.log` (one JSON line per pipeline step, with a `reason` field explaining the decision).

**UI** (inspect one email at a time):

```bash
streamlit run app.py
```

## Architecture

```
email --> classify_email --> extract_fields --> enrich (attachment) --> deduplicate (CRM)
                                                                              |
                                            approval <-- response draft <-- route_action <-- recommend_action
```

- **`classifier.py`** - ordered keyword rules assign one of: `commercial_enquiry`, `invoice_dispute`, `technical_query`, `logistics_confirmation`, `recruitment`, `partner_engagement`, `internal_alert`, `spam`, or falls back to `general_enquiry` (confidence 0.5) when nothing matches, rather than guessing.
- **`extractor.py`** - pulls contact/email/phone/company/location/service/intent. Where the sender's email matches a `crm.csv` row, that verified record wins over anything inferred from free text (higher confidence, `source: "crm.csv"`); otherwise fields fall back to regex/keyword extraction from the email itself, or stay `None` with confidence `0.0` - never invented.
- **`enricher.py`** - the only module that reads `documents/`, and only the file named in that specific email's `attachment` field (not a blind scan of the whole folder). Parses stated numbers (consumption kWh, bill total, PO vs invoice amount) into `extraction.facts` with regex, and computes `invoice_variance` directly from the source numbers rather than trusting any number claimed in the email body itself.
- **`deduplicator.py`** - matches the email to a CRM record (email exact -> phone exact -> name/company similarity), and separately flags other CRM rows that look like the same company under a different spelling (`duplicate_records`), e.g. `C001 Hume Logistics Pty Ltd` vs `C002 Hume Logistic`. `main.py` then clusters emails across the whole batch that resolve to the same (possibly duplicated) CRM entity - this is how `E001`/`E002` get flagged as the same enquiry arriving through two channels.
- **`action_engine.py`** - category + CRM match state -> a specific next action (e.g. `create_new_crm_record`, `escalate_invoice_reconciliation`, `resolve_duplicate_crm_record_then_reply`).
- **`router.py`** - owner is resolved live from `staff_directory.json`'s `"owns"` free-text field per category, not a hardcoded name -> if the directory changes, routing follows without a code change.
- **`responder.py`** - drafts are template text filled only with values already sitting in `extraction`/`extraction.facts`. If a fact wasn't verified (e.g. no consumption figure), the draft asks for it instead of stating a number. Nothing here calls an LLM or a template engine that could be steered by the email content.
- **`audit.py`** / `main.py` - every step appends `{event, details, reason}` to a per-email log; `write_audit_log` flattens all of them to `audit.log`.

### Security / trust boundary

- Email `subject`/`body`/`attachment` content is **data, never instructions**. Nothing in the pipeline executes or forwards text found in an email as a command - e.g. `E004`'s "Reply now for cryptocurrency payment instructions" is just spam-classified text; it has zero effect on control flow.
- No outbound network/API calls anywhere in the pipeline (deliberately no LLM integration - see "AI tools" below) - the only I/O is reading the local `data/` files and writing `audit.log`.
- Every reply requires human approval before it could be sent (`ApprovalStatus`); the system only ever *drafts*, there is no send path. This directly preserves the correction from the Test 1 review: replies always require admin approval, with no automatic-fallback-template exception.
- `approval.required` is tied to whether a reply actually exists (`response.required`) - internal-only actions (`mark_as_spam`, `escalate_system_issue`) aren't given a meaningless "pending approval" state.

## AI tools used

Built with Claude Code (Claude Sonnet 5) as a pair-programmer: scaffolding, the extraction/enrichment/dedup logic, and this README were all written and iterated on interactively, then run against the real dataset to catch bugs (e.g. a CRM CSV column mismatch, a `staff_directory.json` shape mismatch, and a same-row iteration bug in the deduplicator that made E002 match the wrong CRM record). No LLM API is called at runtime by the pipeline itself - classification/extraction/routing are all deterministic rules, which is a design choice, not a limitation (see below).

## Known weaknesses / what I'd improve with another day

- **No cross-email correction handling**: `E009`→`E010` corrects a phone number and asks that a different email address be used going forward. The system currently treats each email independently rather than recognising `E010` as an amendment to `E009`. A day-two version would look for "correcting", "re:", and matching company/contact across recent emails and apply corrections instead of just falling back to `general_enquiry`.
- **Single dominant service per email**: `extractor.py` returns the first matched service keyword (e.g. `E001` mentions solar, battery *and* lighting, but only "Solar" - from the CRM record - is captured). A day-two version would return a list of services with independent confidence rather than one field.
- **Location is CRM-company-level, not project-site-level**: for `E008`, the extracted location is Solara Installations' Sydney NSW HQ, not the Ballarat project site actually mentioned in the email. Worth a separate `project_location` field.
- **Small, fixed vocabularies**: city names and service keywords are hardcoded lists sized for this dataset. Fine for a 3-hour scoped build; would not generalise to new regions/services without maintenance, and is called out explicitly rather than disguised as broader coverage.
- **No automated tests**: given the timebox, verification was done by running `python -m scr.main` and spot-checking specific emails (`E001`, `E003`, `E012`, `E004`, `E011`, `E010`) by hand. A day-two version would add `pytest` cases per module, especially the CRM-matching priority order (the exact class of bug that showed up here: an email match on one row must win over a phone match on a different row within the same pass).
- **No LLM-assisted extraction**: this was a deliberate scope decision - deterministic rules are fully explainable, need no API key, make no external calls, and can't be prompt-injected via email content. The tradeoff is lower recall on phrasing the fixed keyword lists don't anticipate. A day-two version could add an LLM as an *optional, sandboxed* second pass that only ever proposes values back into the same `ExtractionField(confidence, source)` shape - never free text injected straight into a response - so a human still reviews anything the deterministic layer didn't already handle with confidence.
- **CRM duplicate merge is detect-only**: `duplicate_records` correctly flags `C001`/`C002` as likely the same company, and routes those emails to `resolve_duplicate_crm_record_then_reply`, but there's no actual merge workflow - that's intentionally left as a human (Ali Pratama, per the CRM/systems ownership routing) decision rather than something automated.

## Screen recording / architecture walkthrough

Not included in this delivery - to be recorded separately per the submission requirements (`python -m scr.main` for the CLI walkthrough, `streamlit run app.py` for the per-email UI).
