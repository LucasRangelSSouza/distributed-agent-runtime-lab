"""Build the approved aggregate tables for the PNCP public dashboard.

Input: the pinned PNCP Kaggle release files (Parquet), passed by path.
Output: small CSV files, one per approved view, plus ``derivative.json`` with row counts, source
file hashes, and the CSV hashes. The dashboard reads only these aggregates: no free text, no
person, contact, supplier, or address field ever reaches the analytics database.

Usage:
    python build_aggregates.py --notices semantic__obt_pncp_contratacoes.parquet \
        --items trusted__pncp_contratacoes_itens.parquet --cutoff 2026-07-31 --release-version 1 \
        --output out/
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

NOTICE_COLUMNS = ["numero_controle_pncp", "modalidade_nome", "data_publicacao_pncp", "data_encerramento_proposta",
                  "valor_total_estimado", "orgao_cnpj", "orgao_razao_social"]
ITEM_COLUMNS = ["numero_controle_pncp", "item_categoria_nome", "quantidade", "unidade_medida"]
QUANTITY_BUCKETS = [("0 to 1", 0, 1), ("1 to 10", 1, 10), ("10 to 100", 10, 100), ("100 to 1,000", 100, 1000),
                    ("1,000 or more", 1000, float("inf"))]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def write_csv(path: Path, header: list[str], rows) -> int:
    count = 0
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(header)
        for row in rows:
            writer.writerow(row)
            count += 1
    return count


def month_of(array) -> list:
    """Year-month labels (YYYY-MM, UTC) of a timestamp or date column; nulls stay None."""
    return [None if v is None else f"{v.year:04d}-{v.month:02d}" for v in array.to_pylist()]


def notice_aggregates(notices_path: Path, output: Path) -> tuple[dict, pa.Table]:
    table = pq.read_table(notices_path, columns=NOTICE_COLUMNS)
    table = table.filter(pc.is_valid(table["numero_controle_pncp"]))
    # Parent grain: one row per notice, whatever the source repeated.
    indexed = table.append_column("_row", pa.array(range(table.num_rows), pa.int64()))
    first = indexed.group_by("numero_controle_pncp").aggregate([("_row", "min")])
    notices = table.take(pc.sort_indices(first["_row_min"]) and first["_row_min"])

    files: dict[str, int] = {}
    counter = Counter(v for v in notices["modalidade_nome"].to_pylist())
    files["pncp_modality"] = write_csv(output / "pncp_modality.csv", ["modality", "notices"],
                                       [(k or "Not informed", n) for k, n in counter.most_common()])
    months = month_of(notices["data_publicacao_pncp"])
    files["pncp_notices_by_month"] = write_csv(output / "pncp_notices_by_month.csv", ["month", "notices"],
                                               sorted(Counter(m for m in months if m).items()))
    deadline = notices["data_encerramento_proposta"]
    with_deadline = int(pc.sum(pc.cast(pc.is_valid(deadline), pa.int64())).as_py() or 0)
    dl_months = Counter(m for m in month_of(deadline) if m)
    files["pncp_deadlines_by_month"] = write_csv(output / "pncp_deadlines_by_month.csv", ["month", "notices_with_deadline"],
                                                 sorted(dl_months.items()))
    value_by_year: dict[str, list] = defaultdict(lambda: [0, 0.0])
    for month, value in zip(months, notices["valor_total_estimado"].to_pylist()):
        if month and value is not None and float(value) >= 0:
            bucket = value_by_year[month[:4]]
            bucket[0] += 1
            bucket[1] += float(value)
    files["pncp_estimated_value_by_year"] = write_csv(
        output / "pncp_estimated_value_by_year.csv", ["year", "notices_with_value", "estimated_value_brl"],
        [(y, c, round(v, 2)) for y, (c, v) in sorted(value_by_year.items())])
    facts = {"notices": len(notices), "notices_with_deadline": with_deadline,
             "organizations": len({c for c in notices["orgao_cnpj"].to_pylist() if c})}
    return {"files": files, "facts": facts}, notices


def item_aggregates(items_path: Path, notices: pa.Table, output: Path) -> dict:
    notice_keys = notices["numero_controle_pncp"]
    org_by_key = pa.table({"key": notice_keys, "org": notices["orgao_razao_social"]})
    key_set = notice_keys
    categories: Counter = Counter()
    unit_bucket: dict[tuple[str, str], int] = defaultdict(int)
    org_items: Counter = Counter()
    total_items = 0
    parquet = pq.ParquetFile(items_path)
    for batch in parquet.iter_batches(batch_size=500_000, columns=ITEM_COLUMNS):
        table = pa.Table.from_batches([batch])
        total_items += table.num_rows
        categories.update(table["item_categoria_nome"].to_pylist())
        quantity = pc.cast(table["quantidade"], pa.float64(), safe=False)
        units = table["unidade_medida"].to_pylist()
        for unit, q in zip(units, quantity.to_pylist()):
            if q is None or q < 0:
                continue
            for label, low, high in QUANTITY_BUCKETS:
                if low <= q < high:
                    unit_bucket[((unit or "Not informed").strip().upper()[:40], label)] += 1
                    break
        positions = pc.index_in(table["numero_controle_pncp"], value_set=key_set)
        matched = table.filter(pc.is_valid(positions))
        if matched.num_rows:
            idx = pc.drop_null(positions)
            org_items.update(pc.take(org_by_key["org"], idx).to_pylist())
    files: dict[str, int] = {}
    files["pncp_item_categories"] = write_csv(output / "pncp_item_categories.csv", ["category", "items"],
                                              [(k or "Not informed", n) for k, n in categories.most_common(30)])
    unit_totals: Counter = Counter()
    for (unit, _), n in unit_bucket.items():
        unit_totals[unit] += n
    top_units = [u for u, _ in unit_totals.most_common(10)]
    files["pncp_item_quantity_by_unit"] = write_csv(
        output / "pncp_item_quantity_by_unit.csv", ["unit", "quantity_range", "items"],
        [(u, label, unit_bucket.get((u, label), 0)) for u in top_units for label, _, _ in QUANTITY_BUCKETS])
    files["pncp_organization_items"] = write_csv(output / "pncp_organization_items.csv", ["organization", "items"],
                                                 [(k or "Not informed", n) for k, n in org_items.most_common(25)])
    return {"files": files, "facts": {"items": total_items}}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--notices", type=Path, required=True)
    parser.add_argument("--items", type=Path, required=True)
    parser.add_argument("--cutoff", required=True)
    parser.add_argument("--release-version", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    notice_result, notices = notice_aggregates(args.notices, args.output)
    item_result = item_aggregates(args.items, notices, args.output)
    facts = {**notice_result["facts"], **item_result["facts"]}
    rows = [("Data cutoff", args.cutoff), ("Release version", args.release_version),
            ("Notices (parent grain)", facts["notices"]), ("Items", facts["items"]),
            ("Distinct organizations", facts["organizations"]),
            ("Notices with a proposal deadline", facts["notices_with_deadline"])]
    write_csv(args.output / "pncp_release_facts.csv", ["fact", "value"], rows)
    csvs = {p.name: sha256(p) for p in sorted(args.output.glob("*.csv"))}
    derivative = {
        "cutoff": args.cutoff, "release_version": args.release_version, "facts": facts,
        "row_counts": {**notice_result["files"], **item_result["files"]},
        "sources": {"notices": {"file": args.notices.name, "sha256": sha256(args.notices)},
                    "items": {"file": args.items.name, "sha256": sha256(args.items)}},
        "csv_sha256": csvs,
    }
    (args.output / "derivative.json").write_text(json.dumps(derivative, indent=2), encoding="utf-8")
    print(json.dumps({"facts": facts, "csv": sorted(csvs)}, indent=2))


if __name__ == "__main__":
    main()
