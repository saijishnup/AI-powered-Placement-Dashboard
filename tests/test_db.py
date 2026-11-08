"""Login regex, 2-year window, FTS search, cache dirty flags."""
import re
from pathlib import Path

from conftest import OLD, make_review
from lib import db

EMAIL_PATTERN = r"^[A-Za-z0-9._%+-]+@nitk\.edu\.in$"


def test_email_regex_matches_app_and_only_accepts_nitk():
    app_src = (Path(__file__).resolve().parent.parent / "app.py").read_text(encoding="utf-8")
    assert f're.compile(r"{EMAIL_PATTERN}")' in app_src  # same pattern the app uses
    rx = re.compile(EMAIL_PATTERN)
    assert rx.fullmatch("x.cs26@nitk.edu.in")
    for bad in ["x@gmail.com", "x@nitk.edu.in.evil.com", "x@NITK.edu.in.com"]:
        assert not rx.fullmatch(bad), bad


def test_two_year_window_hides_old_review(conn):
    new_id = make_review(conn, selection="recent graph question")
    old_id = make_review(conn, selection="ancient graph question", created_at=OLD)
    ids = set(db.query_reviews(conn)["id"])
    assert new_id in ids and old_id not in ids
    fts_ids = {r["id"] for r in db.search_fts(conn, "graph question")}
    assert fts_ids == {new_id}


def test_fts_finds_keyword_and_honours_filter(conn):
    intern = make_review(conn, type="internship", preparation="studied kubernetes deeply")
    place = make_review(conn, type="placement", preparation="studied kubernetes too")
    make_review(conn, preparation="only aptitude")
    assert {r["id"] for r in db.search_fts(conn, "kubernetes")} == {intern, place}
    assert [r["id"] for r in db.search_fts(conn, "kubernetes", {"type": "internship"})] == [intern]
    assert [r["id"] for r in db.search_fts(conn, "kubernetes", {"departments": ["ECE"]})] == []


def test_fts_survives_hostile_input(conn):
    make_review(conn)
    for q in ['"OR ( * ', 'NEAR( "', "dsa* AND (", "'; DROP TABLE reviews; --"]:
        assert isinstance(db.search_fts(conn, q), list)  # no sqlite3.OperationalError


def test_insert_review_marks_company_and_department_dirty(conn):
    make_review(conn, company="Acme", department="ECE")
    db.set_cache(conn, "company", "Acme", "{}")
    assert db.get_cache(conn, "company", "Acme")["dirty"] == 0
    make_review(conn, company="Acme", department="ECE")
    assert db.get_cache(conn, "company", "Acme")["dirty"] == 1
    assert db.get_cache(conn, "department", "ECE")["dirty"] == 1
