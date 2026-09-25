"""Maintainer-only loader for the public-demo analytics data.

It verifies a pinned education release and writes the approved-column
derivative that the analytics database loads on first start. It never needs a
Kaggle credential: the maintainer downloads the public release separately and
points this script at the local copy.

Gates, in order; any failure writes nothing:
1. SHA-256 of release_manifest.json equals the pinned value in versions.env;
2. the manifest records privacy_gate == "passed";
3. the semantic layer file exists and matches the manifest's bytes and SHA-256;
4. the semantic table has every approved column, the manifest row count,
   unique (municipality_code, year) keys, and identifier_classification ==
   "not_present" on every row.

Output (ignored by Git): deploy/public-demo/analytics/release/
    municipality_education_finance.csv   approved columns only
    derivative.json                      provenance and hashes

Usage:
    py -3.12 scripts/public_demo_load_release.py --release-dir <local release copy>
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Iterable

REPO = Path(__file__).resolve().parent.parent
DEMO_DIR = REPO / "deploy" / "public-demo"
DEFAULT_OUT = DEMO_DIR / "analytics" / "release"
MANIFEST_NAME = "release_manifest.json"
SEMANTIC_PATH = "semantic/records.parquet"
APPROVED_COLUMNS = (
    "municipality_code",
    "year",
    "state_code",
    "population",
    "mde_minimum_share_pct",
    "investment_per_basic_education_student",
)
OUTPUT_CSV = "municipality_education_finance.csv"


class ReleaseRejected(Exception):
    """The release failed a verification gate."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def read_versions(path: Path = DEMO_DIR / "versions.env") -> dict[str, str]:
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, sep, value = line.partition("=")
        if sep and not line.lstrip().startswith("#"):
            values[key.strip()] = value.strip()
    return values


def verify_manifest(release_dir: Path, expected_sha256: str) -> dict[str, Any]:
    manifest_path = release_dir / MANIFEST_NAME
    if not manifest_path.is_file():
        raise ReleaseRejected(f"{MANIFEST_NAME} not found in {release_dir}")
    actual = sha256_file(manifest_path)
    if actual != expected_sha256:
        raise ReleaseRejected(f"manifest SHA-256 {actual} does not match the pinned {expected_sha256}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("privacy_gate") != "passed":
        raise ReleaseRejected(f"manifest privacy_gate is {manifest.get('privacy_gate')!r}, not 'passed'")
    return manifest


def locate_layer(release_dir: Path, manifest: dict[str, Any], manifest_path: str = SEMANTIC_PATH) -> Path:
    entry = next((item for item in manifest.get("files", []) if item.get("path") == manifest_path), None)
    if entry is None:
        raise ReleaseRejected(f"manifest does not list {manifest_path}")
    # Kaggle flattens directories: semantic/records.parquet -> semantic_records.parquet
    candidates = [release_dir / manifest_path, release_dir / manifest_path.replace("/", "_")]
    path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if path is None:
        raise ReleaseRejected(f"{manifest_path} is listed in the manifest but missing from {release_dir}")
    if path.stat().st_size != entry.get("bytes"):
        raise ReleaseRejected(f"{path.name} size {path.stat().st_size} does not match the manifest {entry.get('bytes')}")
    actual = sha256_file(path)
    if actual != entry.get("sha256"):
        raise ReleaseRejected(f"{path.name} SHA-256 {actual} does not match the manifest {entry.get('sha256')}")
    return path


def validate_rows(columns: Iterable[str], rows: list[dict[str, Any]], expected_rows: int | None) -> None:
    missing = [column for column in APPROVED_COLUMNS if column not in set(columns)]
    if missing:
        raise ReleaseRejected(f"semantic layer is missing approved columns {missing}")
    if expected_rows is not None and len(rows) != expected_rows:
        raise ReleaseRejected(f"semantic layer has {len(rows)} rows; manifest records {expected_rows}")
    keys = set()
    for row in rows:
        if row.get("identifier_classification") != "not_present":
            raise ReleaseRejected("a row does not carry identifier_classification == 'not_present'")
        key = (row["municipality_code"], row["year"])
        if key in keys:
            raise ReleaseRejected(f"duplicate municipality-year key {key}")
        keys.add(key)
        if any(row.get(column) is None for column in APPROVED_COLUMNS):
            raise ReleaseRejected(f"null approved value in row {key}")


def read_parquet(path: Path) -> tuple[list[str], list[dict[str, Any]]]:
    try:
        import pyarrow.parquet as pq
    except ImportError as error:  # maintainer tool; the runtime never needs it
        raise SystemExit("pyarrow is required for the loader: python -m pip install pyarrow") from error
    table = pq.read_table(path)
    return table.column_names, table.to_pylist()


def write_derivative(out_dir: Path, rows: list[dict[str, Any]], provenance: dict[str, Any]) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / OUTPUT_CSV
    ordered = sorted(rows, key=lambda row: (int(row["municipality_code"]), int(row["year"])))
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(APPROVED_COLUMNS)
        for row in ordered:
            writer.writerow([row[column] for column in APPROVED_COLUMNS])
    derivative = {**provenance, "rows": len(ordered), "columns": list(APPROVED_COLUMNS), "csv_sha256": sha256_file(csv_path)}
    (out_dir / "derivative.json").write_text(json.dumps(derivative, indent=2) + "\n", encoding="utf-8")
    return derivative


def load(release_dir: Path, out_dir: Path, versions: dict[str, str]) -> dict[str, Any]:
    expected = versions.get("EDUCATION_RELEASE_MANIFEST_SHA256", "")
    if len(expected) != 64:
        raise ReleaseRejected("EDUCATION_RELEASE_MANIFEST_SHA256 is not pinned in versions.env")
    manifest = verify_manifest(release_dir, expected)
    semantic = locate_layer(release_dir, manifest)
    columns, rows = read_parquet(semantic)
    validate_rows(columns, rows, manifest.get("row_counts", {}).get("semantic"))
    provenance = {
        "dataset": versions.get("EDUCATION_RELEASE_DATASET"),
        "dataset_version": versions.get("EDUCATION_RELEASE_VERSION"),
        "manifest_sha256": expected,
        "semantic_sha256": sha256_file(semantic),
        "source_id": manifest.get("source_id"),
        "source_git_commit": manifest.get("git_commit"),
    }
    return write_derivative(out_dir, rows, provenance)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--release-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    try:
        derivative = load(args.release_dir, args.out, read_versions())
    except ReleaseRejected as error:
        print(f"REJECTED: {error}", file=sys.stderr)
        return 2
    print(json.dumps({key: derivative[key] for key in ("dataset", "dataset_version", "manifest_sha256", "rows", "csv_sha256")}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
