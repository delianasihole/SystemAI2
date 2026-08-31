"""
Covers scr/correlator.py and main.apply_contact_corrections():

1. E009/E010 (data/emails.json) are recognised as the same opportunity.
2. The original and corrected values are both kept, tagged with their
   source email id, instead of one silently overwriting the other.
3. The newer, explicitly-stated correction becomes the preferred contact info.
4. A human approval gate is still required before the (single, consolidated)
   reply goes out - nothing here writes to CRM or sends anything automatically.

Also proves the three-signal rule isn't just "same domain": two emails
sharing a domain and even the same phone number, but with no explicit
correction language, must NOT be merged.

Run with:
    python -m unittest scr.tests.test_contact_correlation -v
"""
import json
import unittest

from scr.main import process_email, apply_contact_corrections
from scr.correlator import find_contact_corrections

DATA_PATH = "data/emails.json"


class TestRealE009E010Correction(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(DATA_PATH, encoding="utf-8") as f:
            cls.emails = json.load(f)
        cls.emails_by_id = {e["id"]: e for e in cls.emails}
        results = [process_email(e) for e in cls.emails]
        cls.results, cls.corrections = apply_contact_corrections(results, cls.emails_by_id)
        cls.by_id = {r.id: r for r in cls.results}

    def test_e009_and_e010_recognised_as_same_opportunity(self):
        self.assertEqual(len(self.corrections), 1)
        self.assertEqual(self.corrections[0].email_ids, ["E009", "E010"])

    def test_original_and_corrected_values_both_kept_with_source(self):
        history = self.corrections[0].history
        phone_history = [h for h in history if h.field == "phone"]
        self.assertEqual(len(phone_history), 2)

        original = next(h for h in phone_history if not h.is_correction)
        corrected = next(h for h in phone_history if h.is_correction)
        self.assertEqual((original.value, original.source_email_id), ("0411 999 120", "E009"))
        self.assertEqual((corrected.value, corrected.source_email_id), ("0411 999 102", "E010"))

        # Nothing overwritten: audit_log on both emails carries the full history.
        e009_entry = next(a for a in self.by_id["E009"].audit_log if a["event"] == "contact_correction")
        e010_entry = next(a for a in self.by_id["E010"].audit_log if a["event"] == "contact_correction")
        self.assertEqual(len(e009_entry["details"]["history"]), 4)
        self.assertEqual(len(e010_entry["details"]["history"]), 4)

    def test_newer_correction_is_preferred(self):
        self.assertEqual(self.corrections[0].preferred_phone, "0411 999 102")
        self.assertEqual(self.corrections[0].preferred_email, "sam@harbourcoldstores.example")
        # The consolidated email's own extraction is updated to the preferred value.
        self.assertEqual(self.by_id["E010"].extraction.phone.value, "0411 999 102")

    def test_human_approval_still_required_before_the_reply(self):
        e010 = self.by_id["E010"]
        self.assertEqual(e010.recommended_action, "resolve_contact_correction_then_reply")
        self.assertTrue(e010.response.required)
        self.assertEqual(e010.approval.required, True)
        self.assertEqual(e010.approval.status, "pending")

    def test_superseded_email_gets_no_separate_reply_and_no_crm_action(self):
        e009 = self.by_id["E009"]
        self.assertEqual(e009.recommended_action, "superseded_by_contact_correction")
        self.assertNotIn("crm_record", e009.recommended_action)
        self.assertFalse(e009.response.required)
        self.assertIsNone(e009.response.draft)


class TestDomainAloneIsNotEnough(unittest.TestCase):
    """Same domain AND the same phone number mentioned in both, but with no
    explicit correction language - must NOT be merged."""

    def test_no_correction_language_means_no_merge(self):
        fake_emails = [
            {
                "id": "X1", "from": "alice@acme.example", "subject": "Quote request",
                "body": "Hi, can we get a quote for solar? Call me on 0400 555 111.",
            },
            {
                "id": "X2", "from": "bob@acme.example", "subject": "Unrelated batteries question",
                "body": "Separately, do your batteries come with warranty? My number is 0400 555 111 too.",
            },
        ]
        results = [process_email(e) for e in fake_emails]
        emails_by_id = {e["id"]: e for e in fake_emails}
        corrections = find_contact_corrections(results, emails_by_id)
        self.assertEqual(corrections, [])


if __name__ == "__main__":
    unittest.main()
