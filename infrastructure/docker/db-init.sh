#!/usr/bin/env bash
# Create least-privilege database roles for PARTICIPA-GEO.
#
# Roles:
#   migrator   — owns the schema and runs Alembic migrations.
#   writer     — writes aggregated observations and results.
#   api        — read-only service role used by the FastAPI application.
#   gis_reader — read-only role used by GeoServer (WMS/WFS layers).
#
# The API never uses the migrator role. Secrets are read from environment
# variables only and are never echoed to logs or psql output.
set -euo pipefail

# Escape single quotes for a SQL string literal.
sql_escape() {
  printf '%s' "${1//\'/\'\'}"
}

create_role() {
  local role="$1" password="$2" escaped
  escaped="$(sql_escape "$password")"
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    DO \$\$
    BEGIN
      IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = '${role}') THEN
        CREATE ROLE "${role}" LOGIN PASSWORD '${escaped}';
      ELSE
        ALTER ROLE "${role}" WITH LOGIN PASSWORD '${escaped}';
      END IF;
    END
    \$\$;
EOSQL
}

create_role "$DB_MIGRATOR_USER" "$DB_MIGRATOR_PASSWORD"
create_role "$DB_WRITER_USER" "$DB_WRITER_PASSWORD"
create_role "$DB_API_USER" "$DB_API_PASSWORD"
create_role "$DB_GIS_READER_USER" "$DB_GIS_READER_PASSWORD"
