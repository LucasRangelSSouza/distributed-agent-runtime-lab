#!/usr/bin/env sh
# Build the locally built public-demo images and print their image IDs.
# Tags and pins come from deploy/public-demo/versions.env so Compose and this
# script never disagree. compose.yaml labels these images as local builds; the
# strict release policy check rejects them until registry digests replace them.
set -eu
repo="$(cd "$(dirname "$0")/.." && pwd)"
demo="$repo/deploy/public-demo"
# shellcheck disable=SC1091
. "$demo/versions.env"
docker build --tag "$RUNTIME_IMAGE" "$repo"
docker build --tag "$RAG_IMAGE" --build-arg "RUNTIME_IMAGE=$RUNTIME_IMAGE" "$demo/rag-fixture"
docker build --tag "$AIRFLOW_IMAGE" \
  --build-arg "AIRFLOW_IMAGE=$AIRFLOW_BASE_IMAGE" \
  --build-arg "DATA_MAP_REPO=$DATA_MAP_REPO" \
  --build-arg "DATA_MAP_COMMIT=$DATA_MAP_COMMIT" \
  --build-arg "DATA_MAP_ARCHIVE_SHA256=$DATA_MAP_ARCHIVE_SHA256" \
  --build-arg "MLOPS_REPO=$MLOPS_REPO" \
  --build-arg "MLOPS_COMMIT=$MLOPS_COMMIT" \
  --build-arg "MLOPS_ARCHIVE_SHA256=$MLOPS_ARCHIVE_SHA256" \
  "$demo/airflow"
for image in "$RUNTIME_IMAGE" "$RAG_IMAGE" "$AIRFLOW_IMAGE"; do
  printf '%s %s\n' "$image" "$(docker image inspect --format '{{.Id}}' "$image")"
done
