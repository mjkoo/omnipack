from __future__ import annotations

import json
from pathlib import Path

import pytest

from omnipack import cli
from omnipack.http import HttpClient
from omnipack.report import write_report
from omnipack.sources import IngestionReport
from tests.verification_support import write_verification_inputs


def inputs(root: Path) -> dict[Path, bytes]:
    write_verification_inputs(root)
    (root / "config/http.json").write_text('{"credentials":{}}\n')
    write_report(root, {}, None, IngestionReport())
    (root / ".cache").mkdir()
    (root / ".cache/sentinel").write_bytes(b"cache bytes\x00")
    return snapshot(root)


def snapshot(root: Path) -> dict[Path, bytes]:
    return {
        path.relative_to(root): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file() and path.name != "verify.json"
    }


@pytest.mark.parametrize("build_present", [False, True])
def test_offline_cli_succeeds_without_network_or_protected_file_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, build_present: bool
) -> None:
    inputs(tmp_path)
    if not build_present:
        (tmp_path / ".build/report.json").unlink()
    before = snapshot(tmp_path)
    monkeypatch.setattr(
        HttpClient,
        "_urllib_transport",
        lambda *_args, **_kwargs: pytest.fail("offline request"),
    )
    monkeypatch.chdir(tmp_path)
    assert cli.main(["verify"]) == 0
    assert snapshot(tmp_path) == before
    assert (
        json.loads((tmp_path / ".build/verify.json").read_bytes())["status"]
        == "success"
    )


def test_unsupported_verify_argument_fails_before_verification(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    inputs(tmp_path)
    report_path = tmp_path / ".build/verify.json"
    report_path.write_bytes(b'{"prior":"evidence"}')
    monkeypatch.setattr(
        cli,
        "run_verification",
        lambda *_args, **_kwargs: pytest.fail("verification ran"),
    )
    monkeypatch.setattr(
        HttpClient,
        "_urllib_transport",
        lambda *_args, **_kwargs: pytest.fail("network request"),
    )
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit) as raised:
        cli.main(["verify", "--unsupported-option"])
    assert raised.value.code == 2
    assert "unrecognized arguments" in capsys.readouterr().err
    assert report_path.read_bytes() == b'{"prior":"evidence"}'


def test_cli_report_write_failure_is_concise(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    inputs(tmp_path)
    path = tmp_path / ".build/verify.json"
    path.write_bytes(b'{"prior":"evidence"}')
    original = Path.replace

    def replace(self: Path, target: Path) -> Path:
        if target == path:
            raise PermissionError("fixture report denied")
        return original(self, target)

    monkeypatch.setattr(Path, "replace", replace)
    monkeypatch.chdir(tmp_path)
    assert cli.main(["verify"]) == 1
    error = capsys.readouterr().err
    assert (
        "cannot write verification report" in error and "fixture report denied" in error
    )
    assert "Traceback" not in error and len(error.splitlines()) == 1
    assert json.loads(path.read_bytes()) == {"prior": "evidence"}
