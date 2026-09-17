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
from pathlib import Path

PACKAGE = "ores-otel/ores-otel-assets"
SOURCE = "branding/app-logo.png"
EXPORT_DIR = "exports/png"
EXPORT_SIZES = (16, 32, 48, 64, 128, 180, 192, 256, 512)
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

root = Path(__file__).resolve().parents[1]
manifest_path = root / "asset-manifest.json"


def png_size(path: Path) -> tuple[int, int]:
    header = path.read_bytes()[:24]
    if len(header) < 24 or header[:8] != PNG_SIGNATURE or header[12:16] != b"IHDR":
        raise AssertionError(f"{path.relative_to(root)} is not a PNG")
    return struct.unpack(">II", header[16:24])


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
