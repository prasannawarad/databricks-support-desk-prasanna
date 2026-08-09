"""Every SQL statement the app runs lives here, so routes stay thin."""

import db

# These mirror the CHECK constraints in schema.sql. The database is the real
# gate; these drive the UI option lists and the friendly validation errors.
STATUSES = ("open", "in_progress", "resolved")
PRIORITIES = ("low", "medium", "high", "urgent")


def list_tickets(status=None):
    sql = """
        SELECT t.ticket_id, t.title, t.status, t.priority, t.category,
               t.created_by, t.created_at,
               COUNT(m.message_id)                       AS message_count,
               COALESCE(MAX(m.created_at), t.created_at) AS last_activity
        FROM tickets t
        LEFT JOIN ticket_messages m ON m.ticket_id = t.ticket_id
        {where}
        GROUP BY t.ticket_id
        ORDER BY last_activity DESC
    """
    if status:
        return db.query(sql.format(where="WHERE t.status = %s"), (status,))
    return db.query(sql.format(where=""))


def status_counts():
    rows = db.query("SELECT status, COUNT(*) AS n FROM tickets GROUP BY status")
    return {r["status"]: r["n"] for r in rows}


def get_ticket(ticket_id):
    return db.query_one("SELECT * FROM tickets WHERE ticket_id = %s", (ticket_id,))


def get_messages(ticket_id):
    return db.query(
        """SELECT message_id, ticket_id, message_text, author, created_at
           FROM ticket_messages
           WHERE ticket_id = %s
           ORDER BY created_at ASC, message_id ASC""",
        (ticket_id,),
    )


def create_ticket(title, created_by, priority, category, first_message=None):
    """Ticket and its opening message are written in one transaction."""
    with db.get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(
            """INSERT INTO tickets (title, created_by, priority, category)
               VALUES (%s, %s, %s, %s)
               RETURNING ticket_id""",
            (title, created_by, priority, category),
        )
        ticket_id = cur.fetchone()["ticket_id"]
        if first_message:
            cur.execute(
                """INSERT INTO ticket_messages (ticket_id, message_text, author)
                   VALUES (%s, %s, %s)""",
                (ticket_id, first_message, created_by),
            )
    return ticket_id


def add_message(ticket_id, message_text, author):
    return db.execute(
        """INSERT INTO ticket_messages (ticket_id, message_text, author)
           VALUES (%s, %s, %s)""",
        (ticket_id, message_text, author),
    )


def update_status(ticket_id, status):
    return db.execute(
        "UPDATE tickets SET status = %s WHERE ticket_id = %s",
        (status, ticket_id),
    )


def delete_ticket(ticket_id):
    return db.execute("DELETE FROM tickets WHERE ticket_id = %s", (ticket_id,))
