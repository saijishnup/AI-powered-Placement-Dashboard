"""Review detail: header meta -> AI review summary -> written sections. Name/email never shown here."""
import html
import re
from datetime import datetime

import streamlit as st

from lib import db, qa, ui

SECTIONS = [("selection", "Selection procedure"), ("preparation", "Way of preparation"),
            ("experience", "Overall experience"), ("advice", "Advice for the company"), ("tips", "General tips")]
# Characters markdown/Streamlit would interpret (links, emphasis, math, emoji shortcodes) -> HTML entities.
_MD = {c: f"&#{ord(c)};" for c in "[]()*_`#>|~$\\:!{}"}
LINKEDIN_RE = re.compile(r"^https://(www\.)?linkedin\.com/\S+$")


def safe_text(text):
    """User-written text -> inert HTML: escaped, markdown chars neutralised, one <p> per non-empty line
    (even paragraph spacing whether the writer used single or blank-line breaks).
    Kept on one line so the whole thing is a single raw-HTML block (markdown is not parsed inside)."""
    s = html.escape(text.strip())
    s = "".join(_MD.get(ch, ch) for ch in s)
    return "".join(f"<p>{ln.strip()}</p>" for ln in s.replace("\r\n", "\n").split("\n") if ln.strip())


def back():
    st.switch_page("pages/dashboard.py")


raw = st.query_params.get("id")
row = db.get_review(ui.conn(), int(raw)) if raw and raw.isdigit() else None

if row is None:
    ui.setup("Review not found")
    st.info("This review link is broken or the review was removed. Pick one from the dashboard table instead.")
    if st.button("Back to dashboard", type="primary"):
        back()
    st.stop()

e = lambda v: html.escape(str(v)) if v not in (None, "") else "-"  # noqa: E731

head, btn = st.columns([5, 1], vertical_alignment="center")
with head:
    ui.setup(f"{row['company']}, {row['job_profile'] or 'Review'}")
with btn:
    if st.button("Back"):
        back()

# ---------- header meta ----------
try:
    posted = datetime.fromisoformat(row["created_at"][:10]).strftime("%b %Y")
except (TypeError, ValueError):
    posted = "-"
tags = "".join(f'<span class="pd-tag">{e(t)}</span>' for t in
               ((row["type"] or "").title(), (row["outcome"] or "").title(), row["tier"]) if t)
tags += f'<span class="pd-muted pd-num">R{row["id"]} &middot; Posted {posted}</span>'

link = row.get("linkedin") or ""
linkedin = (f'<a href="{html.escape(link, quote=True)}" target="_blank" rel="noopener noreferrer nofollow">'
            f'View profile</a>' if LINKEDIN_RE.match(link) else "-")
cgpa = f"{row['cgpa']:.2f}" if row["cgpa"] is not None else "-"
meta = [("Company", e(row["company"])), ("LinkedIn", linkedin), ("Department", e(row["department"])),
        ("Batch", f'<span class="pd-num">{e(row["batch_year"])}</span>'),
        ("CGPA", f'<span class="pd-num">{cgpa}</span>'), ("Location", e(row["job_location"])),
        ("Job profile", e(row["job_profile"])),
        ("CTC" if row["type"] == "placement" else "Stipend",
         f'<span class="pd-num">{e(ui.pay_text(row["pay"], row["type"]))}</span>'),
        ("Rounds", f'<span class="pd-num">{e(row["rounds"])}</span>')]
grid = "".join(f'<div><div class="k">{k}</div><div class="v">{v}</div></div>' for k, v in meta)

with st.container(border=True):
    st.markdown(f'<div class="pd-tags">{tags}</div><div class="pd-meta">{grid}</div>', unsafe_allow_html=True)

# ---------- AI review summary (between header meta and sections) ----------
with st.spinner("Summarising this review..."):
    bullets, note = qa.review_summary(ui.conn(), row)  # stored in reviews.ai_summary after the first call
ui.ai_card("AI review summary", [html.escape(b) for b in bullets or [note]],
           "Auto summary" + (f" · {note.lower()}" if bullets else ""))

# ---------- written sections ----------
for col, label in SECTIONS:
    text = (row.get(col) or "").strip()
    if not text:
        continue
    with st.container(border=True):
        st.markdown(f'<section class="pd-section"><h3>{label}</h3>{safe_text(text)}</section>', unsafe_allow_html=True)
