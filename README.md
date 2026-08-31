
## Overview
This project is a small working prototype that processes incoming messages:
- Classifies each item into business categories (sales, support, junk, unknown).
- Extracts structured information (sender, email, phone, subject).
- Checks for duplicate records in CRM.
- Recommends next actions (create new record, update existing).
- Drafts a response if needed.
- Requires human approval before any external impactful action.
- Logs all steps in an audit trail.
- Provides simple CLI output for inspection.

## Setup
1. Clone the repository:
   ```bash
   git clone <your_repo_url>
   cd SystemAI_Test2
Install dependencies:

bash
pip install -r requirements.txt
(requirements: Python 3.9+, standard libraries only for this prototype)

Run the system:

bash
python src/main.py
Data
All input data is fictitious and must be treated as untrusted:

data/staff_directory.json

data/crm.csv

data/emails.json

data/documents/*.txt

Architecture
Pipeline:

Code
Input → Classification → Extraction → Deduplication → Action Recommendation → Draft Response → Audit Log → Output
Modules:

classifier.py → keyword/LLM classification

extractor.py → regex-based info extraction

deduplicator.py → CRM duplicate check

responder.py → draft reply templates

audit.py → log actions

main.py → orchestrates pipeline
