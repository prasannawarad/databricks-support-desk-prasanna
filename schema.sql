-- Support Desk schema for Lakebase Postgres.
-- Safe to re-run: DDL is IF NOT EXISTS and the seed only fills an empty table.

CREATE TABLE IF NOT EXISTS tickets (
    ticket_id   SERIAL PRIMARY KEY,
    title       TEXT      NOT NULL CHECK (length(btrim(title)) > 0),
    status      TEXT      NOT NULL DEFAULT 'open'
                          CHECK (status IN ('open', 'in_progress', 'resolved')),
    priority    TEXT      NOT NULL DEFAULT 'medium'
                          CHECK (priority IN ('low', 'medium', 'high', 'urgent')),
    category    TEXT,
    created_by  TEXT      NOT NULL,
    created_at  TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ticket_messages (
    message_id   SERIAL PRIMARY KEY,
    ticket_id    INTEGER   NOT NULL
                           REFERENCES tickets(ticket_id) ON DELETE CASCADE,
    message_text TEXT      NOT NULL CHECK (length(btrim(message_text)) > 0),
    author       TEXT      NOT NULL,
    created_at   TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_messages_ticket ON ticket_messages (ticket_id, created_at);
CREATE INDEX IF NOT EXISTS idx_tickets_status  ON tickets (status);

-- ── Seed data (4 tickets, 3 statuses, 2+ messages each) ────────────────────
INSERT INTO tickets (title, status, priority, category, created_by)
SELECT * FROM (VALUES
    ('Cannot sign in to the analytics dashboard', 'open',        'high',   'access',  'alice@northwind.com'),
    ('Export to CSV fails on reports over 50k rows', 'in_progress','urgent','bug',     'bob@northwind.com'),
    ('Add dark mode to the settings page',        'resolved',    'low',    'feature', 'carol@northwind.com'),
    ('June invoice is missing the tax breakdown', 'open',        'medium', 'billing', 'dev@northwind.com')
) AS seed(title, status, priority, category, created_by)
WHERE NOT EXISTS (SELECT 1 FROM tickets);

INSERT INTO ticket_messages (ticket_id, message_text, author)
SELECT t.ticket_id, m.message_text, m.author
FROM (VALUES
    ('Cannot sign in to the analytics dashboard', 'Password reset went through but the login page still rejects my credentials.', 'alice@northwind.com'),
    ('Cannot sign in to the analytics dashboard', 'Which browser are you on, and is SSO enabled for your account?',              'desk@northwind.com'),
    ('Export to CSV fails on reports over 50k rows', 'Any export past ~50k rows returns a 500 after about 30 seconds.',          'bob@northwind.com'),
    ('Export to CSV fails on reports over 50k rows', 'Reproduced on staging. The export worker is timing out, patch in review.', 'desk@northwind.com'),
    ('Export to CSV fails on reports over 50k rows', 'Thanks. This blocks our month-end reporting, so an ETA would help.',       'bob@northwind.com'),
    ('Add dark mode to the settings page',        'A dark theme toggle would make late shifts much easier on the eyes.',        'carol@northwind.com'),
    ('Add dark mode to the settings page',        'Shipped in release 2.4. Marking this resolved.',                             'desk@northwind.com'),
    ('June invoice is missing the tax breakdown', 'The PDF invoice for June has no tax line, so finance cannot file it.',       'dev@northwind.com'),
    ('June invoice is missing the tax breakdown', 'Escalated to billing. The corrected invoice goes out with the next run.',    'desk@northwind.com')
) AS m(ticket_title, message_text, author)
JOIN tickets t ON t.title = m.ticket_title
WHERE NOT EXISTS (SELECT 1 FROM ticket_messages);
