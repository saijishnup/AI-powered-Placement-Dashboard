"""Entry point: Google login (demo email form when [auth] is not configured) + sidebar navigation."""
import html
import re

import streamlit as st

from lib import db
from lib.ui import apply_css, conn
from pages import overview

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@nitk\.edu\.in$")

st.set_page_config(page_title="Placement Dashboard", page_icon="assets/logo.svg", layout="wide")
st.logo("assets/logo.svg")  # graduation cap: sidebar brand + browser tab
apply_css()

try:
    GOOGLE = "auth" in st.secrets  # .streamlit/secrets.toml [auth] = real Google sign-in
except Exception:  # no secrets file at all
    GOOGLE = False


def allowed(email):
    return bool(EMAIL_RE.fullmatch(email)) or db.is_admin(conn(), email)


def login():
    _, mid, _ = st.columns([1, 1.1, 1])  # centred card; side columns stay empty
    with mid, st.container(key="login"):
        st.title("Placement Dashboard")
        st.caption("NITK B.Tech internship and placement experiences")
        if st.session_state.pop("denied", None):
            st.error("Use your @nitk.edu.in Google account.")
        if GOOGLE:
            st.button("Sign in with Google", type="primary", width="stretch", on_click=st.login)
        else:
            login_form()


def login_form():
    with st.form("login", border=True):
        email = st.text_input("NITK email", placeholder="name.dept@nitk.edu.in").strip().lower()
        if st.form_submit_button("Continue", type="primary", width="stretch"):
            if allowed(email):
                st.session_state.email = email
                st.rerun()
            st.error("Use your @nitk.edu.in email.")
        st.markdown('<p class="pd-muted">Demo login: Google sign-in is off on this machine.</p>', unsafe_allow_html=True)


if GOOGLE and st.user.is_logged_in and "email" not in st.session_state:
    if allowed(st.user.email.lower()):
        st.session_state.email = st.user.email.lower()
    else:
        st.session_state.denied = True
        st.logout()

if "email" not in st.session_state:
    st.navigation([st.Page(login, title="Sign in")], position="hidden").run()
else:
    with st.sidebar:
        # plain span: st.caption would auto-link the email address
        st.markdown(f'<div class="pd-account"><div class="pd-muted">Signed in as</div>'
                    f'<div class="pd-user">{html.escape(st.session_state.email)}</div></div>',
                    unsafe_allow_html=True)
        if st.button("Sign out", type="tertiary", key="signout"):
            del st.session_state.email
            st.logout() if GOOGLE else st.rerun()
    st.navigation([
        st.Page("pages/dashboard.py", title="Dashboard", default=True),
        st.Page(overview.companies, title="Companies"),
        st.Page(overview.departments, title="Departments"),
        st.Page("pages/ask.py", title="Ask AI"),
        st.Page("pages/submit.py", title="Submit review"),
        *([st.Page("pages/admin.py", title="Admin")] if db.is_admin(conn(), st.session_state.email) else []),
        st.Page("pages/review.py", title="Review", url_path="review", visibility="hidden"),
    ]).run()
