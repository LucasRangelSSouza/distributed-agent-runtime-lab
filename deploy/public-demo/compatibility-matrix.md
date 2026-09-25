# Public-demo compatibility matrix

Machine-readable pins live in `versions.env`; this file explains each one, who owns it, and its test status. Keep both in sync — a pin change here without the matching `versions.env` line (or vice versa) is a release-review defect.

| Component | Owner repo | Pin | Source | Test status |
|---|---|---|---|---|
| Test-chat frontend, gateway, worker | this repo | `RUNTIME_IMAGE=distributed-agent-runtime-lab:0.1.0-public-demo-local` | local build | Full acceptance suite (see `docs/evidence/public-demo-local-2026-09-25.md`). Replace with the GHCR digest once a `v*` tag runs the release workflow, and set `RUNTIME_IMAGE_SOURCE=registry`. |
| RAG gateway | [ai-platform-rag-observability](https://github.com/LucasRangelSSouza/ai-platform-rag-observability) v0.2.0 (real image exists, `rag-platform:0.2.0`, not yet published to a registry) | `RAG_IMAGE=rag-gateway-fixture:0.2.0-fixture-local` (**fixture stand-in, built from this repo**) | local build | Contract-level: matches the real API (`POST /v1/answer`, `GET /healthz`), tested in `tests/test_rag_fixture.py`. Not the real image. Swap: build/pull `rag-platform:0.2.0` from the owner repo (no registry push exists yet — see that repo's `MEMORY.md`), set `RAG_IMAGE`, `RAG_IMAGE_SOURCE=registry` (once pushed) or `local-build` (if built from a pinned checkout), and confirm `RAG_PORT` against its Dockerfile (`8080`, not this stand-in's `8000`) and its education-corpus CLI flags (`--education-dir`, `--release`). |
| Education dataset | [brazil-public-data-map](https://github.com/LucasRangelSSouza/brazil-public-data-map) → Kaggle `lucasrangelss/brazil-education-data-lake` | `ANALYTICS_SOURCE=release`, manifest SHA-256 `44f259602a688432dddbae6b0306a6957514a634d57d94a0abd3cff30f4b3506` | public Kaggle release, no credential needed | `scripts/public_demo_load_release.py` verifies the manifest and every file hash before writing the CSV derivative; `analytics/init/10-approved-views.sh` re-verifies the derivative's own hash record before load. Real 27,830-row release loaded and dashboarded in the 2026-09-25 run. |
| Airflow DAG examples | brazil-public-data-map `dags/education_siope_annual_update.py`; [education-finance-mlops](https://github.com/LucasRangelSSouza/education-finance-mlops) `dags/education_monitoring_demo.py` | `DATA_MAP_COMMIT`, `MLOPS_COMMIT` + archive SHA-256 in `versions.env` | GitHub codeload tarball at a pinned commit, verified by SHA-256 in the Airflow image build | Loaded with no import errors, both `is_paused = True` (2026-09-25 run). `pncp_incremental_update.py` (schedule `0 */6 * * *`, not paused by default) is deliberately excluded — see `deploy/public-demo/airflow/Dockerfile`. |
| Metabase, its metadata DB, the analytics DB, Redis, Airflow's metadata DB, the egress proxy, nginx | upstream (Metabase, PostgreSQL, Redis, Apache Airflow, Squid, nginx-unprivileged) | tag + digest in `versions.env`, recorded 2026-09-25 | `docker pull` | Full acceptance suite. |

## Reissuing pins

1. Pull the new tag, record its digest (`docker inspect --format '{{index .RepoDigests 0}}' <image>`), and update `versions.env`.
2. Update this table's "Test status" cell for that row with the date and what was rerun.
3. Run `python scripts/check_public_demo_policy.py --strict-release` — a service still on a local build without a digest fails here by design.
4. Run the full local acceptance sequence (`docs/reproduce.md` or the evidence template above) and record a new dated file under `docs/evidence/`.

No pin changes without a rerun. A stale "Test status" cell is treated as a release blocker.
