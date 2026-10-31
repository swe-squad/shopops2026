import base64
import hashlib
import io
import json
import shutil
import zipfile
from pathlib import Path

import pytest

from app.agents import runtime_bundle as builder
from app.contracts.errors import ConfigurationConflict
from app.contracts.runtime import RuntimeProfile

ROOT = Path(__file__).resolve().parents[2] / "runtime-bundles"


def profile(manifest):
    return RuntimeProfile(
        profile_id="shopops-hosted-v1",
        environment_type="openai_hosted",
        bundle_id=manifest["bundle_id"],
        bundle_version=manifest["bundle_version"],
        bundle_sha256=manifest["bundle_sha256"],
        container_size="small",
        multi_agent_enabled=True,
        max_concurrent_subagents=2,
    )


@pytest.fixture(params=["shopops-hosted-v1", "shopops-hosted-v1.1"])
def bundle(tmp_path, monkeypatch, request):
    target = tmp_path / "runtime-bundles"
    shutil.copytree(ROOT, target)
    monkeypatch.setattr(builder, "BUNDLE_ROOT", target)
    root = target / request.param
    manifest = json.loads((root / "manifest.json").read_text())
    return root, manifest


def test_registered_bundle_is_deterministic_and_matches_manifest(bundle):
    root, manifest = bundle
    expected = hashlib.sha256(
        "".join(f"{f['path']}\0{f['sha256']}\n" for f in manifest["files"]).encode()
    ).hexdigest()
    assert expected == manifest["bundle_sha256"]
    first = builder.build_runtime_bundle(profile(manifest))
    # mtime, permissions and host filesystem ordering cannot affect the archive.
    for path in root.rglob("*"):
        if path.is_file():
            path.touch()
            path.chmod(0o600)
    second = builder.build_runtime_bundle(profile(manifest))
    assert first.inline_plugin == second.inline_plugin
    assert first.bundle_sha256 == expected
    assert "inline_plugin" not in first.model_dump()
    payload = first.inline_plugin
    assert payload["type"] == "inline"
    archive = base64.b64decode(payload["source"]["data"], validate=True)
    with zipfile.ZipFile(io.BytesIO(archive)) as zipped:
        assert zipped.namelist() == [f["path"] for f in manifest["files"]]
        assert len(zipped.namelist()) == len(set(zipped.namelist()))
        assert sum(i.file_size for i in zipped.infolist()) <= 262144
        assert all(i.date_time == (1980, 1, 1, 0, 0, 0) for i in zipped.infolist())
        assert "manifest.json" not in zipped.namelist()
        assert (
            json.loads(zipped.read("shopops-analysis/.codex-plugin/plugin.json"))["name"]
            == payload["name"]
        )


@pytest.mark.parametrize(
    "mutation",
    [
        "changed",
        "missing",
        "extra",
        "symlink",
        "directory_symlink",
        "root_symlink",
        "absolute",
        "parent",
        "duplicate",
        "unsorted",
        "digest",
        "version",
        "oversize",
        "plugin_name",
        "plugin_description",
        "manifest_extra",
    ],
)
def test_invalid_bundle_fails_closed(bundle, mutation):
    root, manifest = bundle
    path = root / manifest["files"][0]["path"]
    pinned = profile(manifest)
    if mutation == "changed":
        path.write_bytes(path.read_bytes() + b" ")
    elif mutation == "missing":
        path.unlink()
    elif mutation == "extra":
        (root / "shopops-analysis/.env").write_text("not-a-secret")
    elif mutation == "symlink":
        path.unlink()
        path.symlink_to("/etc/hostname")
    elif mutation == "directory_symlink":
        (root / "shopops-analysis/extra").symlink_to(root, target_is_directory=True)
    elif mutation == "root_symlink":
        moved = root.with_name("moved")
        root.rename(moved)
        root.symlink_to(moved, target_is_directory=True)
    elif mutation in {"absolute", "parent"}:
        manifest["files"][0]["path"] = "/etc/hostname" if mutation == "absolute" else "../outside"
    elif mutation == "duplicate":
        manifest["files"].append(manifest["files"][0])
    elif mutation == "unsorted":
        manifest["files"].reverse()
    elif mutation == "digest":
        manifest["files"][0]["sha256"] = "0" * 64
    elif mutation == "version":
        manifest["bundle_version"] = "unregistered"
    elif mutation == "oversize":
        path.write_bytes(b"x" * 262145)
    elif mutation.startswith("plugin_"):
        data = json.loads(path.read_text())
        data[mutation.removeprefix("plugin_")] = "unapproved"
        path.write_text(json.dumps(data))
        # Rehash to prove metadata validation is independent of file hashes.
        manifest["files"][0]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest["bundle_sha256"] = hashlib.sha256(
            "".join(f"{f['path']}\0{f['sha256']}\n" for f in manifest["files"]).encode()
        ).hexdigest()
        pinned = profile(manifest)
    elif mutation == "manifest_extra":
        manifest["credentials"] = "forbidden"
    if mutation != "root_symlink":
        (root / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ConfigurationConflict):
        builder.build_runtime_bundle(pinned)


def test_legacy_profile_cannot_load_bundle():
    with pytest.raises(ConfigurationConflict):
        builder.build_runtime_bundle(RuntimeProfile())


def test_new_version_preserves_the_old_immutable_bundle_and_adds_investigation_assets():
    old = json.loads((ROOT / "shopops-hosted-v1/manifest.json").read_text())
    new = json.loads((ROOT / "shopops-hosted-v1.1/manifest.json").read_text())
    assert old["bundle_version"] == "1.0.0"
    assert (
        old["bundle_sha256"] == "a0fa0d1149fd7f8cccefc4fe1c0da05d7108cb404d458b5a2b9353bb600b718a"
    )
    assert new["bundle_version"] == "1.1.0"
    assert new["bundle_sha256"] != old["bundle_sha256"]
    for manifest in (old, new):
        bundle = builder.build_runtime_bundle(profile(manifest))
        raw = base64.b64decode(bundle.inline_plugin["source"]["data"], validate=True)
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            skill = "shopops-analysis/skills/product-investigation/SKILL.md"
            assert (skill in archive.namelist()) == (manifest is new)
            if manifest is new:
                assert "No raw-record fetch" in archive.read(skill).decode()
                reference = "shopops-analysis/references/investigation/refresh-and-freshness.md"
                assert "Reconcile the same request" in archive.read(reference).decode()


@pytest.mark.parametrize("version", ["1", "1.0.1", "2.0.0", "../shopops-hosted-v1"])
def test_unknown_bundle_version_cannot_select_another_directory(version):
    manifest = json.loads((ROOT / "shopops-hosted-v1/manifest.json").read_text())
    pinned = profile(manifest).model_copy(update={"bundle_version": version})
    with pytest.raises(ConfigurationConflict):
        builder.build_runtime_bundle(pinned)
