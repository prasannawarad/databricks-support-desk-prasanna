# Runbook — Support Desk on Databricks Apps + Lakebase

Follow top to bottom. Roughly 45–60 minutes the first time.
Four values get collected along the way; keep a scratch file:

| Value | Where it comes from | Used in |
|---|---|---|
| `CLIENT_ID` | App → Environment tab, `DATABRICKS_CLIENT_ID` | `grants.sql`, `app.yaml` |
| `PGHOST` | Lakebase → Connect → Parameters only | `app.yaml`, local env |
| `ENDPOINT_NAME` | Lakebase → branch → Computes → Get ID → Copy resource name | `app.yaml`, local env |
| `APP_URL` | App page after deploy | your submission |

---

## Step 0 — Local prerequisites

```bash
python3 --version          # 3.9+
databricks --version       # install: https://docs.databricks.com/aws/en/dev-tools/cli/install
databricks auth login      # pick your workspace host, finish in browser
databricks current-user me # should print your email
```

Unzip this project and `cd` into it.

---

## Step 1 — Create the Databricks App (do not deploy yet)

1. Workspace sidebar → **Compute** → **Apps** → **Create app**.
2. Choose the **Flask** "Hello world" template.
3. Name it `support-desk`. Create.
4. Open the app → **Environment** tab → copy `DATABRICKS_CLIENT_ID`
   (a UUID like `6b215d2b-f099-4bdb-900a-60837201ecec`). This is your `CLIENT_ID`
   and it doubles as the app's Postgres username.

Creating the app first is what gives you the service principal identity that
Lakebase will grant access to.

---

## Step 2 — Create the Lakebase database

1. App switcher (top-left grid icon) → **Lakebase Postgres** → **New project**.
2. Name `support-desk-db`, accept Postgres 17.
3. Wait ~1 minute for compute to go **Active**.
4. Click **Connect** → choose **Parameters only** → copy `PGHOST`.
5. Go to the branch's **Computes** tab → **Get ID** → **Copy resource name**.
   That is `ENDPOINT_NAME`, shaped like
   `projects/<project-id>/branches/<branch-id>/endpoints/<endpoint-id>`.

---

## Step 3 — Create schema and sample data

Open the Lakebase **SQL Editor**.

**3a.** Paste the whole of `schema.sql` and run it. It creates `tickets`,
`ticket_messages` (with the foreign key), two indexes, and seeds 4 tickets
across 3 statuses with 9 messages. It is safe to re-run.

**3b.** Open `grants.sql`, replace **every** `<CLIENT_ID>` with your value from
Step 1, then run it. The last query prints the granted privileges — you should
see SELECT/INSERT/UPDATE/DELETE on both tables.

**3c.** Sanity check in the SQL Editor:

```sql
SELECT t.ticket_id, t.status, t.priority, COUNT(m.message_id) AS messages
FROM tickets t LEFT JOIN ticket_messages m ON m.ticket_id = t.ticket_id
GROUP BY t.ticket_id ORDER BY t.ticket_id;
```

Every row must show 2 or more messages. **Screenshot this** — it is
submission item #4. Also screenshot the table list in the Lakebase **Data**
browser showing `tickets` and `ticket_messages`.

---

## Step 4 — Fill in `app.yaml`

Edit the three placeholders:

```yaml
- name: PGHOST
  value: 'ep-xxxx.database.us-west-2.cloud.databricks.com'
- name: PGUSER
  value: '6b215d2b-f099-4bdb-900a-60837201ecec'      # CLIENT_ID
- name: ENDPOINT_NAME
  value: 'projects/.../branches/.../endpoints/...'
```

Never put a password in here. The app calls
`generate_database_credential()` on every new pooled connection.

`PGUSER` is belt-and-braces: if you leave it out, `db.py` falls back to the
`DATABRICKS_CLIENT_ID` that Databricks Apps injects, which is the same value.
Setting it explicitly just makes the config readable.

---

## Step 5 — Test locally

```bash
python3 smoke_test.py        # 18 route/validation checks, no database needed
```

