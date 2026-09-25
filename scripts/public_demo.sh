#!/usr/bin/env sh
# Thin wrapper so every public-demo command uses the same files:
#   scripts/public_demo.sh up -d
#   scripts/public_demo.sh ps
#   scripts/public_demo.sh --profile seed run --rm metabase-seed
set -eu
root="$(cd "$(dirname "$0")/.." && pwd)/deploy/public-demo"
exec docker compose \
  --project-directory "$root" \
  -f "$root/compose.yaml" \
  --env-file "$root/versions.env" \
  --env-file "$root/.env" \
  "$@"
