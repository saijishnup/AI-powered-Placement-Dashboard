"""SQLite access. All reads apply the 2-year window here, nowhere else.
Plain SQL (works on sqlite3 and libsql/Turso); sqlite-utils only builds the FTS index + sync triggers on a fresh DB."""
import os
import sqlite3
from datetime import date
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
  ai_summary TEXT, is_seed INTEGER DEFAULT 0, created_at TEXT NOT NULL,
  approved INTEGER DEFAULT 1);  -- student submissions start at 0 until an admin approves

CREATE TABLE IF NOT EXISTS overview_cache(
  scope TEXT, key TEXT, content TEXT, dirty INTEGER DEFAULT 1, updated_at TEXT,
  PRIMARY KEY(scope, key));

CREATE TABLE IF NOT EXISTS admins(email TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS asks(email TEXT, at TEXT);  -- one row per Ask AI call (daily limit)
"""


def connect(path=DB_PATH):
    """Local SQLite file, or a Turso embedded replica when TURSO_URL is set (reads stay local, writes go to Turso)."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    if os.getenv("TURSO_URL"):
        import libsql  # only needed when hosted
        conn = libsql.connect(str(Path(path).with_name("replica.db")), sync_url=os.environ["TURSO_URL"],
                              auth_token=os.getenv("TURSO_TOKEN", ""))
        conn.sync()
    else:
        conn = sqlite3.connect(path, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE name = 'reviews_fts'").fetchone():
        sqlite_utils.Database(conn)["reviews"].enable_fts(FTS_COLS, create_triggers=True)
    if not conn.execute("SELECT 1 FROM admins").fetchone():  # first run: seed admins from ADMINS
        conn.executemany("INSERT INTO admins VALUES (?)", [(e.strip().lower(),) for e in os.getenv("ADMINS", "").split(",") if e.strip()])
        conn.commit()
    return conn


def _dicts(cur):
    """Rows as dicts (libsql has no row_factory)."""
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def _where(filters):
    """Build WHERE clause + params from the shared filters dict."""
    f = filters or {}
    sql, p = [WINDOW, "r.approved = 1"], []
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
    rows = _dicts(conn.execute(f"SELECT r.*, c.name AS company, c.tier, c.sector {BASE} WHERE r.id = ?", (review_id,)))
    return rows[0] if rows else None


def list_companies(conn):
    return pd.read_sql_query("SELECT * FROM companies ORDER BY name", conn)


def company_id(conn, name, tier="Normal", sector=None):
    """Return id for a company name, creating it if new (submit form 'other')."""
    conn.execute("INSERT OR IGNORE INTO companies(name, tier, sector) VALUES (?, ?, ?)", (name, tier, sector))
    return conn.execute("SELECT id FROM companies WHERE name = ?", (name,)).fetchone()[0]


def insert_review(conn, data):
    data = {"created_at": date.today().isoformat(), **data}  # keys come from our code, never from users
    rid = conn.execute(f"INSERT INTO reviews({','.join(data)}) VALUES ({','.join('?' * len(data))})",
                       list(data.values())).lastrowid
    mark_dirty(conn, "company", conn.execute("SELECT name FROM companies WHERE id = ?", (data["company_id"],)).fetchone()[0])
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
    return _dicts(conn.execute(
        f"SELECT r.*, c.name AS company, c.tier {BASE} JOIN reviews_fts f ON f.rowid = r.id "
        f"WHERE reviews_fts MATCH ? AND {where} ORDER BY bm25(reviews_fts) LIMIT ?",
        [match, *p, k]))


def get_cache(conn, scope, key):
    rows = _dicts(conn.execute("SELECT content, dirty FROM overview_cache WHERE scope=? AND key=?", (scope, key)))
    return rows[0] if rows else None


def set_cache(conn, scope, key, content):
    conn.execute("INSERT INTO overview_cache VALUES (?, ?, ?, 0, datetime('now', 'localtime')) ON CONFLICT(scope, key) "
                 "DO UPDATE SET content = excluded.content, dirty = 0, updated_at = excluded.updated_at", (scope, key, content))
    conn.commit()


def mark_dirty(conn, scope, key):
    conn.execute("INSERT INTO overview_cache(scope, key) VALUES (?, ?) ON CONFLICT(scope, key) DO UPDATE SET dirty = 1",
                 (scope, key))


# ---------- admins, Ask AI limit, moderation ----------
def admins(conn):
    return [r[0] for r in conn.execute("SELECT email FROM admins ORDER BY email").fetchall()]


def is_admin(conn, email):
    return email.lower() in admins(conn)


def set_admin(conn, email, on):
    """Add or remove an admin. Never removes the last one (no lock-out)."""
    if on:
        conn.execute("INSERT OR IGNORE INTO admins VALUES (?)", (email.lower(),))
    elif len(admins(conn)) > 1:
        conn.execute("DELETE FROM admins WHERE email = ?", (email.lower(),))
    conn.commit()


def asks_today(conn, email):
    return conn.execute("SELECT count(*) FROM asks WHERE email = ? AND at >= date('now')", (email,)).fetchone()[0]


def log_ask(conn, email):
    conn.execute("INSERT INTO asks VALUES (?, datetime('now'))", (email,))
    conn.commit()


def usage_today(conn):
    return pd.read_sql_query("SELECT email, count(*) AS asks FROM asks WHERE at >= date('now') "
                             "GROUP BY email ORDER BY asks DESC", conn)


def submissions(conn, limit=50):
    """Student-written reviews (not seed), newest first, approved or not."""
    return pd.read_sql_query(f"SELECT r.*, c.name AS company {BASE} WHERE r.is_seed = 0 "
                             "ORDER BY r.approved, r.id DESC LIMIT ?", conn, params=[limit])


def moderate(conn, review_id, approve):
    """Approve (show it) or delete a review; either way its overviews regenerate."""
    row = get_review(conn, review_id)
    conn.execute("UPDATE reviews SET approved = 1 WHERE id = ?" if approve else "DELETE FROM reviews WHERE id = ?",
                 (review_id,))
    mark_dirty(conn, "company", row["company"])
    mark_dirty(conn, "department", row["department"])
    conn.commit()


def reset_overviews(conn):
    conn.execute("UPDATE overview_cache SET dirty = 1")
    conn.commit()
