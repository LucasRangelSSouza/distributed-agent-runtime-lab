#!/bin/sh
# Runs once, on first start of an empty analytics volume, as the database owner.
# Loads the approved-column data into a private staging schema, publishes one
# approved view, and creates the unprivileged role that Metabase uses.
#
# ANALYTICS_SOURCE=release  /release/municipality_education_finance.csv, written
#                           by scripts/public_demo_load_release.py after it
#                           verified the pinned manifest and file hashes
# ANALYTICS_SOURCE=fixture  /fixture/municipality_finance_fixture.csv (synthetic)
set -eu

: "${ANALYTICS_READER_PASSWORD:?ANALYTICS_READER_PASSWORD is required}"
case "${ANALYTICS_SOURCE:-}" in
  release)
    data_file=/release/municipality_education_finance.csv
    # The loader recorded the CSV hash; refuse a derivative edited after it ran.
    expected_sha=$(sed -n 's/.*"csv_sha256": "\([0-9a-f]*\)".*/\1/p' /release/derivative.json)
    actual_sha=$(sha256sum "$data_file" | cut -d' ' -f1)
    if [ -z "$expected_sha" ] || [ "$expected_sha" != "$actual_sha" ]; then
      echo "release derivative hash mismatch: expected '$expected_sha', got '$actual_sha'" >&2
      exit 1
    fi
    source_label="verified release derivative, csv sha256 $actual_sha"
    ;;
  fixture)
    data_file=/fixture/municipality_finance_fixture.csv
    source_label="synthetic fixture"
    ;;
  *)
    echo "ANALYTICS_SOURCE must be 'release' or 'fixture'" >&2
    exit 1
    ;;
esac
if [ ! -s "$data_file" ]; then
  echo "missing $data_file; run scripts/public_demo_load_release.py or set ANALYTICS_SOURCE=fixture" >&2
  exit 1
fi
echo "analytics init: loading $source_label from $data_file"

psql -v ON_ERROR_STOP=1 \
  --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v dbname="$POSTGRES_DB" \
  -v reader_password="$ANALYTICS_READER_PASSWORD" \
  -v data_file="$data_file" \
  -v source_label="$source_label" <<'SQL'
REVOKE ALL ON DATABASE :"dbname" FROM PUBLIC;
REVOKE ALL ON SCHEMA public FROM PUBLIC;

CREATE SCHEMA staging;
CREATE TABLE staging.municipality_finance (
    municipality_code integer NOT NULL,
    year smallint NOT NULL,
    state_code char(2) NOT NULL,
    population integer NOT NULL CHECK (population > 0),
    mde_minimum_share_pct numeric(5, 2) NOT NULL,
    investment_per_basic_education_student numeric(12, 2) NOT NULL,
    loaded_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (municipality_code, year)
);
-- Server-side COPY: the bootstrap owner is the cluster superuser and the file
-- is a read-only bind mount readable by the postgres process.
COPY staging.municipality_finance (municipality_code, year, state_code, population, mde_minimum_share_pct, investment_per_basic_education_student)
    FROM :'data_file' WITH (FORMAT csv, HEADER true);

CREATE SCHEMA approved;
COMMENT ON SCHEMA approved IS 'Only views listed in the public-demo allowlist.';
CREATE VIEW approved.municipality_education_finance AS
SELECT municipality_code,
       year,
       state_code,
       population,
       mde_minimum_share_pct,
       investment_per_basic_education_student
FROM staging.municipality_finance;
COMMENT ON VIEW approved.municipality_education_finance IS :'source_label';

CREATE ROLE metabase_reader LOGIN PASSWORD :'reader_password'
    NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION CONNECTION LIMIT 5;
ALTER ROLE metabase_reader SET default_transaction_read_only = on;
ALTER ROLE metabase_reader SET statement_timeout = '5s';
GRANT CONNECT ON DATABASE :"dbname" TO metabase_reader;
GRANT USAGE ON SCHEMA approved TO metabase_reader;
GRANT SELECT ON approved.municipality_education_finance TO metabase_reader;
SQL
