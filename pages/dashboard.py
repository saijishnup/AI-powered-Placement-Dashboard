"""Dashboard: KPI row, 2x2 chart grid, filtered review table. One DB query per rerun."""
import pandas as pd
import plotly.express as px
import streamlit as st

from lib import db, ui

ui.setup("Dashboard", "Last 2 years. Includes synthetic seed data.")
f = ui.filters_sidebar()
df = db.query_reviews(ui.conn(), f)

# Short department labels so the box-plot x axis stays readable.
SHORT = {"Mechanical": "ME", "Civil": "CV", "Chemical": "CH", "Metallurgical and Materials": "MT",
         "Mining": "MN", "Computational and Data Science": "CDS"}
CHART = ui.CHART


def pay_box(rows, unit, height=320):
    rows = rows.dropna(subset=["pay"])
    if rows.empty:
        return st.caption("No pay data for these filters.")
    fig = px.box(rows.assign(dept=rows.department.replace(SHORT)), x="dept", y="pay", points=False,
                 category_orders={"dept": [SHORT.get(d, d) for d in ui.DEPARTMENTS]})
    fig.update_traces(marker_color=ui.ACCENT, line_width=1.2, hovertemplate=f"%{{x}}<br>%{{y}} {unit}<extra></extra>")
    fig = ui.style_fig(fig, height)
    fig.update_yaxes(ticksuffix=f" {unit}" if unit == "LPA" else "k")
    st.plotly_chart(fig, width="stretch", config=CHART)


# ---------- KPI row ----------
place, intern = df[df.type == "placement"], df[df.type == "internship"]
ui.metrics([("Reviews", f"{len(df):,}"), ("Companies", df.company.nunique()),
            ("Median CTC (LPA)", ui.med(place.pay)), ("Median stipend (k/mo)", ui.med(intern.pay, 0))])
if df.empty:
    st.info("No reviews match these filters. Clear a filter in the sidebar.")
    st.stop()

# ---------- 2x2 chart grid ----------
r1 = st.columns(2)
with r1[0], st.container(border=True, key="eq_top_companies"):
    st.markdown("**Top 10 companies by reviews**")
    st.plotly_chart(ui.hbar(df.company.value_counts().head(10)), width="stretch", config=CHART)

with r1[1], st.container(border=True, key="eq_pay"):
    st.markdown("**Pay by department**")
    if f["type"] == "placement":
        pay_box(place, "LPA")
    elif f["type"] == "internship":
        pay_box(intern, "k/mo")
    else:
        t1, t2 = st.tabs(["Placement CTC (LPA)", "Internship stipend (k/mo)"])
        with t1:  # tabs take ~56px, so the chart is shorter to keep the row even
            pay_box(place, "LPA", 264)
        with t2:
            pay_box(intern, "k/mo", 264)

r2 = st.columns(2)
with r2[0], st.container(border=True, key="eq_years"):
    st.markdown("**Reviews per year**")
    years = df.assign(year=df.created_at.str[:4], type=df.type.str.capitalize())
    fig = px.histogram(years.sort_values("year"), x="year", color="type", category_orders={"type": ["Internship", "Placement"]})
    fig.update_traces(hovertemplate="%{x}: %{y}")  # px colours follow the theme palette in config.toml
    fig = ui.style_fig(fig)
    fig.update_layout(barmode="stack", bargap=0.55)
    st.plotly_chart(fig, width="stretch", config=CHART)

with r2[1], st.container(border=True, key="eq_tags"):
    st.markdown("**Top topic tags**")
    tags = ui.tag_counts(df).head(12)
    if tags.empty:
        st.caption("No tags for these filters.")
    else:
        st.plotly_chart(ui.hbar(tags), width="stretch", config=CHART)

# ---------- review table ----------
with st.container(border=True):
    c1, c2 = st.columns([2, 1], vertical_alignment="center")
    c1.markdown(f"**Reviews** · {len(df):,} matching")
    show_mail = c2.toggle("Show consented emails", key="dash_show_mail",
                          help="Only students who ticked consent are shown.")
    top = df.head(200)
    email = top.author_email.where(top.consent == 1) if show_mail else None
    table = pd.DataFrame({
        "Company": top.company, "Dept": top.department, "Type": top.type.str.capitalize(),
        "Batch": top.batch_year, "CGPA": top.cgpa,
        "Pay": [ui.pay_text(p, t) for p, t in zip(top.pay, top.type)],
        "Rounds": top.rounds, "Date": top.created_at.str[:10],
        "Email": (email.fillna("no consent") if show_mail
                  else top.consent.map(lambda c: "hidden" if c == 1 else "no consent")),
    })
    st.caption(f"Newest {len(top):,} of {len(df):,}. Click a row to open the review.")
    ui.review_table(table, top.id, "dash_table",
                    column_config={"CGPA": st.column_config.NumberColumn(format="%.2f"),
                                   "Batch": st.column_config.NumberColumn(format="%d")})
