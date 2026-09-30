"""Idempotent Metabase bootstrap for the PNCP public dashboard (clean-room, structured questions only).

Runs inside the private data network. It registers nothing new about credentials: it signs in with the
operator account, reuses the read-only analytics database, waits for the approved PNCP views, creates
eight structured (non-SQL) questions and one dashboard named "PNCP public procurement research",
enables its public link, and prints the public UUID for the edge allowlist.

Only the Python standard library is used. Secrets come from the environment and are never printed.
"""
from __future__ import annotations

import json
import os
import sys
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

SEED_VERSION = "pncp-dashboard-v1"
DATABASE_NAME = "Public demo analytics (read-only)"
DASHBOARD_NAME = "PNCP public procurement research"
VIEWS = ["pncp_release_facts", "pncp_modality", "pncp_notices_by_month", "pncp_deadlines_by_month",
         "pncp_estimated_value_by_year", "pncp_item_categories", "pncp_item_quantity_by_unit", "pncp_organization_items"]


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
            with urlopen(request, timeout=90) as response:
                raw = response.read()
        except HTTPError as error:
            detail = error.read()[:300].decode("utf-8", "replace")
            raise SystemExit(f"{method} {path} failed with HTTP {error.code}: {detail}") from None
        if not expect_json or not raw:
            return None
        return json.loads(raw)


