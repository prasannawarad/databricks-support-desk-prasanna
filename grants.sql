-- Lakebase permissions for the Databricks App service principal
-- Database: databricks_postgres
-- Branch: production
-- Project: new-database

CREATE EXTENSION IF NOT EXISTS databricks_auth;

-- Create an OAuth-enabled Postgres role for the Databricks App.
-- This must be the App's DATABRICKS_CLIENT_ID.
SELECT databricks_create_role(
    '5b192094-9293-4ebd-8734-7f77c0ffd2a1',
    'SERVICE_PRINCIPAL'
);

-- Database and schema access
GRANT CONNECT ON DATABASE databricks_postgres
    TO "5b192094-9293-4ebd-8734-7f77c0ffd2a1";

GRANT USAGE ON SCHEMA public
    TO "5b192094-9293-4ebd-8734-7f77c0ffd2a1";

-- Ticket table permissions
GRANT SELECT, INSERT, UPDATE, DELETE
    ON TABLE tickets
    TO "5b192094-9293-4ebd-8734-7f77c0ffd2a1";

-- Ticket message permissions
GRANT SELECT, INSERT, UPDATE, DELETE
    ON TABLE ticket_messages
    TO "5b192094-9293-4ebd-8734-7f77c0ffd2a1";

-- Needed if your tables use SERIAL/IDENTITY sequences
GRANT USAGE, SELECT
    ON ALL SEQUENCES IN SCHEMA public
    TO "5b192094-9293-4ebd-8734-7f77c0ffd2a1";

-- Automatically grant table permissions to tables created later
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES
    TO "5b192094-9293-4ebd-8734-7f77c0ffd2a1";

-- Automatically grant sequence permissions to sequences created later
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES
    TO "5b192094-9293-4ebd-8734-7f77c0ffd2a1";