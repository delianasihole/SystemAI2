from scr.reference_data import load_staff

# Category -> keywords to look for in each staff member's "owns" description.
# Routing is derived from staff_directory.json at run time rather than
# hardcoded names, so it stays correct if ownership changes.
CATEGORY_OWNER_HINTS = {
    "commercial_enquiry": ["commercial opportunities", "strategic partnerships"],
    "partner_engagement": ["strategic partnerships", "commercial opportunities"],
    "invoice_dispute": ["crm", "systems", "data", "workflows", "infrastructure"],
    "technical_query": ["crm", "systems", "data", "workflows", "infrastructure"],
    "internal_alert": ["crm", "systems", "data", "workflows", "infrastructure"],
    "spam": ["crm", "systems", "data", "workflows", "infrastructure"],
    "logistics_confirmation": ["scheduling", "administration", "logistics", "operational"],
    "general_enquiry": ["scheduling", "administration", "logistics", "operational"],
    "recruitment": ["marketing", "website", "inbound growth"],
}


def route_action(category: str) -> str:
    hints = CATEGORY_OWNER_HINTS.get(category, [])
    staff = load_staff()

    for hint in hints:
        for person in staff:
            if hint in person.get("owns", "").lower():
                return person["name"]

    return "Unassigned"
