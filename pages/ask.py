import streamlit as st

from lib import qa, ui

conn = ui.conn()
ui.setup("Ask AI", "Answers come only from stored reviews in the last 2 years, with [R#] citations. "
         "Sidebar filters narrow the reviews it searches.")
f = ui.filters_sidebar()

EXAMPLES = ["What does Goldman Sachs ask in interviews?", "How do ECE students prepare for core companies?",
            "Tips for converting an internship into a PPO?", "What is the OA like at Amazon?"]

def use_example():
    """Example pill: copy it into the question box and ask. Runs before the widgets render, so this is allowed."""
    if st.session_state.ask_pick:
        st.session_state.ask_input = st.session_state.ask_pick
        st.session_state.ask_go = True
    st.session_state.ask_pick = None


# Fixed key, no changing value=: a widget whose value= changes between runs is rebuilt and drops typed text.
with st.form("ask", border=True):
    q = st.text_input("Your question", key="ask_input", max_chars=300,
                      placeholder="e.g. What does Goldman Sachs ask in interviews?")
    go = st.form_submit_button("Ask", type="primary")
st.pills("Try", EXAMPLES, label_visibility="collapsed", key="ask_pick", on_change=use_example)

question = (q or "").strip()
if (go or st.session_state.pop("ask_go", False)) and question:
    key = (question, repr(sorted(f.items())))
    if st.session_state.get("ask_key") != key:  # same question + filters: reuse, no second LLM call
        with st.spinner("Reading reviews..."):
            st.session_state.ask_res = qa.answer(conn, question, f)
        st.session_state.ask_key = key if st.session_state.ask_res.get("text") else None  # failures retry

res = st.session_state.get("ask_res")
if not res:
    st.stop()

if res.get("text") is None:
    st.warning("AI is unavailable right now: every configured model failed or was rate limited. "
               "Try again in a minute. " + res.get("error", "")[:120])
elif res["text"] == qa.NOT_ENOUGH:
    st.info(f"Not enough in the reviews: searched {res['retrieved']} matching reviews and none answer this "
            "clearly. Try other words, or clear some filters.")
else:
    ui.ai_card("Answer", [ui.cite_html(res["text"])],
               f"From {len(res['citations'])} of {res['retrieved']} retrieved reviews")
    ui.cited_reviews(res["citations"], key=f"ask_tbl_{hash(st.session_state.ask_key)}")  # new key per answer
