"""Verify the registered skill-only plugin and package it without machine metadata."""

import base64
import hashlib
import io
import json
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath

from app.contracts.errors import ConfigurationConflict
from app.contracts.runtime import RuntimeBundle, RuntimeProfile

BUNDLE_ROOT = Path(__file__).resolve().parents[2] / "runtime-bundles"
BUNDLE_ID = "shopops-hosted-v1"
BUNDLE_VERSION = "1.0.0"
PLUGIN_NAME = "shopops-analysis"
PLUGIN_DESCRIPTION = "Grounded ShopOps returns analysis and versioned knowledge review."
MAX_BYTES = 262144
FILES = (
    "shopops-analysis/.codex-plugin/plugin.json",
    "shopops-analysis/references/specialists/data-analyst.md",
    "shopops-analysis/references/specialists/knowledge-analyst.md",
    "shopops-analysis/skills/knowledge-review/SKILL.md",
    "shopops-analysis/skills/returns-analysis/SKILL.md",
    "shopops-analysis/skills/returns-analysis/scripts/summarize_returns.py",
)
# Each published version has its own immutable directory and exact inventory.
REGISTERED_BUNDLES = {
    BUNDLE_VERSION: (BUNDLE_ID, PLUGIN_DESCRIPTION, FILES),
    "1.1.0": (
        "shopops-hosted-v1.1",
        "Scoped ShopOps product investigations, returns analysis and versioned knowledge review.",
        tuple(
            sorted(
                (
                    *FILES,
                    "shopops-analysis/references/investigation/refresh-and-freshness.md",
                    "shopops-analysis/references/investigation/six-pain-workflows.md",
                    "shopops-analysis/skills/product-investigation/SKILL.md",
                )
            )
        ),
    ),
}


def _object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def _read(path: Path, limit: int) -> bytes:
    if not stat.S_ISREG(path.lstat().st_mode) or path.stat().st_size > limit:
        raise ValueError("invalid bundle file")
    with path.open("rb") as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError("bundle too large")
    return data


def _build(profile: RuntimeProfile, *, bundle_root: Path | None = None) -> RuntimeBundle:
    if profile.profile_id != BUNDLE_ID or profile.bundle_id != BUNDLE_ID:
        raise ValueError("unregistered bundle")
    bundle_directory, description, files = REGISTERED_BUNDLES[profile.bundle_version]
    directory = bundle_root if bundle_root is not None else BUNDLE_ROOT
    root = directory / bundle_directory
    if directory.is_symlink() or root.is_symlink() or not root.is_dir():
        raise ValueError("invalid bundle root")
    actual = set()
    directories = {
        str(parent)
        for name in files
        for parent in PurePosixPath(name).parents
        if str(parent) != "."
    }
    for path in root.rglob("*"):
        mode = path.lstat().st_mode
        relative = path.relative_to(root).as_posix()
        if stat.S_ISDIR(mode) and relative in directories:
            continue
        if not stat.S_ISREG(mode):
            raise ValueError("invalid entry type")
        actual.add(relative)
    if actual != {*files, "manifest.json"}:
        raise ValueError("unregistered files")
    manifest = json.loads(_read(root / "manifest.json", 16384), object_pairs_hook=_object)
    if set(manifest) != {"bundle_id", "bundle_version", "bundle_sha256", "files"}:
        raise ValueError("invalid manifest")
    if (manifest["bundle_id"], manifest["bundle_version"], manifest["bundle_sha256"]) != (
        profile.bundle_id,
        profile.bundle_version,
        profile.bundle_sha256,
    ):
        raise ValueError("bundle pin mismatch")
    records = manifest["files"]
    if not isinstance(records, list) or len(records) != len(files):
        raise ValueError("invalid inventory")
    for record in records:
        if set(record) != {"path", "sha256"}:
            raise ValueError("invalid file record")
        name, digest = record["path"], record["sha256"]
        if (
            not isinstance(name, str)
            or PurePosixPath(name).is_absolute()
            or ".." in PurePosixPath(name).parts
            or "\\" in name
            or not isinstance(digest, str)
            or not re.fullmatch(r"[a-f0-9]{64}", digest)
        ):
            raise ValueError("invalid path or digest")
    if [record["path"] for record in records] != list(files):
        raise ValueError("unsorted or duplicate inventory")
    aggregate = hashlib.sha256(
        "".join(f"{record['path']}\0{record['sha256']}\n" for record in records).encode("utf-8")
    ).hexdigest()
    if aggregate != profile.bundle_sha256:
        raise ValueError("aggregate mismatch")
    contents = {}
    total = 0
    for record in records:
        data = _read(root / record["path"], MAX_BYTES - total)
        total += len(data)
        if hashlib.sha256(data).hexdigest() != record["sha256"]:
            raise ValueError("file digest mismatch")
        contents[record["path"]] = data
    metadata = json.loads(
        contents["shopops-analysis/.codex-plugin/plugin.json"], object_pairs_hook=_object
    )
    if metadata != {
        "name": PLUGIN_NAME,
        "description": description,
        "version": profile.bundle_version,
        "skills": "./skills/",
    }:
        raise ValueError("plugin metadata mismatch")
    output = io.BytesIO()
    # ZIP_STORED avoids zlib-version differences. No host timestamps or executable bits.
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, data in contents.items():
            entry = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            entry.create_system = 3
            entry.external_attr = (stat.S_IFREG | 0o644) << 16
            archive.writestr(entry, data)
    return RuntimeBundle(
        bundle_id=BUNDLE_ID,
        bundle_version=profile.bundle_version,
        bundle_sha256=aggregate,
        inline_plugin={
            "type": "inline",
            "name": PLUGIN_NAME,
            "description": description,
            "source": {
                "type": "base64",
                "media_type": "application/zip",
                "data": base64.b64encode(output.getvalue()).decode("ascii"),
            },
        },
    )


def build_runtime_bundle(
    profile: RuntimeProfile, *, bundle_root: Path | None = None
) -> RuntimeBundle:
    """No user paths, archive ingestion, network, shell calls or fallback."""
    try:
        return _build(profile, bundle_root=bundle_root)
    except OSError, ValueError, KeyError, TypeError, AttributeError, RecursionError:
        raise ConfigurationConflict() from None
