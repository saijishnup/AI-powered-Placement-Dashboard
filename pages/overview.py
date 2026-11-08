"""Company and department overviews: two nav pages, one file. Stats, cached AI summary, recent reviews."""
import html

import plotly.express as px
import streamlit as st

from lib import db, qa, ui


def ai_summary(scope, key, df):
    """Cached in SQLite by lib.qa.overview: a clean cache costs zero LLM calls."""
    with st.spinner("Summarising reviews..."):
        bullets, ids, meta = qa.overview(ui.conn(), scope, key, df)
    if bullets is None:
        return ui.ai_card("AI summary", [html.escape(meta)], "Auto summary")
    ui.ai_card("AI summary", [ui.cite_html(b) for b in bullets], f"Auto summary · {meta.lower()}")
    ui.cited_reviews(ids, key=f"cited_{scope}_{key}",  # the company column is redundant on a company page
                     cols=("cite", "job_profile", "selection") if scope == "company" else ("cite", "company", "selection"))


def stats(df, last, per_row=4):
    p, i = df[df.type == "placement"], df[df.type == "internship"]
    ui.metrics([("Reviews", len(df)), ("Median CTC (LPA)", ui.med(p.pay)),
                ("Median stipend (k/mo)", ui.med(i.pay, 0)), last], per_row)
    st.markdown(ui.tags_html(ui.tag_counts(df).head(10).index), unsafe_allow_html=True)


def tail(scope, key, df, cols):
    """AI summary, then the newest reviews (click a row to open)."""
    ai_summary(scope, key, df)
    st.markdown(f"**Recent reviews** · {min(10, len(df))} of {len(df)}")
    ui.review_table(df.head(10)[cols], df.head(10).id, key=f"recent_{scope}_{key}")


def companies():
    conn = ui.conn()
    reviews = db.query_reviews(conn)  # 2-year window applied in lib/db.py
    g = reviews.groupby("company")
    co = db.list_companies(conn)
    co = co.assign(reviews=co.name.map(g.size()).fillna(0).astype(int),
                   ctc=co.name.map(g.apply(lambda x: x.loc[x.type == "placement", "pay"].median())))
    ui.setup("Companies", f"{len(co)} companies, last 2 years")
    left, right = st.columns([5, 7], gap="medium")
    with left, st.container(border=True):
        q = st.text_input("Search", placeholder="Search company or sector", label_visibility="collapsed").strip()
        tier = st.pills("Tier", ["All", *ui.TIERS], default="All", label_visibility="collapsed") or "All"
        hit = lambda s: s.fillna("").str.contains(q, case=False, regex=False)  # noqa: E731
        shown = co[(hit(co.name) | hit(co.sector)) & ((co.tier == tier) | (tier == "All"))]
        shown = shown.sort_values(["reviews", "name"], ascending=[False, True])
        ev = st.dataframe(  # new key per filter so a stale row index never points at the wrong company
            shown[["name", "tier", "reviews", "ctc"]], hide_index=True, width="stretch", height=min(38 + 35 * len(shown), 560),
            on_select="rerun", selection_mode="single-row", key=f"co_{q}_{tier}",
            column_config={"name": st.column_config.TextColumn("Company", width=170),
                           "tier": st.column_config.TextColumn("Tier", width=96),
                           "reviews": st.column_config.NumberColumn("Reviews", width=68),
                           "ctc": st.column_config.NumberColumn("Median CTC", width=84, format="%.1f")})
    if shown.empty:
        return right.info("No company matches. Clear the search or pick another tier.")
    sel = shown.iloc[ev.selection.rows[0] if ev.selection.rows else 0]  # default: most reviews
    df = reviews[reviews.company == sel["name"]]
    with right:
        st.subheader(sel["name"])
        st.caption(" · ".join(str(x) for x in (sel.tier, sel.sector, sel.hq) if isinstance(x, str) and x))
        if df.empty:
            return st.info("No reviews in the last 2 years. Be the first: use Submit review.")
        stats(df, ("Avg rounds", ui.med(df.rounds.astype(float), 1, "mean")), per_row=2)  # narrow column
        tail("company", sel["name"], df, ["job_profile", "batch_year", "selection"])


def departments():
    ui.setup("Departments", "B.Tech departments, last 2 years")
    dept = st.pills("Department", ui.DEPARTMENTS, default="CSE", label_visibility="collapsed") or "CSE"
    df = db.query_reviews(ui.conn(), {"departments": [dept]})
    if df.empty:
        return st.info(f"No {dept} reviews in the last 2 years. Add one from Submit review.")
    stats(df, ("Companies", df.company.nunique()))
    c1, c2 = st.columns(2, gap="medium")
    with c1, st.container(border=True, key="eq_dept_top"):
        st.markdown("**Top companies**")
        st.plotly_chart(ui.hbar(df.company.value_counts().head(10)), config=ui.CHART, width="stretch")
    with c2, st.container(border=True, key="eq_dept_pay"):
        st.markdown("**Pay by tier**")
        kind = st.segmented_control("Pay", ["Placement CTC", "Internship stipend"], default="Placement CTC",
                                    label_visibility="collapsed") or "Placement CTC"
        rtype, unit = ("placement", "LPA") if kind == "Placement CTC" else ("internship", "k / month")
        pay = df[(df.type == rtype) & df.pay.notna()]
        if pay.empty:
            st.caption(f"No {rtype} pay data for {dept}.")
        else:
            fig = px.box(pay, x="tier", y="pay", color="tier", category_orders={"tier": ui.TIERS}, points="outliers")
            fig.update_layout(showlegend=False)
            fig.update_traces(hovertemplate="%{y:.1f} " + unit + "<extra></extra>")
            fig = ui.style_fig(fig, 264)
            fig.update_yaxes(title=unit, title_font=dict(size=11))
            st.plotly_chart(fig, config=ui.CHART, width="stretch")
    tail("department", dept, df, ["company", "batch_year", "selection"])
