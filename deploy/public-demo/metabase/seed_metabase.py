"""Versioned Metabase bootstrap for the public-demo profile.

Runs inside the private data network (``docker compose run --rm metabase-seed``)
and never through the public edge. It is idempotent by object name:

1. completes first-run setup with the operator account from the ignored .env;
2. registers the analytics database with the read-only ``metabase_reader`` role;
3. waits for the schema sync to expose the one approved view;
4. creates two structured (non-SQL) questions over that view;
5. creates the public dashboard and enables its public link;
6. prints the public UUID, which the operator copies into PUBLIC_DASHBOARD_UUID.

``--revoke`` removes the dashboard's public link instead.

Only the Python standard library is used. Secrets are read from environment
variables and are never printed.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

SEED_VERSION = "public-demo-dashboard-v1"
DATABASE_NAME = "Public demo analytics (read-only)"
APPROVED_SCHEMA = "approved"
APPROVED_VIEW = "municipality_education_finance"
DASHBOARD_NAME = "Municipality education finance"


def dashboard_description() -> str:
    """State the actual loaded source; ANALYTICS_SOURCE controls what init loaded, not this label."""
    source = os.environ.get("ANALYTICS_SOURCE", "fixture")
    if source == "release":
        origin = (
            "Public FNDE SIOPE / IBGE derivative from the lucasrangelss/brazil-education-data-lake "
            "Kaggle release, hash-verified before load. Declared values, not audited."
        )
    else:
        origin = "Synthetic fixture data. Not an official statistic."
    return f"{origin} Public-demo profile, seed version {SEED_VERSION}."
TABLE_CARD = "Approved view: municipality-year rows"
TREND_CARD = "Average investment per basic education student by year"


class Metabase:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.session: str | None = None

    def call(self, method: str, path: str, body: Any = None, expect_json: bool = True) -> Any:
        data = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {"Content-Type": "application/json"}
        if self.session:
            headers["X-Metabase-Session"] = self.session
        request = Request(f"{self.base_url}{path}", data=data, method=method, headers=headers)
        try:
            with urlopen(request, timeout=60) as response:
                raw = response.read()
        except HTTPError as error:
            detail = error.read()[:300].decode("utf-8", "replace")
            raise SystemExit(f"{method} {path} failed with HTTP {error.code}: {detail}") from None
        if not expect_json or not raw:
            return None
        return json.loads(raw)

    def wait_healthy(self, timeout_s: int) -> None:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            try:
                with urlopen(f"{self.base_url}/api/health", timeout=5) as response:
                    if json.loads(response.read()).get("status") == "ok":
                        return
            except (URLError, HTTPError, OSError, ValueError):
                pass
            time.sleep(5)
        raise SystemExit(f"Metabase did not report healthy within {timeout_s}s")


def env(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise SystemExit(f"missing required environment variable {name}")
    return value


def login_or_setup(mb: Metabase) -> None:
    properties = mb.call("GET", "/api/session/properties")
    email, password = env("METABASE_ADMIN_EMAIL"), env("METABASE_ADMIN_PASSWORD")
    if not properties.get("has-user-setup"):
        result = mb.call("POST", "/api/setup", {
            "token": properties["setup-token"],
            "user": {"email": email, "password": password, "first_name": "Demo", "last_name": "Operator", "site_name": "Public demo"},
            "prefs": {"site_name": "Public demo", "site_locale": "en", "allow_tracking": False},
        })
        mb.session = result["id"]
        print("setup: completed first-run setup")
    else:
        mb.session = mb.call("POST", "/api/session", {"username": email, "password": password})["id"]
        print("setup: already done, signed in")


def ensure_database(mb: Metabase) -> int:
    existing = mb.call("GET", "/api/database")
    databases = existing["data"] if isinstance(existing, dict) else existing
    for database in databases:
        if database["name"] == DATABASE_NAME:
            print(f"database: reusing id {database['id']}")
            return database["id"]
    created = mb.call("POST", "/api/database", {
        "engine": "postgres",
        "name": DATABASE_NAME,
        "details": {
            "host": env("ANALYTICS_HOST"),
            "port": 5432,
            "dbname": env("ANALYTICS_DB"),
            "user": env("ANALYTICS_READER_USER"),
            "password": env("ANALYTICS_READER_PASSWORD"),
            "ssl": False,
            "schema-filters-type": "inclusion",
            "schema-filters-patterns": APPROVED_SCHEMA,
        },
        "is_full_sync": True,
        "is_on_demand": False,
        "auto_run_queries": True,
    })
    print(f"database: created id {created['id']} with the read-only role")
    return created["id"]


def wait_for_view(mb: Metabase, database_id: int, timeout_s: int = 180) -> dict[str, Any]:
    mb.call("POST", f"/api/database/{database_id}/sync_schema", {}, expect_json=False)
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        metadata = mb.call("GET", f"/api/database/{database_id}/metadata")
        tables = [t for t in metadata.get("tables", []) if t["name"] == APPROVED_VIEW and t.get("schema") == APPROVED_SCHEMA]
        visible = sorted(f"{t.get('schema')}.{t['name']}" for t in metadata.get("tables", []))
        if tables and tables[0].get("fields"):
            print(f"sync: visible tables {visible}")
            return tables[0]
        time.sleep(3)
    raise SystemExit("sync: approved view did not appear; check the metabase_reader grants")


def find_by_name(items: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    return next((item for item in items if item.get("name") == name and not item.get("archived")), None)


def ensure_cards(mb: Metabase, database_id: int, table: dict[str, Any]) -> list[int]:
    fields = {field["name"]: field["id"] for field in table["fields"]}
    existing = mb.call("GET", "/api/card?f=all")
    definitions = [
        (TABLE_CARD, "table", {
            "source-table": table["id"],
            "order-by": [["asc", ["field", fields["year"], None]], ["asc", ["field", fields["municipality_code"], None]]],
            "limit": 200,
        }),
        (TREND_CARD, "bar", {
            "source-table": table["id"],
            "aggregation": [["avg", ["field", fields["investment_per_basic_education_student"], None]]],
            "breakout": [["field", fields["year"], None]],
        }),
    ]
    card_ids = []
    for name, display, query in definitions:
        card = find_by_name(existing, name)
        if card is None:
            card = mb.call("POST", "/api/card", {
                "name": name,
                "display": display,
                "description": f"Seed {SEED_VERSION}; synthetic fixture.",
                "visualization_settings": {},
                "dataset_query": {"type": "query", "database": database_id, "query": query},
            })
            print(f"card: created '{name}' id {card['id']}")
        else:
            print(f"card: reusing '{name}' id {card['id']}")
        card_ids.append(card["id"])
    return card_ids


def ensure_dashboard(mb: Metabase, card_ids: list[int]) -> int:
    dashboard = find_by_name(mb.call("GET", "/api/dashboard?f=all"), DASHBOARD_NAME)
    if dashboard is None:
        dashboard = mb.call("POST", "/api/dashboard", {"name": DASHBOARD_NAME, "description": dashboard_description()})
        print(f"dashboard: created id {dashboard['id']}")
    else:
        print(f"dashboard: reusing id {dashboard['id']}")
    dashcards = [
        {"id": -1, "card_id": card_ids[1], "row": 0, "col": 0, "size_x": 12, "size_y": 6, "parameter_mappings": [], "visualization_settings": {}},
        {"id": -2, "card_id": card_ids[0], "row": 6, "col": 0, "size_x": 24, "size_y": 10, "parameter_mappings": [], "visualization_settings": {}},
    ]
    mb.call("PUT", f"/api/dashboard/{dashboard['id']}", {"dashcards": dashcards})
    return dashboard["id"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--revoke", action="store_true", help="remove the dashboard public link and exit")
    parser.add_argument("--wait", type=int, default=600, help="seconds to wait for Metabase health")
    args = parser.parse_args()

    mb = Metabase(os.environ.get("MB_URL", "http://metabase:3000"))
    mb.wait_healthy(args.wait)
    login_or_setup(mb)

    if args.revoke:
        dashboard = find_by_name(mb.call("GET", "/api/dashboard?f=all"), DASHBOARD_NAME)
        if dashboard is None:
            print("revoke: dashboard not found; nothing to revoke")
            return 0
        mb.call("DELETE", f"/api/dashboard/{dashboard['id']}/public_link", expect_json=False)
        print(f"revoke: public link removed from dashboard {dashboard['id']}; set PUBLIC_DASHBOARD_UUID to the zero UUID and recreate nginx")
        return 0

    if not mb.call("GET", "/api/session/properties").get("enable-public-sharing"):
        raise SystemExit("public sharing is disabled; the compose file sets MB_ENABLE_PUBLIC_SHARING=true")
    database_id = ensure_database(mb)
    table = wait_for_view(mb, database_id)
    card_ids = ensure_cards(mb, database_id, table)
    dashboard_id = ensure_dashboard(mb, card_ids)
    public_uuid = mb.call("POST", f"/api/dashboard/{dashboard_id}/public_link", {})["uuid"]
    print(json.dumps({"seed_version": SEED_VERSION, "dashboard_id": dashboard_id, "public_uuid": public_uuid, "public_path": f"/public/dashboard/{public_uuid}"}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
