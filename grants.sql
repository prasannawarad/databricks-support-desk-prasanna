-- Run this in the Lakebase SQL Editor BEFORE deploying.
-- Replace every <CLIENT_ID> with the app's DATABRICKS_CLIENT_ID
-- (Databricks App → Environment tab). Keep the double quotes.

CREATE EXTENSION IF NOT EXISTS databricks_auth;

-- Postgres role for the app's service principal, authenticated by OAuth
SELECT databricks_create_role('<CLIENT_ID>', 'service_principal');

GRANT CONNECT ON DATABASE databricks_postgres TO "<CLIENT_ID>";
GRANT USAGE  ON SCHEMA public                 TO "<CLIENT_ID>";

-- Table and sequence access (service principals inherit nothing by default)
GRANT SELECT, INSERT, UPDATE, DELETE ON tickets         TO "<CLIENT_ID>";
GRANT SELECT, INSERT, UPDATE, DELETE ON ticket_messages TO "<CLIENT_ID>";
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public   TO "<CLIENT_ID>";

-- Anything created later in this schema is covered too
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO "<CLIENT_ID>";
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO "<CLIENT_ID>";

-- Verify
SELECT table_name, privilege_type
FROM information_schema.role_table_grants
WHERE grantee = '<CLIENT_ID>'
ORDER BY table_name, privilege_type;
