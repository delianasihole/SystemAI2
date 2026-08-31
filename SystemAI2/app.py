import json
import pandas as pd
import streamlit as st
from scr.main import process_email
from scr.approvals import load_approvals, save_approval
from scr.audit import append_event

DATA_PATH = "data/emails.json"
STAFF_PATH = "data/staff_directory.json"

CATEGORY_COLORS = {
    "commercial_enquiry": "blue",
    "invoice_dispute": "orange",
    "technical_query": "violet",
    "logistics_confirmation": "green",
    "recruitment": "blue",
    "partner_engagement": "green",
    "internal_alert": "gray",
    "spam": "red",
    "general_enquiry": "gray",
}

CRM_STATUS_COLORS = {
    "strong_match": "green",
    "possible_match": "orange",
    "no_match": "gray",
}

st.set_page_config(page_title="Email Intake Pipeline", layout="wide", page_icon="📧")

st.title("📧 Email Intake Pipeline")
st.caption("Classify → Extract → Enrich → Match CRM → Recommend action → Draft → Approve → Audit")

with open(DATA_PATH, encoding="utf-8") as f:
    emails = json.load(f)

with open(STAFF_PATH, encoding="utf-8") as f:
    staff = json.load(f)
staff_names = [s["name"] for s in staff]

email_ids = [e["id"] for e in emails]
selected_id = st.sidebar.selectbox("Pilih Email ID", email_ids)
selected_email = next(e for e in emails if e["id"] == selected_id)
st.sidebar.caption("Setiap email diproses lewat pipeline yang sama secara independen.")

approver = st.sidebar.selectbox("Approver", staff_names)

result = process_email(selected_email)

# Approve/reject decisions are persisted separately (data/approvals.json) since
# process_email itself is a stateless, deterministic pipeline run.
approvals = load_approvals()
decision = approvals.get(selected_id)
if result.approval.required and decision:
    result.approval.status = decision["status"]

# --- Email preview -----------------------------------------------------
with st.container(border=True):
    st.markdown(f"**From:** {selected_email['from']}")
    st.markdown(f"**Subject:** {selected_email['subject']}")
    st.markdown("**Body:**")
    st.markdown(f"> {selected_email['body']}")
    if selected_email.get("attachment"):
        st.caption(f"📎 Attachment: {selected_email['attachment']}")

st.divider()

# --- At-a-glance summary -----------------------------------------------
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("**Classification**")
    st.badge(
        result.classification.category.replace("_", " ").title(),
        color=CATEGORY_COLORS.get(result.classification.category, "gray"),
    )
    st.caption(f"method: {result.classification.method}")
    st.progress(result.classification.confidence, text=f"Confidence {result.classification.confidence:.0%}")

with col2:
    st.markdown("**CRM Match**")
    st.badge(
        result.crm_match.status.replace("_", " ").title(),
        color=CRM_STATUS_COLORS.get(result.crm_match.status, "gray"),
    )
    st.caption(f"record: {result.crm_match.record_id or '—'}")
    st.progress(result.crm_match.confidence, text=f"Confidence {result.crm_match.confidence:.0%}")
    if result.crm_match.duplicate_records:
        st.warning(f"⚠️ Kemungkinan duplikat dengan: {', '.join(result.crm_match.duplicate_records)}")

with col3:
    st.markdown("**Recommended Action**")
    st.badge(result.recommended_action.replace("_", " ").title(), color="blue")
    st.caption(f"owner: **{result.owner}**")
    if result.approval.required:
        badge_color, badge_icon = {
            "pending": ("orange", "⏳"),
            "approved": ("green", "✅"),
            "rejected": ("red", "❌"),
        }[result.approval.status]
        st.badge(f"Approval: {result.approval.status}", color=badge_color, icon=badge_icon)
    else:
        st.badge("No approval needed", color="gray")

st.divider()

# --- Extraction ----------------------------------------------------------
st.subheader("🔍 Extraction")

field_rows = []
for field_name in ["contact_name", "email", "phone", "company", "location", "service", "intent"]:
    field = getattr(result.extraction, field_name)
    field_rows.append({
        "Field": field_name.replace("_", " ").title(),
        "Value": field.value or "—",
        "Confidence": field.confidence,
        "Source": field.source or "—",
    })

st.dataframe(
    pd.DataFrame(field_rows),
    hide_index=True,
    width="stretch",
    column_config={
        "Confidence": st.column_config.ProgressColumn("Confidence", min_value=0, max_value=1, format="%.0f%%"),
    },
)

if result.extraction.evidence:
    st.caption("Evidence: " + " · ".join(result.extraction.evidence))

if result.extraction.facts:
    st.markdown("**Enriched facts** _(parsed from the linked attachment)_")
    fact_rows = [
        {"Fact": k.replace("_", " ").title(), "Value": ", ".join(v) if isinstance(v, list) else v}
        for k, v in result.extraction.facts.items()
    ]
    st.dataframe(pd.DataFrame(fact_rows), hide_index=True, width="stretch")

st.divider()

# --- Response draft --------------------------------------------------------
st.subheader("✉️ Response Draft")
if result.response.draft:
    st.text_area("Draft", result.response.draft, height=180, label_visibility="collapsed")
    sources = ", ".join(result.response.grounded_sources) or "—"
    st.caption(f"Confidence: {result.response.confidence:.0%} · grounded in: {sources}")
else:
    st.info("Tidak ada tanggapan yang diperlukan untuk kategori ini.")

# --- Approval ---------------------------------------------------------------
st.subheader("✅ Approval")
if result.approval.required:
    status = result.approval.status

    if status == "pending":
        st.warning("Status: **pending** — menunggu persetujuan admin sebelum dikirim. Tidak ada jalur auto-send.")
        col_approve, col_reject = st.columns(2)
        if col_approve.button("✅ Approve", key=f"approve_{selected_id}", type="primary", width="stretch"):
            save_approval(selected_id, "approved", decided_by=approver)
            append_event(
                "approval_decision", selected_id, {"status": "approved", "decided_by": approver},
                reason=f"{approver} approved the response draft via the UI.",
            )
            st.rerun()
        if col_reject.button("❌ Reject", key=f"reject_{selected_id}", width="stretch"):
            save_approval(selected_id, "rejected", decided_by=approver)
            append_event(
                "approval_decision", selected_id, {"status": "rejected", "decided_by": approver},
                reason=f"{approver} rejected the response draft via the UI.",
            )
            st.rerun()
    else:
        if status == "approved":
            st.success(f"Status: **approved** ✅ — oleh **{decision['decided_by']}** ({decision['timestamp']})")
        else:
            st.error(f"Status: **rejected** ❌ — oleh **{decision['decided_by']}** ({decision['timestamp']})")
        if st.button("↩️ Reset ke pending", key=f"reset_{selected_id}"):
            save_approval(selected_id, "pending", decided_by=approver)
            append_event(
                "approval_decision", selected_id, {"status": "pending", "decided_by": approver},
                reason=f"{approver} reset the approval decision back to pending via the UI.",
            )
            st.rerun()
else:
    st.success("Tidak ada tindakan eksternal yang perlu disetujui untuk email ini.")

st.divider()

# --- Audit log ----------------------------------------------------------
st.subheader("📝 Audit Log")
audit_rows = [
    {"Step": e["event"].replace("_", " ").title(), "Reason": e["reason"], "Timestamp": e["timestamp"]}
    for e in result.audit_log
]
st.dataframe(pd.DataFrame(audit_rows), hide_index=True, width="stretch")

with st.expander("Lihat detail mentah (raw JSON per step)"):
    st.json(result.audit_log)
