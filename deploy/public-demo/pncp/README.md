# PNCP public dashboard (clean-room)

A read-only Metabase dashboard, **PNCP public procurement research**, built only from the pinned PNCP Kaggle release. It shares the public-demo analytics database and Metabase instance but exposes its own approved views.

| Step | File | What it does |
|---|---|---|
| 1 | `build_aggregates.py` | Reads the pinned semantic notices Parquet and the trusted items Parquet, deduplicates to parent notice grain, and writes eight small aggregate CSVs plus `derivative.json` (row counts, source and CSV SHA-256) |
| 2 | `load_aggregates.sh` | Verifies the CSV hash, loads the aggregates into a private staging schema, and publishes eight `approved.pncp_*` views to the read-only role |
| 3 | `seed_pncp_dashboard.py` | Creates eight structured (non-SQL) questions and the dashboard, enables its public link, prints the UUID for the edge allowlist |

## Safety rules

- No free text, person, contact, supplier, or address field enters the analytics database. Item descriptions are not aggregated. Organization names are public authority names taken from the notice record.
- Estimated value sums each parent notice once. It is never summed per item.
- Missing deadlines stay missing. No deadline is inferred.
- Only the single public dashboard route is allowed through the edge; login, editor, query builder, APIs, and saved questions stay denied.

## Reproduce

```bash
python build_aggregates.py --notices semantic__obt_pncp_contratacoes.parquet \
  --items trusted__pncp_contratacoes_itens.parquet --cutoff 2026-07-31 --release-version 1 --output out/
```

`derivative.json` records the source hashes so a reader can match them against the release manifest.
