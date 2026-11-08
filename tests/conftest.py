"""Shared fixtures: a throwaway SQLite DB and a fake LLM. No real DB, no network."""
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib import db, llm  # noqa: E402

RECENT = (date.today() - timedelta(days=30)).isoformat()
OLD = (date.today() - timedelta(days=3 * 365)).isoformat()


def make_review(conn, company="Acme", **over):
    """Insert one review with sensible defaults; override any field by keyword."""
    data = {"company_id": db.company_id(conn, company, tier="Dream"),
            "author_name": "Ravi Kumar", "author_email": "ravi.cs26@nitk.edu.in",
            "linkedin": "https://linkedin.com/in/ravikumar", "consent": 1,
            "department": "CSE", "batch_year": 2026, "cgpa": 8.5,
            "type": "placement", "outcome": "company", "job_profile": "SDE",
            "selection": "two coding rounds then hr", "preparation": "leetcode daily",
            "experience": "good", "advice": "revise dsa", "tips": "be calm",
            "created_at": RECENT}
    data.update(over)
    return db.insert_review(conn, data)


@pytest.fixture
def conn(tmp_path):
    c = db.connect(tmp_path / "t.db")
    yield c
    c.close()


class FakeLLM:
    """Stands in for llm.chat. `script` maps model index (in the LLM_MODEL list) -> list of replies
    (a string to return, or an Exception to raise). Records every call."""

    def __init__(self, script):
        self.script = {i: list(v) for i, v in script.items()}
        self.calls = []

    def __call__(self, messages, kind="qa", model="m0"):
        provider = int(model[1:])
        self.calls.append({"provider": provider, "kind": kind, "messages": messages})
        reply = self.script[provider].pop(0) if self.script[provider] else "NOT_SCRIPTED"
        if isinstance(reply, Exception):
            raise reply
        return reply, None


@pytest.fixture
def fake_llm(monkeypatch):
    """Call fake_llm({0: [...], 1: [...]}) to install a fake LLM with models m0, m1."""
    def install(script):
        fake = FakeLLM(script)
        monkeypatch.setattr(llm, "models", lambda: [f"m{i}" for i in sorted(script)])
        monkeypatch.setattr(llm, "chat", fake)
        return fake
    return install
