# [tenant]
#!/bin/bash
# Two-role RLS setup, run once on a fresh Postgres volume (docker-entrypoint-initdb.d).
#   myapp_admin: BYPASSRLS, owns DB/schema/tables — migrations, Django admin, cross-tenant jobs
#   myapp_app:   NOBYPASSRLS, DML only — all tenant-scoped web traffic
# Prod/test: run the SQL below by hand with real passwords. The app role must never
# be SUPERUSER, BYPASSRLS or a table owner, or every policy is silently inert.
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v app_pw="${APP_DB_PASSWORD:-myapp_app}" -v admin_pw="${ADMIN_DB_PASSWORD:-myapp_admin}" <<-'EOSQL'
	-- psql doesn't interpolate :'vars' inside DO $$ blocks, so build each CREATE ROLE
	-- as a string and \gexec it; WHERE NOT EXISTS makes it idempotent.
	SELECT format('CREATE ROLE myapp_admin LOGIN PASSWORD %L BYPASSRLS CREATEDB', :'admin_pw')
	WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'myapp_admin')
	\gexec
	SELECT format('CREATE ROLE myapp_app LOGIN PASSWORD %L NOBYPASSRLS', :'app_pw')
	WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'myapp_app')
	\gexec

	-- pytest connects as admin and drops/recreates the test DB: it needs ownership.
	SELECT format('ALTER DATABASE %I OWNER TO myapp_admin', current_database())
	\gexec
	ALTER SCHEMA public OWNER TO myapp_admin;

	GRANT USAGE ON SCHEMA public TO myapp_app;
	GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES    IN SCHEMA public TO myapp_app;
	GRANT USAGE, SELECT                  ON ALL SEQUENCES IN SCHEMA public TO myapp_app;
	-- Tables created later by migrations (as admin) are usable by the app at once.
	ALTER DEFAULT PRIVILEGES FOR ROLE myapp_admin IN SCHEMA public
	    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES    TO myapp_app;
	ALTER DEFAULT PRIVILEGES FOR ROLE myapp_admin IN SCHEMA public
	    GRANT USAGE, SELECT                  ON SEQUENCES TO myapp_app;
EOSQL
# [/tenant]
