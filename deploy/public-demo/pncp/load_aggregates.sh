#!/bin/sh
# Loads the PNCP aggregate CSVs into the analytics database and publishes them as approved views.
# Run inside the analytics database container as the database owner, with the CSVs mounted at
# /pncp (read-only). Idempotent: it recreates the staging tables and the views each time.
set -eu
: "${POSTGRES_USER:?}" "${POSTGRES_DB:?}"
dir="${PNCP_DIR:-/pncp}"
expected=$(sed -n 's/.*"pncp_release_facts.csv": "\([0-9a-f]*\)".*/\1/p' "$dir/derivative.json")
actual=$(sha256sum "$dir/pncp_release_facts.csv" | cut -d' ' -f1)
if [ -z "$expected" ] || [ "$expected" != "$actual" ]; then
  echo "aggregate hash mismatch for pncp_release_facts.csv" >&2
  exit 1
fi

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<SQL
CREATE SCHEMA IF NOT EXISTS pncp_staging;
DROP VIEW IF EXISTS approved.pncp_release_facts, approved.pncp_modality, approved.pncp_notices_by_month,
  approved.pncp_deadlines_by_month, approved.pncp_estimated_value_by_year, approved.pncp_item_categories,
  approved.pncp_item_quantity_by_unit, approved.pncp_organization_items;
DROP TABLE IF EXISTS pncp_staging.release_facts, pncp_staging.modality, pncp_staging.notices_by_month,
  pncp_staging.deadlines_by_month, pncp_staging.estimated_value_by_year, pncp_staging.item_categories,
  pncp_staging.item_quantity_by_unit, pncp_staging.organization_items;

CREATE TABLE pncp_staging.release_facts (fact text PRIMARY KEY, value text NOT NULL);
CREATE TABLE pncp_staging.modality (modality text PRIMARY KEY, notices bigint NOT NULL CHECK (notices >= 0));
CREATE TABLE pncp_staging.notices_by_month (month text PRIMARY KEY, notices bigint NOT NULL CHECK (notices >= 0));
CREATE TABLE pncp_staging.deadlines_by_month (month text PRIMARY KEY, notices_with_deadline bigint NOT NULL CHECK (notices_with_deadline >= 0));
CREATE TABLE pncp_staging.estimated_value_by_year (year text PRIMARY KEY, notices_with_value bigint NOT NULL, estimated_value_brl numeric(20,2) NOT NULL CHECK (estimated_value_brl >= 0));
CREATE TABLE pncp_staging.item_categories (category text PRIMARY KEY, items bigint NOT NULL CHECK (items >= 0));
CREATE TABLE pncp_staging.item_quantity_by_unit (unit text NOT NULL, quantity_range text NOT NULL, items bigint NOT NULL CHECK (items >= 0), PRIMARY KEY (unit, quantity_range));
CREATE TABLE pncp_staging.organization_items (organization text PRIMARY KEY, items bigint NOT NULL CHECK (items >= 0));

\copy pncp_staging.release_facts FROM '$dir/pncp_release_facts.csv' WITH (FORMAT csv, HEADER true)
\copy pncp_staging.modality FROM '$dir/pncp_modality.csv' WITH (FORMAT csv, HEADER true)
\copy pncp_staging.notices_by_month FROM '$dir/pncp_notices_by_month.csv' WITH (FORMAT csv, HEADER true)
\copy pncp_staging.deadlines_by_month FROM '$dir/pncp_deadlines_by_month.csv' WITH (FORMAT csv, HEADER true)
\copy pncp_staging.estimated_value_by_year FROM '$dir/pncp_estimated_value_by_year.csv' WITH (FORMAT csv, HEADER true)
\copy pncp_staging.item_categories FROM '$dir/pncp_item_categories.csv' WITH (FORMAT csv, HEADER true)
\copy pncp_staging.item_quantity_by_unit FROM '$dir/pncp_item_quantity_by_unit.csv' WITH (FORMAT csv, HEADER true)
\copy pncp_staging.organization_items FROM '$dir/pncp_organization_items.csv' WITH (FORMAT csv, HEADER true)

CREATE VIEW approved.pncp_release_facts AS SELECT fact, value FROM pncp_staging.release_facts;
CREATE VIEW approved.pncp_modality AS SELECT modality, notices FROM pncp_staging.modality;
CREATE VIEW approved.pncp_notices_by_month AS SELECT month, notices FROM pncp_staging.notices_by_month;
CREATE VIEW approved.pncp_deadlines_by_month AS SELECT month, notices_with_deadline FROM pncp_staging.deadlines_by_month;
CREATE VIEW approved.pncp_estimated_value_by_year AS SELECT year, notices_with_value, estimated_value_brl FROM pncp_staging.estimated_value_by_year;
CREATE VIEW approved.pncp_item_categories AS SELECT category, items FROM pncp_staging.item_categories;
CREATE VIEW approved.pncp_item_quantity_by_unit AS SELECT unit, quantity_range, items FROM pncp_staging.item_quantity_by_unit;
CREATE VIEW approved.pncp_organization_items AS SELECT organization, items FROM pncp_staging.organization_items;

GRANT SELECT ON ALL TABLES IN SCHEMA approved TO metabase_reader;
SQL
echo "pncp aggregates loaded"
