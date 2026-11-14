#!/usr/bin/env python3
"""Validate (or regenerate with --write) the integrity-bound asset manifest.

The source logo is the single authority. Static/CDN exports are derived PNGs
at fixed square sizes, and every file is bound to the manifest by sha256 so
consumers (CDN uploads, the Flutter launcher generator) can prove which bytes
they shipped. Standard library only.
"""

from __future__ import annotations

import hashlib
import json
import struct
import sys
import zlib
from pathlib import Path

PACKAGE = "ores-otel/ores-otel-assets"
SOURCE = "branding/app-logo.png"
EXPORT_DIR = "exports/png"
EXPORT_SIZES = (16, 32, 48, 64, 128, 180, 192, 256, 512)
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

root = Path(__file__).resolve().parents[1]
manifest_path = root / "asset-manifest.json"


def png_size(path: Path) -> tuple[int, int]:
    # Validate the complete, fixed-length IHDR including its CRC before trusting
    # the uncompressed dimensions. This is a structural check, not a PNG decoder.
    with path.open("rb") as stream:
        header = stream.read(33)
    if (
        len(header) != 33
        or header[:8] != PNG_SIGNATURE
        or struct.unpack(">I", header[8:12])[0] != 13
        or header[12:16] != b"IHDR"
        or struct.unpack(">I", header[29:33])[0] != zlib.crc32(header[12:29])
    ):
        raise AssertionError(f"{path.relative_to(root)} has an invalid PNG IHDR")
    width, height = struct.unpack(">II", header[16:24])
    if not (0 < width <= 16384 and 0 < height <= 16384):
        raise AssertionError(f"{path.relative_to(root)} has out-of-range dimensions")
    return width, height


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def entry(relative: str, role: str) -> dict[str, object]:
    path = root / relative
    width, height = png_size(path)
    return {
        "path": relative,
        "role": role,
        "mediaType": "image/png",
        "width": width,
        "height": height,
        "sha256": sha256(path),
    }


def expected_manifest() -> dict[str, object]:
    source = entry(SOURCE, "source")
    return {
        "schemaVersion": 1,
        "package": PACKAGE,
        "brandApproval": "pending",
        "flutterLauncher": {
            "source": SOURCE,
            "sha256": source["sha256"],
        },
        "assets": [source]
        + [entry(f"{EXPORT_DIR}/app-logo-{size}.png", "static-export") for size in EXPORT_SIZES],
    }


def main(argv: list[str]) -> int:
    if argv == ["--write"]:
        manifest_path.write_text(json.dumps(expected_manifest(), indent=2) + "\n", encoding="utf-8")
        print(f"wrote {manifest_path.relative_to(root)}")
        return 0
    if argv:
        print("usage: scripts/validate.py [--write]", file=sys.stderr)
        return 2

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schemaVersion"] == 1
    assert manifest["package"] == PACKAGE
    assert manifest["brandApproval"] in {"pending", "approved"}

    for asset in manifest["assets"]:
        path = root / asset["path"]
        assert path.is_file() and not path.is_symlink(), f"missing {asset['path']}"
        assert path.resolve().is_relative_to(root.resolve()), f"escapes root: {asset['path']}"
        assert (asset["width"], asset["height"]) == png_size(path), f"size drift: {asset['path']}"
        assert sha256(path) == asset["sha256"], f"checksum drift: {asset['path']}"

    exports = sorted(p.relative_to(root).as_posix() for p in (root / EXPORT_DIR).glob("*"))
    listed = sorted(a["path"] for a in manifest["assets"] if a["role"] == "static-export")
    assert exports == listed, f"unlisted or missing exports: {sorted(set(exports) ^ set(listed))}"

    expected = expected_manifest()
    expected["brandApproval"] = manifest["brandApproval"]
    assert manifest == expected, "asset-manifest.json is stale; run scripts/validate.py --write"
    for asset in manifest["assets"]:
        if asset["role"] == "static-export":
            assert asset["width"] == asset["height"], f"non-square export: {asset['path']}"

    print("asset package contract: valid")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
