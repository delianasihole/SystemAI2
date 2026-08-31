from typing import Dict, List, Optional

from scr.extractor import contains_correction_language, find_all_phone_numbers
from scr.models import ContactFieldHistory, OpportunityCorrection, ProcessingResult


def _sender_domain(email_address: Optional[str]) -> Optional[str]:
    if not email_address or "@" not in email_address:
        return None
    return email_address.split("@", 1)[1].lower()


def find_contact_corrections(
    results: List[ProcessingResult], emails_by_id: Dict[str, dict]
) -> List[OpportunityCorrection]:
    """
    Links two emails as the same opportunity ONLY when all three hold:
      1. same sender domain,
      2. the later email uses explicit, self-declared correction language, and
      3. a phone number that later email restates in its own text matches a
         value already extracted from an earlier email under that domain.

    Domain match alone is not enough (colleagues at the same company email
    about unrelated things) and correction language alone is not enough
    (it says nothing about which earlier email, if any, it corrects) - only
    the combination, verified against an actual restated value, counts as
    proof rather than a guess.
    """
    corrections: List[OpportunityCorrection] = []

    by_domain: Dict[str, List[ProcessingResult]] = {}
    for r in results:
        domain = _sender_domain(r.extraction.email.value)
        if domain:
            by_domain.setdefault(domain, []).append(r)

    for domain, group in by_domain.items():
        if len(group) < 2:
            continue

        for later in group:
            later_email = emails_by_id[later.id]
            later_text = f"{later_email.get('subject', '')} {later_email.get('body', '')}"
            if not contains_correction_language(later_text):
                continue

            mentioned_phones = find_all_phone_numbers(later_text)

            for earlier in group:
                if earlier.id == later.id:
                    continue

                earlier_phone = earlier.extraction.phone.value
                if not earlier_phone:
                    continue

                old_matches = [p for p in mentioned_phones if p.lower() == earlier_phone.lower()]
                if not old_matches:
                    continue  # signal 3 not met - nothing ties this pair together

                # The preferred value is whichever mentioned number is NOT the
                # old one - found this way (not just "whatever extractor.py
                # picked first") so a correction reads correctly regardless of
                # whether the email states the new or old number first.
                new_candidates = [p for p in mentioned_phones if p.lower() != earlier_phone.lower()]
                preferred_phone = new_candidates[0] if new_candidates else later.extraction.phone.value

                history = [
                    ContactFieldHistory("phone", earlier_phone, earlier.id, is_correction=False),
                    ContactFieldHistory("phone", preferred_phone, later.id, is_correction=True),
                    ContactFieldHistory("email", earlier.extraction.email.value, earlier.id, is_correction=False),
                    ContactFieldHistory("email", later.extraction.email.value, later.id, is_correction=True),
                ]
                corrections.append(OpportunityCorrection(
                    email_ids=[earlier.id, later.id],
                    history=history,
                    preferred_phone=preferred_phone,
                    preferred_email=later.extraction.email.value,
                    reason=(
                        f"{later.id} uses explicit correction language and restates {earlier.id}'s phone "
                        f"({earlier_phone}) verbatim while correcting it to {preferred_phone} - same sender "
                        f"domain ({domain}). Treating {later.id}'s contact info as preferred; {earlier.id}'s "
                        f"original value is kept in history, not discarded."
                    ),
                ))

    return corrections
