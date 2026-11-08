"""Shared UI: CSS, chart styling, sidebar filters, small HTML blocks.
Pages call setup() first. Look matches docs/mockup.html."""
import html
import re

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib import db

ACCENT = "#7C5CFF"  # chart category colours live in .streamlit/config.toml (one list per theme)
DEPARTMENTS = ["CSE", "IT", "ECE", "EEE", "Mechanical", "Civil", "Chemical",
               "Metallurgical and Materials", "Mining", "AI", "Computational and Data Science"]
TIERS = ["Super Dream", "Dream", "Normal", "University"]
TAGS = ["DSA", "OA", "system design", "OOPs", "DBMS", "OS", "CN", "projects", "resume", "HR",
        "puzzles", "aptitude", "core", "ML", "PPO", "referral"]
MONO = '"Geist Mono", ui-monospace, monospace'


CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Geist+Mono:wght@400;500;600&display=swap');
/* Colours derive from the live text colour, so one rule set fits light and dark with no theme detection. */
:root { --pd-text: currentColor; --pd-muted: color-mix(in srgb, currentColor 62%, transparent);
        --pd-border: color-mix(in srgb, currentColor 14%, transparent); --pd-soft: rgba(124,92,255,.12);
        --pd-line: rgba(124,92,255,.5); --pd-ink: color-mix(in srgb, #7C5CFF 72%, currentColor); }
/* Spacing scale: 4 / 8 / 12 / 16 / 24 / 32 px. Cards: 16px padding (Streamlit border box), 16px gap between blocks. */
.block-container { padding-top: 48px; padding-bottom: 64px; max-width: 1320px; }
/* style/script holders render nothing but still take a flex gap each: drop them from layout */
[data-testid="stElementContainer"]:has(style), [data-testid="stElementContainer"]:has(.stHtml) { display: none; }
/* Streamlit pulls every markdown/caption block up by -1rem to cancel a trailing <p> margin. Raw-HTML blocks
   have no such margin, so the pull ate 16px of card padding (text touching the bottom border). Zero both. */
[data-testid="stMarkdownContainer"], [data-testid="stCaptionContainer"] { margin-bottom: 0 !important; }
[data-testid="stMarkdownContainer"] > :last-child, [data-testid="stCaptionContainer"] > :last-child { margin-bottom: 0; }
[data-testid="stHeader"] { height: 40px; }
.stSkillsNudge { display: none; }  /* Streamlit dev nudge toast: not for app users */
@media (min-width: 761px) { [data-testid="stHeader"] { background: transparent; } }

/* sidebar: boxes start at 16px, list text (brand, nav, account) at 24px */
[data-testid="stSidebarContent"] { padding: 0 16px; }
[data-testid="stSidebarHeader"] { padding: 20px 0 12px; height: auto; }
[data-testid="stSidebarHeader"]::before { content: "Placement Dashboard"; order: 1; font-weight: 800; font-size: 16px;
    letter-spacing: -.01em; color: var(--pd-text); padding-left: 8px; margin-right: auto; }
[data-testid="stSidebarNavItems"] { padding: 0; }
[data-testid="stSidebarNavItems"] li { margin: 0 0 2px; }
[data-testid="stSidebarNavLink"] { margin: 0; height: 36px; padding: 0 8px; border-radius: 4px; }
[data-testid="stSidebarNavLinkContainer"] { height: auto; }
[data-testid="stSidebarNavSeparator"] { margin: 8px 0; }
[data-testid="stSidebarUserContent"] { padding: 4px 0 64px; }
[data-testid="stSidebarUserContent"] [data-testid="stVerticalBlock"] { gap: 16px; }
.pd-account { padding: 0 8px; }
.pd-account .pd-muted { line-height: 1.5; }
.pd-user { font-size: 13px; color: var(--pd-text); word-break: break-all; line-height: 1.5; }
[data-testid="stSidebar"] [data-testid="stElementContainer"]:has(.pd-account) + [data-testid="stElementContainer"] { margin-top: -12px; }
/* Sign out: same 8px inset and 13px size as the email line above it */
.st-key-signout button { padding: 0 8px !important; min-height: 28px; height: 28px; justify-content: flex-start; }
.st-key-signout button p { font-size: 13px; color: var(--pd-muted); }
.st-key-signout button:hover p { color: var(--pd-text); }
/* login: centred column, pushed down a little */
.st-key-login { margin-top: 10vh; }
[data-testid="stSidebar"] h3 { font-size: 16px; padding: 16px 0 0; border-top: 1px solid var(--pd-border); }

/* page head: title, then caption 8px below; 24px to the first content block */
h1 { line-height: 1.2 !important; letter-spacing: -0.01em; padding: 0 !important; }
[data-testid="stMain"] [data-testid="stElementContainer"]:has(h1) + [data-testid="stElementContainer"]:has([data-testid="stCaptionContainer"]) { margin-top: -16px; }
[data-testid="stMain"] [data-testid="stElementContainer"]:has(h1) + [data-testid="stElementContainer"]:has([data-testid="stCaptionContainer"]) p { font-size: 14px; }
[data-testid="stMain"] [data-testid="stElementContainer"]:has(h1), [data-testid="stMain"] [data-testid="stElementContainer"]:has(h1) + [data-testid="stElementContainer"]:has([data-testid="stCaptionContainer"]) { margin-bottom: 8px; }

[data-testid="stColumn"] [data-testid="stElementContainer"]:has(h1) { margin-bottom: 0; }
[data-testid="stHorizontalBlock"]:has(h1) { margin-bottom: 8px; }

/* type */
.pd-num { font-family: {mono}; font-variant-numeric: tabular-nums; }
.pd-muted { color: var(--pd-muted); font-size: 12px; }
p.pd-muted { font-size: 14px; margin: 0; }

/* metrics: mono numbers; 2 per row on phones */
[data-testid="stMetricValue"] { font-family: {mono}; font-variant-numeric: tabular-nums; font-size: 24px; }
@media (max-width: 760px) {
  [data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) { flex-wrap: wrap; gap: 12px; }
  [data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) > [data-testid="stColumn"] { flex: 1 1 calc(50% - 6px) !important; min-width: calc(50% - 6px) !important; }
}

/* equal-height cards in a row: opt in with st.container(border=True, key="eq_...") */
[data-testid="stLayoutWrapper"]:has(> [class*="st-key-eq_"]), [class*="st-key-eq_"] { height: 100%; }

/* AI summary card: tinted header strip + 1px violet outline + icon */
.pd-ai { border: 1px solid var(--pd-line); border-radius: 6px; overflow: hidden; }
.pd-ai-head { display: flex; align-items: center; gap: 12px; padding: 12px 20px; background: var(--pd-soft);
              border-bottom: 1px solid var(--pd-line); flex-wrap: wrap; }
.pd-ai-head b { font-size: 14px; font-weight: 700; color: var(--pd-text); }
.pd-ai-head span { margin-left: auto; font-size: 12px; color: var(--pd-muted); }
.pd-ai-ico { width: 28px; height: 28px; border-radius: 4px; border: 1px solid var(--pd-border); display: grid;
             place-items: center; color: var(--pd-ink); flex: none; }
.pd-ai-ico svg { width: 16px; height: 16px; stroke: currentColor; fill: none; stroke-width: 1.6; }
.pd-ai ul { margin: 0; padding: 16px 20px 16px 40px; display: flex; flex-direction: column; gap: 8px; max-width: 86ch; }
.pd-ai li { margin: 0; padding: 0; line-height: 1.6; }
@media (max-width: 600px) { .pd-ai-head span { margin-left: 40px; width: 100%; } .pd-ai ul { padding: 12px 16px 12px 36px; } }
.pd-cite { font-size: 12px; font-weight: 500; padding: 0 4px; border-radius: 3px; background: var(--pd-soft);
           color: var(--pd-ink) !important; text-decoration: none !important; }

/* tags / chips: flex gap, no trailing margins */
.pd-tags { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
button[data-variant="pills"] { border-radius: 4px !important; }  /* st.pills ignores theme radius; 4px like every chip */
.pd-tag { display: inline-block; font-size: 12px; line-height: 20px; padding: 0 8px; border-radius: 4px;
          border: 1px solid color-mix(in srgb, currentColor 24%, transparent); color: var(--pd-muted); white-space: nowrap; }

/* review detail */
.pd-meta { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; border-top: 1px solid var(--pd-border);
           margin-top: 16px; padding-top: 16px; }
.pd-meta .k { font-size: 12px; color: var(--pd-muted); line-height: 1.5; }
.pd-meta .v { font-weight: 500; color: var(--pd-text); line-height: 1.5; }
@media (max-width: 760px) { .pd-meta { grid-template-columns: 1fr 1fr; } }
.pd-section h3 { font-size: 16px; font-weight: 700; line-height: 1.4; margin: 0 0 8px; padding: 0; }
.pd-section p { margin: 0 0 12px; max-width: 72ch; line-height: 1.6; }
.pd-section p:last-child { margin-bottom: 0; }

@media (min-width: 641px) { [data-testid="stColumn"] { min-width: 0; } }  /* desktop only: phones must keep column stacking */
</style>
"""

AI_ICON = ('<svg viewBox="0 0 24 24"><path d="M4 6h16M4 12h10M4 18h7"/><path d="M17 15l1.5 3 3 1.5-3 1.5L17 24"/></svg>')


def apply_css():
    st.markdown(CSS.replace("{mono}", MONO), unsafe_allow_html=True)


def setup(title, caption=None):
    """Call at top of every page: page title (CSS is injected once by app.py)."""
    st.title(title)
    if caption:
        st.caption(caption)


@st.cache_resource
def conn():
    return db.connect()


# ---------- filters (persist across pages: widget keys are copied into plain session keys) ----------
DEFAULTS = {"type": "All", "departments": [], "batches": [], "tiers": [], "company_q": "", "cgpa": (5.0, 10.0)}


def _keep(name):
    st.session_state["flt_" + name] = st.session_state["_w_" + name]


def _clear():
    for k, v in DEFAULTS.items():
        st.session_state["flt_" + k] = v
        st.session_state.pop("_w_" + k, None)  # widgets rebuild from the defaults


def filters_sidebar():
    """Render shared sidebar filters; return the filters dict used by lib.db."""
    for k, v in DEFAULTS.items():
        st.session_state.setdefault("flt_" + k, v)
    s = st.session_state
    with st.sidebar:
        st.subheader("Filters")
        active = any(s["flt_" + k] != v for k, v in DEFAULTS.items())
        st.button("Clear filters", type="tertiary", key="clear_filters", on_click=_clear, disabled=not active)
        st.segmented_control("Type", ["All", "Internship", "Placement"], key="_w_type", default=s.flt_type,
                             on_change=_keep, args=("type",))
        st.multiselect("Department", DEPARTMENTS, default=s.flt_departments, key="_w_departments",
                       on_change=_keep, args=("departments",), placeholder="All departments")
        st.multiselect("Batch", [2024, 2025, 2026, 2027], default=s.flt_batches, key="_w_batches",
                       on_change=_keep, args=("batches",), placeholder="All batches")
        st.multiselect("Company tier", TIERS, default=s.flt_tiers, key="_w_tiers",
                       on_change=_keep, args=("tiers",), placeholder="All tiers")
        st.text_input("Company", value=s.flt_company_q, key="_w_company_q", on_change=_keep,
                      args=("company_q",), placeholder="Search company")
        st.slider("CGPA", 5.0, 10.0, value=s.flt_cgpa, step=0.1, key="_w_cgpa", on_change=_keep, args=("cgpa",))
    t = s.flt_type or "All"
    return {"type": None if t == "All" else t.lower(), "departments": s.flt_departments, "batches": s.flt_batches,
            "tiers": s.flt_tiers, "company_q": s.flt_company_q.strip(),
            "cgpa": None if tuple(s.flt_cgpa) == (5.0, 10.0) else tuple(s.flt_cgpa)}


# ---------- HTML blocks ----------
def ai_card(title, bullets_html, meta):
    """bullets_html: list of already-safe HTML strings (escape review text before adding cite links)."""
    items = "".join(f"<li>{b}</li>" for b in bullets_html)
    st.markdown(f'<div class="pd-ai"><div class="pd-ai-head"><div class="pd-ai-ico">{AI_ICON}</div>'
                f'<b>{html.escape(title)}</b><span>{html.escape(meta)}</span></div><ul>{items}</ul></div>',
                unsafe_allow_html=True)


def tags_html(tags):
    spans = "".join(f'<span class="pd-tag">{html.escape(t)}</span>' for t in tags)
    return f'<div class="pd-tags">{spans}</div>' if spans else ""


def cite_html(text):
    """Escape model text, then turn [R3] and [S] (the stats block) into citation chips."""
    text = re.sub(r"\[R(\d+)\]", r'<span class="pd-cite">R\1</span>', html.escape(text or ""))
    return text.replace("[S]", '<span class="pd-cite">Stats</span>')


def cited_reviews(ids, key, cols=("cite", "company", "job_profile", "selection")):
    """Cited reviews in citation order, as a clickable table with a one-line preview."""
    if not ids:
        return
    t = pd.DataFrame([{"cite": rid, **db.get_review(conn(), i)}
                      for rid, i in sorted(ids.items(), key=lambda kv: int(kv[0][1:]))])
    st.markdown("**Cited reviews** · click a row to open")
    review_table(t[list(cols)], t.id, key)


def open_review(review_id):
    """Navigate in-app (keeps session/login; an <a href> would reload and drop the fake login)."""
    st.switch_page("pages/review.py", query_params={"id": int(review_id)})


def pay_text(pay, rtype):
    if pay is None or pay != pay:  # None or NaN
        return "-"
    return f"{pay:.1f} LPA" if rtype == "placement" else f"{pay:.0f}k / month"


def med(s, nd=1, how="median"):
    s = s.dropna()
    return "-" if s.empty else f"{getattr(s, how)():.{nd}f}"


def metrics(cells, per_row=4):
    for i in range(0, len(cells), per_row):
        for col, (label, value) in zip(st.columns(per_row), cells[i:i + per_row]):
            col.metric(label, value, border=True)


def tag_counts(df):
    t = df.tags.dropna().str.split(",").explode().str.strip()
    return t[t != ""].value_counts()


LABELS = {"cite": "Cite", "company": "Company", "job_profile": "Role", "department": "Dept",
          "batch_year": "Batch", "type": "Type", "selection": "Preview"}


def review_table(table, ids, key, **kw):
    """Click a row to open that review. ids: review ids aligned with table rows."""
    kw.setdefault("column_config", {"Batch": st.column_config.NumberColumn(format="%d"),
                                    "Preview": st.column_config.TextColumn(width="large")})
    if "selection" in table:  # long free text -> one-line preview of the selection procedure
        table = table.assign(selection=table.selection.fillna("").str.replace(r"\s+", " ", regex=True).str[:160])
    ev = st.dataframe(table.rename(columns=LABELS), hide_index=True, width="stretch", on_select="rerun",
                      selection_mode="single-row", key=key, **kw)
    if ev.selection.rows:
        open_review(ids.iloc[ev.selection.rows[0]])


# ---------- charts ----------
CHART = {"displayModeBar": False}

def style_fig(fig, height=320):
    """Size, legend and mono numeric ticks. Colours, grid and fonts come from Streamlit's chart theme (config.toml)."""
    fig.update_layout(height=height, margin=dict(l=8, r=8, t=8, b=8), bargap=0.35,
                      legend=dict(orientation="h", y=1.08, x=0, title=None), hoverlabel=dict(font=dict(family=MONO)))
    for axis, update in (("x", fig.update_xaxes), ("y", fig.update_yaxes)):
        # Geist Mono only for numeric axes; category labels (company, dept, tag) stay in the body font.
        vals = next((getattr(tr, axis) for tr in fig.data if getattr(tr, axis, None) is not None), None)
        if not (vals is not None and len(vals) and isinstance(list(vals)[0], str)):
            update(tickfont=dict(family=MONO, size=11))
        update(title=None)
    return fig


def hbar(counts, height=320):
    """Shared horizontal accent bar (largest on top, mono value labels, no x grid). Used by dashboard + departments."""
    counts = counts.sort_values()
    fig = go.Figure(go.Bar(x=counts.values, y=counts.index.astype(str), orientation="h", marker_color=ACCENT,
                           text=counts.values, textposition="outside", cliponaxis=False,
                           textfont=dict(family=MONO, color="#8A8F9C"), hovertemplate="%{y}: %{x}<extra></extra>"))
    fig = style_fig(fig, height)
    fig.update_xaxes(showgrid=False, showticklabels=False)
    fig.update_layout(bargap=0.45)
    return fig
