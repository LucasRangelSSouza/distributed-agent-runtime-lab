import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("public_demo_load_release", ROOT / "scripts" / "public_demo_load_release.py")
loader = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(loader)


def row(code="1100015", year=2019, **overrides):
    base = {
        "municipality_code": code, "year": year, "state_code": "RO", "population": 1000,
        "mde_minimum_share_pct": 25.5, "investment_per_basic_education_student": 6000.0,
        "identifier_classification": "not_present", "municipality_name": "Example",
    }
    return {**base, **overrides}


class ReleaseFixture:
    """A tiny on-disk release with a manifest that lists one semantic file."""

    def __init__(self, root: Path, privacy_gate="passed", flattened=True):
        self.root = root
        payload = b"not-a-real-parquet-but-hashable"
        name = "semantic_records.parquet" if flattened else "semantic/records.parquet"
        (root / name).parent.mkdir(parents=True, exist_ok=True)
        (root / name).write_bytes(payload)
        manifest = {
            "privacy_gate": privacy_gate,
            "row_counts": {"semantic": 1},
            "files": [{"path": "semantic/records.parquet", "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}],
        }
        (root / "release_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        self.manifest_sha256 = loader.sha256_file(root / "release_manifest.json")


class LoaderGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_pinned_manifest_and_matching_file_pass(self):
        release = ReleaseFixture(self.root)
        manifest = loader.verify_manifest(self.root, release.manifest_sha256)
        self.assertEqual(loader.locate_layer(self.root, manifest).name, "semantic_records.parquet")

    def test_unflattened_layout_is_accepted(self):
        release = ReleaseFixture(self.root, flattened=False)
        manifest = loader.verify_manifest(self.root, release.manifest_sha256)
        self.assertEqual(loader.locate_layer(self.root, manifest).name, "records.parquet")

    def test_altered_manifest_is_rejected(self):
        release = ReleaseFixture(self.root)
        path = self.root / "release_manifest.json"
        path.write_text(path.read_text(encoding="utf-8").replace('"passed"', '"passed" '), encoding="utf-8")
        with self.assertRaisesRegex(loader.ReleaseRejected, "does not match the pinned"):
            loader.verify_manifest(self.root, release.manifest_sha256)

    def test_unapproved_manifest_hash_is_rejected(self):
        ReleaseFixture(self.root)
        with self.assertRaises(loader.ReleaseRejected):
            loader.verify_manifest(self.root, "0" * 64)

    def test_failed_privacy_gate_is_rejected(self):
        release = ReleaseFixture(self.root, privacy_gate="failed")
        with self.assertRaisesRegex(loader.ReleaseRejected, "privacy_gate"):
            loader.verify_manifest(self.root, release.manifest_sha256)

    def test_checksum_mismatch_is_rejected(self):
        release = ReleaseFixture(self.root)
        manifest = loader.verify_manifest(self.root, release.manifest_sha256)
        target = self.root / "semantic_records.parquet"
        target.write_bytes(target.read_bytes().replace(b"real", b"fake"))
        with self.assertRaisesRegex(loader.ReleaseRejected, "SHA-256"):
            loader.locate_layer(self.root, manifest)

    def test_missing_layer_file_is_rejected(self):
        release = ReleaseFixture(self.root)
        manifest = loader.verify_manifest(self.root, release.manifest_sha256)
        (self.root / "semantic_records.parquet").unlink()
        with self.assertRaisesRegex(loader.ReleaseRejected, "missing"):
            loader.locate_layer(self.root, manifest)

    def test_unpinned_versions_file_is_rejected(self):
        ReleaseFixture(self.root)
        with self.assertRaisesRegex(loader.ReleaseRejected, "not pinned"):
            loader.load(self.root, self.root / "out", {"EDUCATION_RELEASE_MANIFEST_SHA256": ""})
        self.assertFalse((self.root / "out").exists())

    def test_versions_file_pins_the_education_release(self):
        versions = loader.read_versions()
        self.assertEqual(len(versions["EDUCATION_RELEASE_MANIFEST_SHA256"]), 64)


class LoaderRowTests(unittest.TestCase):
    def test_valid_rows_pass(self):
        loader.validate_rows(row().keys(), [row(), row(year=2020)], 2)

    def test_missing_approved_column_is_rejected(self):
        columns = [c for c in row() if c != "population"]
        with self.assertRaisesRegex(loader.ReleaseRejected, "missing approved columns"):
            loader.validate_rows(columns, [row()], 1)

    def test_row_count_mismatch_is_rejected(self):
        with self.assertRaisesRegex(loader.ReleaseRejected, "rows"):
            loader.validate_rows(row().keys(), [row()], 2)

    def test_identifier_rows_are_rejected(self):
        with self.assertRaisesRegex(loader.ReleaseRejected, "identifier_classification"):
            loader.validate_rows(row().keys(), [row(identifier_classification="person")], 1)

    def test_duplicate_keys_are_rejected(self):
        with self.assertRaisesRegex(loader.ReleaseRejected, "duplicate"):
            loader.validate_rows(row().keys(), [row(), row()], 2)

    def test_derivative_contains_only_approved_columns(self):
        with tempfile.TemporaryDirectory() as tmp:
            derivative = loader.write_derivative(Path(tmp), [row(year=2020), row()], {"dataset": "d"})
            header = (Path(tmp) / loader.OUTPUT_CSV).read_text(encoding="utf-8").splitlines()[0]
        self.assertEqual(header.split(","), list(loader.APPROVED_COLUMNS))
        self.assertEqual(derivative["rows"], 2)
        self.assertNotIn("municipality_name", header)


if __name__ == "__main__":
    unittest.main()
