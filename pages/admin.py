"""Admin: approve or delete student reviews, manage admins, Ask AI usage, regenerate AI summaries."""
import streamlit as st

from lib import db, ui

conn = ui.conn()
me = st.session_state.get("email", "")
ui.setup("Admin", "Visible to admins only.")
if not db.is_admin(conn, me):
    st.info("Admins only.")
    st.stop()

st.subheader("Student reviews")
subs = db.submissions(conn)
if subs.empty:
    st.caption("No student reviews yet.")
for r in subs.itertuples():
    with st.container(border=True):
        st.markdown(f"**{r.company}**, {r.job_profile} · {r.department} {r.batch_year} · R{r.id} · "
                    + ("approved" if r.approved else ":orange[waiting]"))
        st.caption((r.selection or "")[:300])
        a, b, c = st.columns([1, 1, 4])
        if not r.approved and a.button("Approve", key=f"ok{r.id}", type="primary"):
            db.moderate(conn, r.id, True)
            st.rerun()
        if b.button("Delete", key=f"del{r.id}"):
            db.moderate(conn, r.id, False)
            st.rerun()
        if c.button("Open", key=f"open{r.id}", type="tertiary"):
            ui.open_review(r.id)

st.subheader("Admins")
admins = db.admins(conn)
for e in admins:
    a, b = st.columns([4, 1], vertical_alignment="center")
    a.text(e + (" (you)" if e == me else ""))
    if b.button("Remove", key=f"rm{e}", disabled=len(admins) == 1, help="The last admin cannot be removed."):
        db.set_admin(conn, e, False)
        st.rerun()
with st.form("add_admin", clear_on_submit=True, border=False):
    new = st.text_input("Add admin", placeholder="name@nitk.edu.in").strip()
    if st.form_submit_button("Add") and "@" in new:
        db.set_admin(conn, new, True)
        st.rerun()

st.subheader("Ask AI usage today")
st.dataframe(db.usage_today(conn), hide_index=True)

st.subheader("AI summaries")
if st.button("Regenerate all overviews", help="Marks every company and department summary for regeneration."):
    db.reset_overviews(conn)
    st.success("Done. Each overview regenerates on its next view.")
