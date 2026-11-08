"""Submit review: grouped form -> validate -> insert (marks company + department overview dirty)."""
import re

import streamlit as st

from lib import db, ui

LINKEDIN_RE = re.compile(r"^https://(www\.)?linkedin\.com/\S+$")
OTHER = "Other (type below)"
BATCHES = [2024, 2025, 2026, 2027, 2028]
MIN_SELECTION = 40
TEXTS = [("selection", "Selection procedure", "Round 1, round 2, what was asked in each"),
         ("preparation", "Way of preparation", "Resources, sheets, how long"),
         ("experience", "Overall experience", "Interviewers, process, work"),
         ("advice", "Advice for the company", "What this company looks for"),
         ("tips", "General tips", "Anything for the season in general")]
KEYS = ["name", "department", "batch", "cgpa", "linkedin", "consent", "outcome", "company", "company_other",
        "job_profile", "location", "pay", "rounds", "tags"] + [k for k, *_ in TEXTS]

conn = ui.conn()
s = st.session_state
errs = s.get("sub_errs", {})

ui.setup("Submit review", "Takes about 10 minutes")

email = s.get("email")
if not email:
    st.info("Sign in with your NITK email to submit a review.")
    st.stop()

if "sub_new_id" in s:
    st.success("Review posted. It is on the dashboard now.")
    if st.button("View your review", type="primary"):
        ui.open_review(s.pop("sub_new_id"))


def section(title, hint):
    st.subheader(title)
    st.caption(hint)


# Type sits outside the form so the pay label can follow it (form widgets do not rerun on change).
with st.container(border=True):
    rtype = st.segmented_control("This review is for", ["Internship", "Placement"], default="Internship",
                                 key="sub_type", required=True).lower()
placement = rtype == "placement"
companies = db.list_companies(conn)["name"].tolist()

with st.form("submit_review", border=False, enter_to_submit=False):
    with st.container(border=True):
        section("About you", "Name, email and LinkedIn are never sent to the AI.")
        a, b = st.columns(2)
        with a:
            st.text_input("Full name", key="sub_name", max_chars=80)
            st.selectbox("Batch (graduation year)", BATCHES, index=None, placeholder="Select batch", key="sub_batch")
        with b:
            st.selectbox("Department", ui.DEPARTMENTS, index=None, placeholder="Select department",
                         key="sub_department")
            st.number_input("CGPA", 0.0, 10.0, value=None, step=0.01, format="%.2f", key="sub_cgpa",
                            placeholder="e.g. 8.43", help="At the time of the offer")
        st.text_input("LinkedIn URL (optional)", key="sub_linkedin", placeholder="https://www.linkedin.com/in/your-handle")
        st.checkbox("Show my email to logged-in students", key="sub_consent",
                    help=f"Shares {email} on the dashboard so juniors can reach out.")

    with st.container(border=True):
        section("The offer", "Structured fields power the charts and filters.")
        a, b = st.columns(2)
        with a:
            st.segmented_control("Outcome", ["Company", "University"], default="Company", key="sub_outcome")
            st.selectbox("Company", companies + [OTHER], index=None, placeholder="Select company", key="sub_company")
            st.text_input("Job profile", key="sub_job_profile", max_chars=100, placeholder="e.g. SDE Intern")
            st.number_input("Number of rounds", 1, 8, value=None, step=1, key="sub_rounds", placeholder="1 to 8")
        with b:
            st.text_input("Company name, if not listed", key="sub_company_other", max_chars=80,
                          placeholder="Only when you pick Other")
            st.text_input("Location", key="sub_location", max_chars=80, placeholder="e.g. Bengaluru")
            if placement:
                st.number_input("CTC (LPA)", 0.0, 200.0, value=None, step=0.5, format="%.1f", key="sub_pay",
                                placeholder="e.g. 18.5")
            else:
                st.number_input("Stipend (k / month)", 0.0, 1000.0, value=None, step=5.0, format="%.0f",
                                key="sub_pay", placeholder="e.g. 85")
        st.pills("Topic tags", ui.TAGS, selection_mode="multi", key="sub_tags")

    with st.container(border=True):
        section("Experience", "Write like you are telling a junior. Rough is fine.")
        key, label, ph = TEXTS[0]
        st.text_area(label, key=f"sub_{key}", placeholder=ph, height=160, max_chars=5000)
        cols = st.columns(2)
        for i, (key, label, ph) in enumerate(TEXTS[1:]):
            with cols[i % 2]:
                st.text_area(label, key=f"sub_{key}", placeholder=ph, height=130, max_chars=5000)

    if errs:
        st.error("Fix these fields:\n" + "\n".join(f"- {m}" for m in errs.values()))
    sent = st.form_submit_button("Submit review", type="primary")


def validate(v):
    e = {}
    if len(v["name"]) < 2:
        e["name"] = "Enter your name."
    if not v["department"]:
        e["department"] = "Pick your department."
    if not v["batch"]:
        e["batch"] = "Pick your batch."
    if v["cgpa"] is None:
        e["cgpa"] = "Enter your CGPA (0 to 10)."
    if v["linkedin"] and not LINKEDIN_RE.match(v["linkedin"]):
        e["linkedin"] = "Use the full profile link, for example https://www.linkedin.com/in/your-handle"
    if not v["company"]:
        e["company"] = "Pick a company, or Other."
    elif v["company"] == OTHER and len(v["company_other"]) < 2:
        e["company_other"] = "Type the company name."
    if len(v["job_profile"]) < 2:
        e["job_profile"] = "Enter the job profile."
    if v["rounds"] is None:
        e["rounds"] = "Enter the number of rounds."
    if len(v["selection"]) < MIN_SELECTION:
        e["selection"] = f"Describe the rounds in at least {MIN_SELECTION} characters ({len(v['selection'])} now)."
    return e


if sent:
    v = {k: s.get(f"sub_{k}") for k in KEYS}
    for k in ("name", "linkedin", "company_other", "job_profile", "location") + tuple(k for k, *_ in TEXTS):
        v[k] = (v[k] or "").strip()
    s.sub_errs = validate(v)
    if not s.sub_errs:
        outcome = (v["outcome"] or "Company").lower()
        name = v["company"]
        if name == OTHER:  # reuse an existing row if only the casing differs
            name = next((c for c in companies if c.lower() == v["company_other"].lower()), v["company_other"])
        cid = db.company_id(conn, name, tier="University" if outcome == "university" else "Normal")
        new_id = db.insert_review(conn, {
            "company_id": cid, "author_name": v["name"], "author_email": email, "consent": int(bool(v["consent"])),
            "linkedin": v["linkedin"] or None, "department": v["department"], "batch_year": int(v["batch"]),
            "cgpa": round(float(v["cgpa"]), 2), "type": rtype, "outcome": outcome, "job_profile": v["job_profile"],
            "job_location": v["location"] or None, "pay": v["pay"], "rounds": int(v["rounds"]),
            "tags": ",".join(v["tags"] or []), **{k: v[k] or None for k, *_ in TEXTS}, "is_seed": 0})
        for k in KEYS:  # reset the form for the next review
            s.pop(f"sub_{k}", None)
        s.sub_new_id = new_id
    st.rerun()
