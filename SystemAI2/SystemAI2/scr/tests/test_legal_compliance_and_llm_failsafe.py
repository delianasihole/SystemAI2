"""
Covers the two requirements changes:

1. `legal_compliance` is a deterministic, highest-priority category checked
   before any LLM classification is even attempted.
2. An LLM error/timeout on a genuinely ambiguous email never guesses a
   category: it returns LLM_UNCLASSIFIED, holds the email for manual review,
   suppresses the reply, and never recommends a CRM-touching action.

Run with (no dependencies required, matching this project's zero-dependency
CLI - see README):

    python -m unittest scr.tests.test_legal_compliance_and_llm_failsafe -v
"""
import unittest

from scr.classifier import classify_email
from scr.action_engine import recommend_action
from scr.responder import generate_response
from scr.extractor import extract_fields
from scr.main import process_email
from scr.models import CRMMatch


class ExplodingLLMClient:
    """Stands in for a real LLM client whose call times out / errors."""

    def classify(self, text: str):
        raise TimeoutError("LLM request timed out")


# Ambiguous by construction: matches none of classifier.RULES, so it's the
# kind of email that would only ever be resolved by an LLM call.
AMBIGUOUS_EMAIL = {
    "id": "TEST-AMBIGUOUS-001",
    "subject": "Following up",
    "body": "Hi, just checking in on where things are at. Let me know when you get a chance.",
    "from": "someone@example.com",
}


class TestLegalComplianceCategory(unittest.TestCase):
    def test_legal_keyword_short_circuits_before_llm_would_ever_run(self):
        # llm_client would raise if it were ever consulted - proving the
        # deterministic legal_compliance rule wins first.
        result = classify_email(
            "Cease and desist notice",
            "Our solicitor has issued a cease and desist regarding your recent solar marketing claims.",
            llm_client=ExplodingLLMClient(),
        )
        self.assertEqual(result.category, "legal_compliance")
        self.assertEqual(result.method, "deterministic")

    def test_legal_compliance_outranks_other_keyword_categories(self):
        # Contains both an invoice_dispute keyword and a legal_compliance
        # keyword; legal_compliance must win because it's checked first.
        result = classify_email(
            "Invoice dispute becomes a compliance matter",
            "This invoice does not match our purchase order and is now escalated as a regulatory breach.",
        )
        self.assertEqual(result.category, "legal_compliance")

    def test_legal_compliance_action_and_reply_never_touch_crm(self):
        action = recommend_action(
            classify_email("Legal notice", "Please see the attached legal notice regarding a compliance breach."),
            extract_fields(AMBIGUOUS_EMAIL),
            CRMMatch(record_id=None, confidence=0.0, status="no_match"),
        )
        self.assertEqual(action.recommended_action, "escalate_legal_compliance_review")
        self.assertNotIn("crm_record", action.recommended_action)


class TestLLMFailSafePath(unittest.TestCase):
    """The ambiguous fixture forces the LLM path, then forces it to fail."""

    def test_llm_timeout_returns_unclassified_not_a_guess(self):
        classification = classify_email(
            AMBIGUOUS_EMAIL["subject"], AMBIGUOUS_EMAIL["body"], llm_client=ExplodingLLMClient()
        )
        self.assertEqual(classification.category, "LLM_UNCLASSIFIED")
        self.assertEqual(classification.method, "llm_error")
        self.assertEqual(classification.confidence, 0.0)

    def test_llm_failure_holds_for_manual_review_and_blocks_crm_and_reply(self):
        classification = classify_email(
            AMBIGUOUS_EMAIL["subject"], AMBIGUOUS_EMAIL["body"], llm_client=ExplodingLLMClient()
        )
        extraction = extract_fields(AMBIGUOUS_EMAIL)
        crm_match = CRMMatch(record_id=None, confidence=0.0, status="no_match")
        action = recommend_action(classification, extraction, crm_match)

        # No CRM-creating/updating action may ever result from a failed LLM call.
        self.assertEqual(action.recommended_action, "hold_for_manual_review")
        self.assertNotIn("crm_record", action.recommended_action)

        # No external reply may be drafted or sent.
        self.assertFalse(action.response_required)
        response = generate_response(classification, extraction, action)
        self.assertFalse(response.required)
        self.assertIsNone(response.draft)

    def test_without_an_llm_client_the_old_safe_default_is_unchanged(self):
        # The LLM hook is opt-in: with no client configured, ambiguous text
        # still falls back to the pre-existing deterministic fallback.
        classification = classify_email(AMBIGUOUS_EMAIL["subject"], AMBIGUOUS_EMAIL["body"])
        self.assertEqual(classification.category, "general_enquiry")
        self.assertEqual(classification.method, "deterministic_fallback")


class TestPipelineFailSafe(unittest.TestCase):
    """End-to-end: the full process_email() pipeline with a failing LLM client."""

    def test_process_email_holds_for_manual_review_on_llm_failure(self):
        result = process_email(AMBIGUOUS_EMAIL, llm_client=ExplodingLLMClient())

        self.assertEqual(result.classification.category, "LLM_UNCLASSIFIED")
        self.assertTrue(result.approval.required)
        self.assertEqual(result.approval.status, "pending_manual_review")
        self.assertFalse(result.response.required)
        self.assertIsNone(result.response.draft)
        self.assertNotIn("crm_record", result.recommended_action)


if __name__ == "__main__":
    unittest.main()
