# Public-demo operator runbook

This covers the local Compose profile. **No VPS, domain, or DNS deployment exists yet.** The real host, domain, and management-access method are external inputs (spec section 14.2, `distributed-agent-runtime-lab` section 12.7) that a separate private infrastructure repository supplies after its own host-exposure review — never this one.

## First start

```powershell
python scripts/public_demo_env.py            # writes deploy/public-demo/.env with fresh random secrets; never commit it
bash scripts/public_demo_cert.sh              # writes deploy/public-demo/certs/tls.{crt,key}; never commit it
bash scripts/public_demo_load_release.py --release-dir <extracted lucasrangelss/brazil-education-data-lake v1>
bash scripts/public_demo.sh up -d --build
bash scripts/public_demo.sh --profile seed run --rm metabase-seed
```

The seed command prints a public dashboard UUID. Copy it into `deploy/public-demo/.env` as `PUBLIC_DASHBOARD_UUID`, then recreate nginx (`bash scripts/public_demo.sh up -d nginx`) — a plain `restart` reuses the old environment and will keep routing the stale UUID. Without this step the dashboard path 404s.

## Image update

1. Pull the new tag, get its digest, update `versions.env`, update `compatibility-matrix.md`'s row for that component.
2. `python scripts/check_public_demo_policy.py --strict-release` — must pass before a real deployment.
3. `bash scripts/public_demo.sh up -d --build` recreates only the services whose image or environment changed.
4. Rerun the acceptance checks (port scan, egress isolation, Metabase/Airflow boundary — see `docs/evidence/public-demo-local-2026-09-25.md` for the exact commands) and record a new dated evidence file.

## Rollback

Compose does not keep image history by name; rollback means re-pinning the previous tag/digest in `versions.env` and repeating the update steps above. Keep the previous `versions.env` values in the commit history you are rolling back to — that is the rollback record.

## Secret rotation

```powershell
python scripts/public_demo_env.py --force     # regenerates every __GENERATE__ value
bash scripts/public_demo.sh up -d             # recreate services that read the rotated values
```

Rotating `METABASE_DB_PASSWORD`, `ANALYTICS_*_PASSWORD`, or `AIRFLOW_*` requires recreating the owning database container with the new credential already applied at first init — a rotation against a database with existing data needs an `ALTER USER ... PASSWORD` issued by the operator, not just an env-var change, because these images do not re-run their init scripts against an existing volume.

## Public-link revocation

```powershell
bash scripts/public_demo.sh run --rm metabase-seed python /seed/seed_metabase.py --revoke
```

This disables the dashboard's public link in Metabase. Also clear `PUBLIC_DASHBOARD_UUID` back to the placeholder zero UUID in `.env` and recreate nginx, so the old path stops being routed even if the link were re-enabled by mistake.

## Backup and restore

Durable state lives in three named volumes: `metabase-db-data`, `analytics-db-data`, `airflow-db-data`. Back up with `docker run --rm -v <volume>:/data -v $(pwd):/backup alpine tar czf /backup/<volume>-<date>.tar.gz -C /data .` for each. Restore by reversing the tar into a fresh volume before the owning service starts. Redis holds only ephemeral runtime coordination state (idempotency keys, conversation checkpoints) and is not backed up; losing it loses in-flight conversations, not the analytics or dashboard data.

## Log review

`docker compose -f deploy/public-demo/compose.yaml logs nginx` for edge access; the access log format excludes request bodies and `Authorization` headers by construction (see `nginx/snippets/security-headers.conf` and the log format in `nginx.conf`). Never grep for a raw prompt or answer in the RAG gateway's logs — the redaction contract in `ai-platform-rag-observability` keeps them out by default; a log line containing passage or answer text is itself a defect to report there.

## Teardown and rebuild

```powershell
bash scripts/public_demo.sh down -v      # removes containers, networks, and named volumes (destroys data)
```

Rebuild with the "First start" sequence above. `deploy/public-demo/.env`, `certs/`, and `analytics/release/*` (except `.gitkeep`) are git-ignored and regenerated locally; nothing under Git needs to change for a teardown/rebuild cycle.

## What this runbook does not cover

A public host, TLS from a real certificate authority, DNS, firewall rules beyond this Compose file's own network isolation, and anything requiring an SSH target or cloud account. Those belong to the private infrastructure repository referenced in spec section 3.2, after its own review — not here.
