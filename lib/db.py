"""SQLite access. All reads apply the 2-year window here, nowhere else.
Tables are plain SQL (CHECK constraints); sqlite-utils builds the FTS index + sync triggers and does inserts/upserts."""
import sqlite3
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import sqlite_utils

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "reviews.db"
WINDOW = "r.created_at >= date('now', '-2 years')"

SCHEMA = """
CREATE TABLE IF NOT EXISTS companies(
  id INTEGER PRIMARY KEY,
  name TEXT UNIQUE NOT NULL,
  tier TEXT CHECK(tier IN ('Super Dream','Dream','Normal','University')),
  sector TEXT, hq TEXT);

CREATE TABLE IF NOT EXISTS reviews(
  id INTEGER PRIMARY KEY,
  company_id INTEGER NOT NULL REFERENCES companies(id),
  author_name TEXT, author_email TEXT, consent INTEGER DEFAULT 0, linkedin TEXT,
  department TEXT NOT NULL, batch_year INTEGER NOT NULL,
  cgpa REAL CHECK(cgpa BETWEEN 0 AND 10),
  type TEXT CHECK(type IN ('internship','placement')),
  outcome TEXT CHECK(outcome IN ('company','university')),
  job_profile TEXT, job_location TEXT,
  pay REAL,                 -- LPA for placement, INR k/month for internship
  rounds INTEGER, tags TEXT,
  selection TEXT, preparation TEXT, experience TEXT, advice TEXT, tips TEXT,
  ai_summary TEXT, is_seed INTEGER DEFAULT 0, created_at TEXT NOT NULL);

CREATE TABLE IF NOT EXISTS overview_cache(
  scope TEXT, key TEXT, content TEXT, dirty INTEGER DEFAULT 1, updated_at TEXT,
  PRIMARY KEY(scope, key));
"""


def connect(path=DB_PATH):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    if "reviews_fts" not in sqlite_utils.Database(conn).table_names():
        _t(conn, "reviews").enable_fts(FTS_COLS, create_triggers=True)
    return conn


def _t(conn, name):
    return sqlite_utils.Database(conn)[name]


def _where(filters):
    """Build WHERE clause + params from the shared filters dict."""
    f = filters or {}
    sql, p = [WINDOW], []
    if f.get("type"):
        sql.append("r.type = ?"); p.append(f["type"])
    for key, col in (("departments", "r.department"), ("batches", "r.batch_year"), ("tiers", "c.tier")):
        if f.get(key):
            sql.append(f"{col} IN ({','.join('?' * len(f[key]))})"); p += list(f[key])
    if f.get("company_q"):
        sql.append("c.name LIKE ?"); p.append(f"%{f['company_q']}%")
    if f.get("cgpa"):
        sql.append("r.cgpa BETWEEN ? AND ?"); p += list(f["cgpa"])
    return " AND ".join(sql), p


FTS_COLS = ["selection", "preparation", "experience", "advice", "tips", "job_profile"]
BASE = "FROM reviews r JOIN companies c ON c.id = r.company_id"
STOP = set("a an the is are was were be do does did how what which who whom when where why in on of for to and or "
           "at by with from as it its this that these those i me my we our you your they them their can could "
           "should would will there here about into like any some all much many more most".split())


def query_reviews(conn, filters=None):
    where, p = _where(filters)
    return pd.read_sql_query(
        f"SELECT r.*, c.name AS company, c.tier, c.sector {BASE} WHERE {where} ORDER BY r.created_at DESC",
        conn, params=p)


def get_review(conn, review_id):
    row = conn.execute(f"SELECT r.*, c.name AS company, c.tier, c.sector {BASE} WHERE r.id = ?",
                       (review_id,)).fetchone()
    return dict(row) if row else None


def list_companies(conn):
    return pd.read_sql_query("SELECT * FROM companies ORDER BY name", conn)


def company_id(conn, name, tier="Normal", sector=None):
    """Return id for a company name, creating it if new (submit form 'other')."""
    return _t(conn, "companies").lookup({"name": name}, {"tier": tier, "sector": sector})


def insert_review(conn, data):
    rid = _t(conn, "reviews").insert({"created_at": date.today().isoformat(), **data}).last_pk
    mark_dirty(conn, "company", _t(conn, "companies").get(data["company_id"])["name"])
    mark_dirty(conn, "department", data["department"])
    conn.commit()
    return rid


def search_fts(conn, q, filters=None, k=8):
    """BM25 top-k inside window + filters. Query words OR-ed, quoted to neutralise FTS syntax."""
    # keep 2-letter terms (OA, HR, ML, OS, CN) but drop common question words
    words = [w for w in "".join(ch if ch.isalnum() else " " for ch in q).split()
             if len(w) > 1 and w.lower() not in STOP]
    if not words:
        return []
    match = " OR ".join(f'"{w}"' for w in words)
    where, p = _where(filters)
    rows = conn.execute(
        f"SELECT r.*, c.name AS company, c.tier {BASE} JOIN reviews_fts f ON f.rowid = r.id "
        f"WHERE reviews_fts MATCH ? AND {where} ORDER BY bm25(reviews_fts) LIMIT ?",
        [match, *p, k]).fetchall()
    return [dict(r) for r in rows]


def get_cache(conn, scope, key):
    row = conn.execute("SELECT content, dirty FROM overview_cache WHERE scope=? AND key=?",
                       (scope, key)).fetchone()
    return dict(row) if row else None


def set_cache(conn, scope, key, content):
    _t(conn, "overview_cache").upsert({"scope": scope, "key": key, "content": content, "dirty": 0,
                                       "updated_at": datetime.now().isoformat(" ", "seconds")}, pk=("scope", "key"))
    conn.commit()


def mark_dirty(conn, scope, key):
    _t(conn, "overview_cache").upsert({"scope": scope, "key": key, "dirty": 1}, pk=("scope", "key"))
