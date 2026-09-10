from __future__ import annotations

from pathlib import Path
from stat import S_IMODE

import pytest

from omnipack import build
from omnipack.sources import IngestionReport
from tests.test_build import composition, write_config

MARKED = b"Guide\r\n<!-- omnipack:catalog:start -->\r\nold\n<!-- omnipack:catalog:end -->\r\nTail\xff"


@pytest.mark.parametrize("existing", [False, True])
@pytest.mark.parametrize("failure_at", [0, 1, 2])
@pytest.mark.parametrize("operation", ["stage", "replace"])
def test_output_transaction_restores_bytes_or_absence_and_cleans_temporary_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    existing: bool,
    failure_at: int,
    operation: str,
) -> None:
    paths = [
        tmp_path / "dist/single.json",
        tmp_path / "dist/dual.json",
        tmp_path / "README.md",
    ]
    paths[0].parent.mkdir()
    for path in paths:
        if existing or path.name == "README.md":
            path.write_bytes(b"previous:" + path.name.encode())
            path.chmod(0o640 if path.name == "README.md" else 0o644)
    before = {path: path.read_bytes() if path.exists() else None for path in paths}
    modes = {path: S_IMODE(path.stat().st_mode) for path in paths if path.exists()}
    original_write = Path.write_bytes
    original_replace = Path.replace
    calls = 0

    def fail_write(path: Path, content: bytes) -> int:
        nonlocal calls
        call = calls
        calls += 1
        if call == failure_at:
            original_write(path, b"partial")
            raise OSError("injected staging failure")
        return original_write(path, content)

    def fail_replace(path: Path, target: Path) -> Path:
        nonlocal calls
        call = calls
        calls += 1
        if call == failure_at:
            raise OSError("injected replacement failure")
        return original_replace(path, target)

    monkeypatch.setattr(
        Path,
        "write_bytes" if operation == "stage" else "replace",
        fail_write if operation == "stage" else fail_replace,
    )
    with pytest.raises(OSError, match="injected"):
        build._replace_outputs({path: b"new" for path in paths})
    for path, snapshot in before.items():
        assert (path.read_bytes() if path.exists() else None) == snapshot
        if snapshot is not None:
            assert S_IMODE(path.stat().st_mode) == modes[path]
    assert {path for path in tmp_path.rglob("*") if path.is_file()} == {
        path for path, value in before.items() if value is not None
    }


@pytest.mark.parametrize("mode", [0o600, 0o640, 0o644, 0o755])
def test_output_replacement_preserves_existing_permissions(
    tmp_path: Path, mode: int
) -> None:
    output = tmp_path / "README.md"
    output.write_bytes(b"previous")
    output.chmod(mode)

    build._replace_outputs({output: b"new"})

    assert output.read_bytes() == b"new"
    assert S_IMODE(output.stat().st_mode) == mode


def test_new_output_uses_normal_file_creation_permissions(tmp_path: Path) -> None:
    reference = tmp_path / "reference.json"
    reference.write_bytes(b"reference")
    output = tmp_path / "new.json"

    build._replace_outputs({output: b"new"})

    assert output.read_bytes() == b"new"
    assert S_IMODE(output.stat().st_mode) == S_IMODE(reference.stat().st_mode)


@pytest.mark.parametrize(
    "stage", ["rendering", "offline verification", "report writing", "publication"]
)
def test_concurrent_readme_edit_is_preserved_before_publication(
    tmp_path: Path, stage: str
) -> None:
    write_config(tmp_path)
    readme = tmp_path / "README.md"
    readme.write_bytes(MARKED)

    def mutate(value: str) -> None:
        if value == stage:
            readme.write_bytes(MARKED + b"edit")

    with pytest.raises(build.OfflineVerificationError) as failure:
        build.publish_build(
            tmp_path, composition("one"), {}, IngestionReport(), on_stage=mutate
        )
    assert failure.value.findings[0]["code"] == "input_changed"
    assert readme.read_bytes() == MARKED + b"edit"
    assert not (tmp_path / "dist/single-screen.json").exists()


@pytest.mark.parametrize(
    "content",
    [
        None,
        b"no markers",
        b"<!-- omnipack:catalog:end -->\n<!-- omnipack:catalog:start -->\n",
    ],
)
def test_invalid_readme_fails_offline_gate_without_publishing(
    tmp_path: Path, content: bytes | None
) -> None:
    write_config(tmp_path)
    readme = tmp_path / "README.md"
    readme.unlink(missing_ok=True)
    if content is not None:
        readme.write_bytes(content)
    with pytest.raises(build.OfflineVerificationError) as failure:
        build.publish_build(tmp_path, composition("one"), {}, IngestionReport())
    assert failure.value.findings[0]["stage"] == "catalog"
    assert not (tmp_path / "dist").exists()
    assert (readme.read_bytes() if readme.exists() else None) == content


