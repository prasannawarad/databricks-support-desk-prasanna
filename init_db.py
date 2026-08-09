"""Apply schema.sql to Lakebase and print what's in the tables.

Usage (after exporting the PG* / ENDPOINT_NAME variables):
    python3 init_db.py
"""

import pathlib
import sys

import db
import repository as repo


def main():
    sql = pathlib.Path(__file__).with_name("schema.sql").read_text()

    with db.get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(sql)

    # Same query the home page runs, so this verifies the app's own read path.
    tickets = sorted(repo.list_tickets(), key=lambda t: t["ticket_id"])

    print(f"\n{len(tickets)} tickets in Lakebase:\n")
    for t in tickets:
        print(f"  #{t['ticket_id']:<3} [{t['status']:<11}] [{t['priority']:<6}] "
              f"{t['title'][:48]:<50} {t['message_count']} messages")
    print()

    if len(tickets) < 3 or min((t["message_count"] for t in tickets), default=0) < 2:
        print("WARNING: fewer tickets or messages than the assignment requires.")
        return 1
    print("Schema and sample data look good.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