Then against real Lakebase. Copy `env.example` to `.env`, fill it in using the
same values as `app.yaml` **except** `PGUSER`, which locally is your own
Databricks email:

```bash
cp env.example .env          # then edit
source .env
pip3 install -r requirements.txt --break-system-packages
python3 init_db.py           # applies schema.sql, prints tickets + message counts
python3 app.py               # http://localhost:8000
```

If `init_db.py` fails on permissions, your own user needs a role too — run in
the SQL Editor: `SELECT databricks_create_role('you@company.com', 'user');`
then re-run the GRANT lines in `grants.sql` with your email in place of
`<CLIENT_ID>`.

Click through: create a ticket, open it, add a message, change the status,
refresh. Then stop the server (`Ctrl+C`).

---

## Step 6 — Deploy

```bash
databricks sync . /Workspace/Users/<your-email>/support-desk

databricks apps deploy support-desk \
  --source-code-path /Workspace/Users/<your-email>/support-desk
```

Takes 2–3 minutes. `databricks sync` uploads; `--source-code-path` tells the
app to run what you just uploaded rather than the template.

---

## Step 7 — Verify the deployment

Open `APP_URL` from the app page, then:

1. `APP_URL/healthz` → `{"status":"ok","database":"connected"}`
2. Seeded tickets appear on the home page.
3. Create a ticket → it opens on its own page.
4. Add a message → it appears in the thread.
5. Change status → the tag and the counters both change.
6. **Hard refresh** (Cmd/Ctrl+Shift+R) → everything you just did is still there.
   This is the proof the data lives in Lakebase, not in app memory.
7. Confirm in the Lakebase SQL Editor:
   ```sql
   SELECT * FROM tickets ORDER BY ticket_id DESC LIMIT 3;
   ```
   Your new ticket is there.

**Screenshot the deployed app** (home page with counters + queue is the best
single shot) — submission item #3.

---

## Step 8 — Submit

1. **App URL** — from the app page.
2. **Source zip** —
   `zip -r support-desk.zip . -x '*.pyc' '__pycache__/*' '.env' '.git/*' '.venv/*'`
   (`.env` is excluded, so the zip contains no secrets — `app.yaml` holds only
   a hostname and the app's client ID, neither of which is one.)
3. **App screenshot** — Step 7.
4. **Lakebase screenshot** — Step 3c.
5. **Reflection** — draft in `REFLECTION.md`, rewrite in your own words.

Grant your instructor **Can use** on the app: app page → **Permissions** →
add their email. Without this the URL 403s for them.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `permission denied for table tickets` | Grants not applied to the app's role | Re-run `grants.sql` with the correct `CLIENT_ID` |
| `permission denied for sequence tickets_ticket_id_seq` | Sequence grant missed | Run the `GRANT USAGE, SELECT ON ALL SEQUENCES` line |
| `role "<uuid>" does not exist` | `databricks_create_role` not run | Run it, case-sensitive, in double quotes |
| `password authentication failed` | Wrong `PGUSER` for the context | Deployed = CLIENT_ID, local = your email |
| `Missing environment variables: ...` | `app.yaml` placeholder left in | Fill it in, redeploy |
| App loads but 500s on every page | Endpoint scaled to zero or wrong `ENDPOINT_NAME` | Check `/healthz`, re-copy the compute resource name |
| Changes vanish on refresh | You are looking at a stale tab | Hard refresh; confirm rows via SQL Editor |
| Deploy succeeds but shows the template | `--source-code-path` omitted | Redeploy with the flag |

---

## What's in the project

```
app.py           routes, validation, error pages
repository.py    every SQL statement
db.py            connection pool + OAuth token rotation
schema.sql       DDL, indexes, seed data (re-runnable)
grants.sql       Postgres role + privileges for the service principal
init_db.py       applies schema.sql, prints a verification table
smoke_test.py    18 offline checks over SQLite, no Lakebase needed
app.yaml         Databricks Apps runtime config (no secrets)
templates/       base, index, ticket, error
static/style.css single stylesheet, no CDN dependency
docs/            README screenshots — swap in your deployed ones if you like
```