def test_build_catalog_matches_published_exports_and_preserves_surrounding_bytes(
    tmp_path: Path,
) -> None:
    from omnipack.catalog import generate_catalog, split_catalog
    from omnipack.composition_policy import load_composition_policy

    write_config(tmp_path)
    readme = tmp_path / "README.md"
    readme.write_bytes(MARKED)
    build.publish_build(tmp_path, composition("one"), {}, IngestionReport())
    prefix, interior, suffix = split_catalog(readme.read_bytes())
    before_prefix, _, before_suffix = split_catalog(MARKED)
    assert (prefix, suffix) == (before_prefix, before_suffix)
    assert interior == generate_catalog(
        (tmp_path / "dist/single-screen.json").read_bytes(),
        (tmp_path / "dist/dual-screen.json").read_bytes(),
        load_composition_policy((tmp_path / "config/composition.json").read_bytes()),
    )


@pytest.mark.parametrize("existing", [False, True])
def test_readme_replacement_failure_restores_published_pack_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    existing: bool,
) -> None:
    write_config(tmp_path)
    readme = tmp_path / "README.md"
    before = readme.read_bytes()
    outputs = [tmp_path / "dist" / name for name in build.OUTPUTS.values()]
    if existing:
        outputs[0].parent.mkdir()
        for output in outputs:
            output.write_bytes(b"previous pack")
    original = Path.replace

    def replace(path: Path, target: Path) -> Path:
        if target == readme:
            assert all(output.read_bytes() != b"previous pack" for output in outputs)
            raise OSError("README replacement failed")
        return original(path, target)

    monkeypatch.setattr(Path, "replace", replace)
    with pytest.raises(OSError, match="README replacement failed"):
        build.publish_build(tmp_path, composition("one"), {}, IngestionReport())
    assert readme.read_bytes() == before
    for output in outputs:
        assert (output.read_bytes() if output.exists() else None) == (
            b"previous pack" if existing else None
        )
    assert not list(tmp_path.rglob("*.tmp"))


def test_policy_snapshot_is_rechecked_when_caller_does_not_supply_one(
    tmp_path: Path,
) -> None:
    write_config(tmp_path)
    policy = tmp_path / "config/composition.json"

    def mutate(stage: str) -> None:
        if stage == "publication":
            policy.write_bytes(policy.read_bytes() + b"\n")

    with pytest.raises(build.OfflineVerificationError) as failure:
        build.publish_build(
            tmp_path, composition("one"), {}, IngestionReport(), on_stage=mutate
        )
    assert failure.value.findings[0]["code"] == "input_changed"
    assert not (tmp_path / "dist").exists()


@pytest.mark.parametrize("existing", [False, True])
@pytest.mark.parametrize("input_name", ["README.md", "config/composition.json"])
def test_input_edit_during_staging_preserves_inputs_outputs_and_cleans_temps(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    existing: bool,
    input_name: str,
) -> None:
    write_config(tmp_path)
    readme = tmp_path / "README.md"
    readme.write_bytes(MARKED)
    outputs = [tmp_path / "dist" / name for name in build.OUTPUTS.values()]
    if existing:
        outputs[0].parent.mkdir()
        for output in outputs:
            output.write_bytes(b"previous pack")
    preserved = [readme, tmp_path / "config/composition.json", *outputs]
    expected = {
        path: path.read_bytes() if path.exists() else None for path in preserved
    }
    edited = tmp_path / input_name
    edited_bytes = edited.read_bytes() + b"\n"
    expected[edited] = edited_bytes
    original_write = Path.write_bytes
    staged = 0

    def mutate_during_write(path: Path, content: bytes) -> int:
        nonlocal staged
        result = original_write(path, content)
        if path.suffix == ".tmp" and path.parent in {tmp_path, tmp_path / "dist"}:
            if staged == 2:
                original_write(edited, edited_bytes)
            staged += 1
        return result

    monkeypatch.setattr(Path, "write_bytes", mutate_during_write)
    with pytest.raises(build.OfflineVerificationError) as failure:
        build.publish_build(tmp_path, composition("one"), {}, IngestionReport())

    assert staged == 3
    assert failure.value.findings[0]["code"] == "input_changed"
    for path, snapshot in expected.items():
        assert (path.read_bytes() if path.exists() else None) == snapshot
    assert not list(tmp_path.rglob("*.tmp"))
