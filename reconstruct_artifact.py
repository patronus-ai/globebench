#!/usr/bin/env python3
"""Reconstruct and verify source files from the chunked release tree."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath


def safe_relative(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise ValueError(f"unsafe artifact path: {value!r}")
    return path


def reconstruct(artifact_dir: Path, out_dir: Path) -> dict[str, str]:
    index_path = artifact_dir / "DATA_INDEX.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    if index.get("schema") != "globebench-chunk-index/1":
        raise ValueError("unsupported DATA_INDEX schema")
    verified: dict[str, str] = {}
    for original, record in sorted(index.get("files", {}).items()):
        destination_relative = safe_relative(original)
        parts = record.get("parts")
        if not isinstance(parts, list) or not parts:
            raise ValueError(f"{original}: parts must be a nonempty list")
        chunks = []
        for value in parts:
            relative = safe_relative(value)
            chunks.append((artifact_dir / Path(*relative.parts)).read_bytes())
        data = b"".join(chunks)
        actual = hashlib.sha256(data).hexdigest()
        expected = record.get("sha256")
        if actual != expected:
            raise ValueError(f"{original}: sha256 {actual} != {expected}")
        destination = out_dir / Path(*destination_relative.parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        verified[original] = actual
    return verified


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact-dir", type=Path, default=Path("."))
    parser.add_argument("--out-dir", required=True, type=Path)
    args = parser.parse_args()
    verified = reconstruct(args.artifact_dir, args.out_dir)
    print(json.dumps({"verified_files": len(verified)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
