"""Lakebase (Postgres) connection handling.

Credentials are never stored. Every new pooled connection asks the Databricks
SDK for a fresh OAuth token, which works identically for a local user identity
and for the app's service principal once deployed.
"""

import os
import threading

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from databricks.sdk import WorkspaceClient

_pool = None
_lock = threading.Lock()


class OAuthConnection(psycopg.Connection):
    """Injects a freshly minted database credential as the password."""

    workspace = None

    @classmethod
    def connect(cls, conninfo="", **kwargs):
        if cls.workspace is None:
            cls.workspace = WorkspaceClient()
        credential = cls.workspace.postgres.generate_database_credential(
            endpoint=os.environ["ENDPOINT_NAME"]
        )
        kwargs["password"] = credential.token
        return super().connect(conninfo, **kwargs)


def _conninfo():
    settings = {
        "PGHOST": os.environ.get("PGHOST"),
        "PGDATABASE": os.environ.get("PGDATABASE"),
        "ENDPOINT_NAME": os.environ.get("ENDPOINT_NAME"),
        # Deployed, the Postgres user IS the app's service principal, and
        # Databricks Apps injects that ID for us. Locally, PGUSER is your email.
        "PGUSER": os.environ.get("PGUSER") or os.environ.get("DATABRICKS_CLIENT_ID"),
    }
    missing = [k for k, v in settings.items() if not v]
    if missing:
        raise RuntimeError(
            "Missing environment variables: " + ", ".join(missing) +
            ". Set them in app.yaml (deployed) or your shell (local)."
        )
    return (
        f"dbname={settings['PGDATABASE']} "
        f"user={settings['PGUSER']} "
        f"host={settings['PGHOST']} "
        f"port={os.environ.get('PGPORT', '5432')} "
        f"sslmode={os.environ.get('PGSSLMODE', 'require')}"
    )


def get_pool():
    """Create the pool on first use so imports never touch the network."""
    global _pool
    if _pool is None:
        with _lock:
            if _pool is None:
                _pool = ConnectionPool(
                    conninfo=_conninfo(),
                    connection_class=OAuthConnection,
                    min_size=1,
                    max_size=10,
                    max_lifetime=1800,   # recycle before the 60-min token expires
                    open=True,
                    kwargs={"row_factory": dict_row},
                )
    return _pool


def query(sql, params=None):
    """Read rows as dicts."""
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(sql, params or ())
        return cur.fetchall()


def query_one(sql, params=None):
    rows = query(sql, params)
    return rows[0] if rows else None


def execute(sql, params=None):
    """Write inside a transaction. Returns the number of rows affected."""
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(sql, params or ())
        return cur.rowcount
