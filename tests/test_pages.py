"""Page-level checks with Streamlit's AppTest. The LLM is faked; pages read the real seed DB (read-only here)."""
from pathlib import Path
from unittest import mock

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent.parent
PAGES = ["dashboard", "companies", "departments", "review", "submit", "ask"]
OVERVIEW = {"companies", "departments"}  # functions in pages/overview.py


@pytest.mark.parametrize("page", PAGES)
def test_page_renders_without_error(page):
    at = (AppTest.from_string(f"from pages.overview import {page}; {page}()", default_timeout=60) if page in OVERVIEW
          else AppTest.from_file(str(ROOT / "pages" / f"{page}.py"), default_timeout=60))
    at.query_params["id"] = "1116"  # review page: the injection test row
    at.session_state["email"] = "test.cs26@nitk.edu.in"
    with mock.patch("lib.qa.overview", return_value=(["Cached test bullet [R1]"], {"R1": 1116}, "Cached")), \
         mock.patch("lib.qa.review_summary", return_value=(["a", "b", "c"], "Cached")):
        at.run()
    assert not at.exception and at.title  # a script that fails to compile renders nothing and raises nothing


def test_ask_second_question_replaces_first():
    """Regression: the question box used a changing value=, so a typed follow-up was dropped and the old answer stayed."""
    def fake(conn, q, f):
        return {"text": f"ANS:{q} [R1]", "citations": {}, "provider": 0, "retrieved": 8}

    with mock.patch("lib.qa.answer", side_effect=fake):
        at = AppTest.from_file(str(ROOT / "pages" / "ask.py"), default_timeout=60).run()
        ask = lambda q: (at.text_input(key="ask_input").input(q),  # noqa: E731
                         next(b for b in at.button if b.label == "Ask").click(), at.run())
        ask("first question")
        ask("second question")
    shown = " ".join(m.value for m in at.markdown)
    assert "ANS:second question" in shown and "ANS:first question" not in shown
