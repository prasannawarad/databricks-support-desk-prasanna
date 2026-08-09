"""Offline smoke test: swaps Lakebase for in-memory SQLite and drives every route.

    python3 smoke_test.py

Requires only flask. Proves the routes, validation, and templates work before
you spend time deploying. It does NOT test the Lakebase connection itself --
use `python3 init_db.py` and `/healthz` for that.
"""

import sqlite3
import sys
import types
from datetime import datetime

# Stub the db module so importing repository/app never needs psycopg or the SDK.
conn = sqlite3.connect(":memory:", check_same_thread=False)
conn.row_factory = sqlite3.Row
conn.execute("PRAGMA foreign_keys = ON")
conn.executescript("""
CREATE TABLE tickets (
    ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open',
    priority TEXT NOT NULL DEFAULT 'medium', category TEXT,
    created_by TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE ticket_messages (
    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL REFERENCES tickets(ticket_id) ON DELETE CASCADE,
    message_text TEXT NOT NULL, author TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
INSERT INTO tickets (title, status, priority, category, created_by) VALUES
 ('Cannot sign in', 'open', 'high', 'access', 'alice@x.com'),
 ('Export fails', 'in_progress', 'urgent', 'bug', 'bob@x.com'),
 ('Dark mode', 'resolved', 'low', 'feature', 'carol@x.com');
INSERT INTO ticket_messages (ticket_id, message_text, author) VALUES
 (1,'reset did not help','alice@x.com'), (1,'which browser?','desk@x.com'),
 (2,'500 on export','bob@x.com'),        (2,'reproduced','desk@x.com'),
 (3,'please add','carol@x.com'),         (3,'shipped in 2.4','desk@x.com');
""")
conn.commit()


def _pg(sql):
    """psycopg placeholders -> sqlite3 placeholders."""
    return sql.replace("%s", "?")


def _rows(sql, params=()):
    cur = conn.execute(_pg(sql), params)
    out = []
    for r in cur.fetchall():
        d = dict(r)
        for k, v in d.items():
            if k.endswith("_at") or k == "last_activity":
                d[k] = datetime.fromisoformat(str(v))
        out.append(d)
    return out


class _Cur:
    def __init__(self): self._c = None
    def __enter__(self): return self
    def __exit__(self, *a): pass
    def execute(self, sql, params=()): self._c = conn.execute(_pg(sql), params)
    def fetchone(self):
        if "RETURNING" in str(self._c) or self._c.description is None:
            return {"ticket_id": self._c.lastrowid, "message_id": self._c.lastrowid}
        r = self._c.fetchone()
        return dict(r) if r else None
    @property
    def rowcount(self): return self._c.rowcount


class _Conn:
    def __enter__(self): return self
    def __exit__(self, *a): conn.commit()
    def cursor(self): return _Cur()


fake_db = types.ModuleType("db")
fake_db.query = lambda sql, params=None: _rows(sql, params or ())
fake_db.query_one = lambda sql, params=None: (_rows(sql, params or ()) or [None])[0]
fake_db.get_pool = lambda: types.SimpleNamespace(connection=lambda: _Conn())


def _execute(sql, params=None):
    cur = conn.execute(_pg(sql), params or ())
    count = cur.rowcount
    conn.commit()
    return count


fake_db.execute = _execute
sys.modules["db"] = fake_db

import app as application  # noqa: E402

application.app.config.update(TESTING=True)
client = application.app.test_client()

checks = []


def check(label, cond):
    checks.append((label, cond))
    print(("  PASS  " if cond else "  FAIL  ") + label)


print("\nSupport Desk smoke test\n" + "-" * 40)

r = client.get("/")
check("index renders", r.status_code == 200)
check("seeded ticket listed", b"Cannot sign in" in r.data)
check("status counters render", b"All tickets" in r.data)

r = client.get("/?status=resolved")
check("status filter works", b"Dark mode" in r.data and b"Cannot sign in" not in r.data)

r = client.get("/?status=bogus")
check("bad filter rejected", b"Unknown status filter" in r.data)

r = client.post("/tickets", data={"title": "", "created_by": "x"}, follow_redirects=True)
check("empty title rejected", b"Add a title" in r.data)

r = client.post("/tickets", data={
    "title": "Printer offline", "created_by": "dana@x.com",
    "priority": "high", "category": "hardware",
    "first_message": "It went offline after the update.",
}, follow_redirects=True)
check("ticket created", b"Printer offline" in r.data)
check("opening message stored", b"went offline after the update" in r.data)

r = client.post("/tickets/1/messages",
                data={"message_text": "", "author": "desk@x.com"}, follow_redirects=True)
check("empty message rejected", b"Write a message" in r.data)

r = client.post("/tickets/1/messages",
                data={"message_text": "SSO was disabled, re-enabled now.",
                      "author": "desk@x.com"}, follow_redirects=True)
check("message added", b"SSO was disabled" in r.data)

r = client.post("/tickets/1/status", data={"status": "resolved"}, follow_redirects=True)
check("status updated", b"moved to resolved" in r.data)

r = client.post("/tickets/1/status", data={"status": "nope"}, follow_redirects=True)
check("bad status rejected", b"Pick a status" in r.data)

r = client.post("/tickets/3/delete", data={"confirm_id": "9"}, follow_redirects=True)
check("wrong confirmation blocks delete", b"to delete this ticket" in r.data)

r = client.post("/tickets/3/delete", data={"confirm_id": "3"}, follow_redirects=True)
check("delete works", b"were deleted" in r.data)
check("cascade removed messages", not _rows("SELECT 1 FROM ticket_messages WHERE ticket_id=3"))

r = client.get("/tickets/999", follow_redirects=True)
check("missing ticket handled", b"no longer exists" in r.data)

r = client.get("/nope")
check("404 page renders", r.status_code == 404)

r = client.get("/tickets")          # POST-only route
check("wrong method stays a 405", r.status_code == 405)

failed = [c for c, ok in checks if not ok]
print("-" * 40)
print(f"{len(checks) - len(failed)}/{len(checks)} passed")
sys.exit(1 if failed else 0)