def env(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise SystemExit(f"missing required environment variable {name}")
    return value


def wait_healthy(mb: Metabase, timeout_s: int = 180) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with urlopen(f"{mb.base_url}/api/health", timeout=5) as response:
                if json.loads(response.read()).get("status") == "ok":
                    return
        except (URLError, HTTPError, OSError, ValueError):
            pass
        time.sleep(5)
    raise SystemExit("Metabase did not report healthy")


def database_id(mb: Metabase) -> int:
    existing = mb.call("GET", "/api/database")
    for database in existing["data"] if isinstance(existing, dict) else existing:
        if database["name"] == DATABASE_NAME:
            return database["id"]
    raise SystemExit("analytics database is not registered; run the base seed first")


def wait_for_views(mb: Metabase, db_id: int, timeout_s: int = 240) -> dict[str, dict[str, Any]]:
    def present() -> dict[str, dict[str, Any]] | None:
        metadata = mb.call("GET", f"/api/database/{db_id}/metadata")
        tables = {t["name"]: t for t in metadata.get("tables", []) if t.get("schema") == "approved"}
        return {v: tables[v] for v in VIEWS} if all(v in tables and tables[v].get("fields") for v in VIEWS) else None

    found = present()
    if found:  # already synced: skip a sync that would open extra reader connections
        return found
    mb.call("POST", f"/api/database/{db_id}/sync_schema", {}, expect_json=False)
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        metadata = mb.call("GET", f"/api/database/{db_id}/metadata")
        tables = {t["name"]: t for t in metadata.get("tables", []) if t.get("schema") == "approved"}
        if all(v in tables and tables[v].get("fields") for v in VIEWS):
            return {v: tables[v] for v in VIEWS}
        time.sleep(4)
    raise SystemExit("the approved PNCP views did not appear after sync")


def field(table: dict[str, Any], name: str) -> list:
    fid = next(f["id"] for f in table["fields"] if f["name"] == name)
    return ["field", fid, None]


def questions(views: dict[str, dict[str, Any]]) -> list[tuple[str, str, str, dict[str, Any]]]:
    """(name, display, view, structured query)"""
    v = views
    return [
        ("Coverage: release facts", "table", "pncp_release_facts", {"source-table": v["pncp_release_facts"]["id"]}),
        ("Notices published per month", "line", "pncp_notices_by_month", {
            "source-table": v["pncp_notices_by_month"]["id"],
            "aggregation": [["sum", field(v["pncp_notices_by_month"], "notices")]],
            "breakout": [field(v["pncp_notices_by_month"], "month")]}),
        ("Notices by modality", "bar", "pncp_modality", {
            "source-table": v["pncp_modality"]["id"],
            "aggregation": [["sum", field(v["pncp_modality"], "notices")]],
            "breakout": [field(v["pncp_modality"], "modality")]}),
        ("Items by controlled category (item level)", "bar", "pncp_item_categories", {
            "source-table": v["pncp_item_categories"]["id"],
            "aggregation": [["sum", field(v["pncp_item_categories"], "items")]],
            "breakout": [field(v["pncp_item_categories"], "category")]}),
        ("Contracting organizations by item count (top 25)", "bar", "pncp_organization_items", {
            "source-table": v["pncp_organization_items"]["id"],
            "aggregation": [["sum", field(v["pncp_organization_items"], "items")]],
            "breakout": [field(v["pncp_organization_items"], "organization")]}),
        ("Item quantities by unit (item level, non-negative)", "bar", "pncp_item_quantity_by_unit", {
            "source-table": v["pncp_item_quantity_by_unit"]["id"],
            "aggregation": [["sum", field(v["pncp_item_quantity_by_unit"], "items")]],
            "breakout": [field(v["pncp_item_quantity_by_unit"], "unit"), field(v["pncp_item_quantity_by_unit"], "quantity_range")]}),
        ("Proposal deadlines per month (only where a deadline is recorded)", "line", "pncp_deadlines_by_month", {
            "source-table": v["pncp_deadlines_by_month"]["id"],
            "aggregation": [["sum", field(v["pncp_deadlines_by_month"], "notices_with_deadline")]],
            "breakout": [field(v["pncp_deadlines_by_month"], "month")]}),
        ("Estimated value by year (parent notice level, BRL)", "bar", "pncp_estimated_value_by_year", {
            "source-table": v["pncp_estimated_value_by_year"]["id"],
            "aggregation": [["sum", field(v["pncp_estimated_value_by_year"], "estimated_value_brl")]],
            "breakout": [field(v["pncp_estimated_value_by_year"], "year")]}),
    ]


def banner_text() -> str:
    cutoff = os.environ.get("PNCP_CUTOFF", "2026-07-31")
    version = os.environ.get("PNCP_RELEASE_VERSION", "1")
    return (f"**Scope:** aggregates from the public PNCP Kaggle catalogue, release {version}, data through {cutoff}. "
            "Counts describe the released records only; they do not certify current procurement status or national "
            "completeness. Missing values stay missing. Estimated value sums each notice once (parent level), never once per item.")


def main() -> None:
    mb = Metabase(env("MB_URL"))
    wait_healthy(mb)
    mb.session = mb.call("POST", "/api/session", {"username": env("METABASE_ADMIN_EMAIL"), "password": env("METABASE_ADMIN_PASSWORD")})["id"]
    db_id = database_id(mb)
    views = wait_for_views(mb, db_id)
    existing = mb.call("GET", "/api/card?f=all")
    card_ids = []
    for name, display, _, query in questions(views):
        card = next((c for c in existing if c.get("name") == name and not c.get("archived")), None)
        if card is None:
            card = mb.call("POST", "/api/card", {
                "name": name, "display": display, "description": f"Seed {SEED_VERSION}.",
                "visualization_settings": {"stackable.stack_type": "stacked"} if "unit" in name.lower() else {},
                "dataset_query": {"type": "query", "database": db_id, "query": query}})
            print(f"card: created '{name}' id {card['id']}")
        else:
            print(f"card: reusing '{name}' id {card['id']}")
        card_ids.append(card["id"])
    dashboards = mb.call("GET", "/api/dashboard?f=all")
    dash = next((d for d in dashboards if d.get("name") == DASHBOARD_NAME and not d.get("archived")), None)
    if dash is None:
        dash = mb.call("POST", "/api/dashboard", {"name": DASHBOARD_NAME,
                                                  "description": f"Public PNCP release aggregates. Seed {SEED_VERSION}."})
    dashcards = [{"id": -1, "card_id": None, "row": 0, "col": 0, "size_x": 24, "size_y": 3, "parameter_mappings": [],
                  "visualization_settings": {"virtual_card": {"name": None, "display": "text", "visualization_settings": {},
                                                               "dataset_query": {}, "archived": False},
                                             "text": banner_text()}}]
    order = [0, 1, 2, 3, 4, 5, 6, 7]  # facts, per-month, modality, categories, orgs, quantities, deadlines, value
    placement = [(3, 0, 24, 6), (9, 0, 12, 7), (9, 12, 12, 7), (16, 0, 12, 8), (16, 12, 12, 8), (24, 0, 24, 9),
                 (33, 0, 12, 7), (33, 12, 12, 7)]
    for i, (row, col, w, h) in zip(order, placement):
        dashcards.append({"id": -(i + 2), "card_id": card_ids[i], "row": row, "col": col, "size_x": w, "size_y": h,
                          "parameter_mappings": [], "visualization_settings": {}})
    mb.call("PUT", f"/api/dashboard/{dash['id']}", {"dashcards": dashcards})
    public = mb.call("POST", f"/api/dashboard/{dash['id']}/public_link", {})
    print(f"public_dashboard_uuid={public['uuid']}")


if __name__ == "__main__":
    main()
