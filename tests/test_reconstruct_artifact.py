import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import reconstruct_artifact

SCHEMA = "globebench-chunk-index/1"


def write_artifact(root: Path, files: dict[str, bytes], index: dict) -> None:
    for name, data in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    (root / "DATA_INDEX.json").write_text(json.dumps(index), encoding="utf-8")


class ReconstructArtifactTests(unittest.TestCase):
    def test_reconstruction_joins_parts_and_verifies_sha(self):
        data = b'{"id":1}\n{"id":2}\n'
        parts = {
            "data/eval.parts/part-0001.jsonl": b'{"id":1}\n',
            "data/eval.parts/part-0002.jsonl": b'{"id":2}\n',
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifact, output = root / "artifact", root / "output"
            write_artifact(artifact, parts, {
                "schema": SCHEMA,
                "files": {
                    "data/eval.jsonl": {
                        "sha256": hashlib.sha256(data).hexdigest(),
                        "parts": list(parts),
                    }
                },
            })
            verified = reconstruct_artifact.reconstruct(artifact, output)
            self.assertEqual(verified["data/eval.jsonl"], hashlib.sha256(data).hexdigest())
            self.assertEqual((output / "data" / "eval.jsonl").read_bytes(), data)

    def test_sha_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifact = root / "artifact"
            write_artifact(artifact, {"a.txt": b"x"}, {
                "schema": SCHEMA,
                "files": {"a.txt": {"sha256": "0" * 64, "parts": ["a.txt"]}},
            })
            with self.assertRaisesRegex(ValueError, "sha256"):
                reconstruct_artifact.reconstruct(artifact, root / "output")

    def test_path_traversal_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifact = root / "artifact"
            write_artifact(artifact, {"a.txt": b"x"}, {
                "schema": SCHEMA,
                "files": {"../escape.txt": {"sha256": "", "parts": ["a.txt"]}},
            })
            with self.assertRaisesRegex(ValueError, "unsafe artifact path"):
                reconstruct_artifact.reconstruct(artifact, root / "output")

    def test_unknown_schema_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            write_artifact(root, {}, {"schema": "other/1", "files": {}})
            with self.assertRaisesRegex(ValueError, "unsupported DATA_INDEX schema"):
                reconstruct_artifact.reconstruct(root, root / "output")


if __name__ == "__main__":
    unittest.main()
