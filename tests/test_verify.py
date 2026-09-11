from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from omnipack import verify


def historical_composition() -> str:
    document = json.loads(Path("config/composition.json").read_text())
    document["candidates"] = [
        rule for rule in document["candidates"] if rule["match"]["source"] != "extras"
    ]
    document["pins"] = [
        pin for pin in document["pins"] if pin["match"]["source"] != "extras"
    ]
    return json.dumps(document)


def copy_inputs(root: Path) -> None:
    for relative in verify.INPUT_PATHS.values():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if relative.name in {"overlay.json", "overlay.dual.json"}:
            target.write_text("[]")
        elif relative.name == "composition.json" and relative.exists():
            target.write_text(historical_composition())
        elif relative.exists():
            shutil.copyfile(relative, target)
        elif relative.name == "composition.json":
            target.write_text('{"schemaVersion":1,"candidates":[],"pins":[]}')


def test_offline_evidence_fingerprints_exact_inputs(tmp_path: Path) -> None:
    copy_inputs(tmp_path)
    result = verify.run_verification(tmp_path)
    assert result["status"] == "success"
    assert result["complete"] is True
    assert result["mode"] == "offline"
    assert set(result["inputs"]) == set(verify.INPUT_PATHS)
    for name, relative in verify.INPUT_PATHS.items():
        expected = hashlib.sha256((tmp_path / relative).read_bytes()).hexdigest()
        assert result["inputs"][name] == {"state": "present", "sha256": expected}
    assert json.loads((tmp_path / verify.VERIFY_PATH).read_text()) == result


def test_missing_inputs_complete_as_failed_evidence(tmp_path: Path) -> None:
    result = verify.run_verification(tmp_path)
    assert result["status"] == "failed"
    assert result["complete"] is True
    assert all(value["state"] == "missing" for value in result["inputs"].values())


def test_running_record_precedes_offline_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    copy_inputs(tmp_path)

    def interrupted(_inputs: object) -> object:
        stored = json.loads((tmp_path / verify.VERIFY_PATH).read_text())
        assert stored["status"] == "running"
        assert stored["complete"] is False
        raise KeyboardInterrupt

    monkeypatch.setattr(verify, "validate_offline", interrupted)
    with pytest.raises(KeyboardInterrupt):
        verify.run_verification(tmp_path)
    stored = json.loads((tmp_path / verify.VERIFY_PATH).read_text())
    assert stored["complete"] is False


def test_changed_input_prevents_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    copy_inputs(tmp_path)
    real = verify.capture_inputs
    calls = 0

    def capture(root: Path):
        nonlocal calls
        calls += 1
        if calls == 2:
            (root / "config/settings.json").write_bytes(b'{"changed":true}\n')
        return real(root)

    monkeypatch.setattr(verify, "capture_inputs", capture)
    result = verify.run_verification(tmp_path)
    assert any(item["code"] == "input_changed" for item in result["errors"])
    assert result["status"] == "failed"


def test_composition_only_change_makes_recorded_evidence_stale(tmp_path: Path) -> None:
    from omnipack.report import format_reports

    copy_inputs(tmp_path)
    result = verify.run_verification(tmp_path)
    assert result["status"] == "success"
    path = tmp_path / "config/composition.json"
    path.write_bytes(path.read_bytes() + b"\n")
    assert "Evidence: stale" in format_reports(tmp_path)


def test_initial_report_write_error_is_wrapped(tmp_path: Path) -> None:
    (tmp_path / ".build").write_text("occupied")
    with pytest.raises(
        verify.VerificationReportError, match="cannot write verification report"
    ):
        verify.run_verification(tmp_path)


def test_http_config_is_not_read_or_fingerprinted(tmp_path, monkeypatch) -> None:
    copy_inputs(tmp_path)
    (tmp_path / "config/http.json").write_text(
        json.dumps({"credentials": {"example.test": 1}})
    )
    read_bytes = Path.read_bytes
    monkeypatch.setattr(
        Path,
        "read_bytes",
        lambda self: (
            pytest.fail("unexpected read")
            if self.name == "http.json"
            else read_bytes(self)
        ),
    )
    result = verify.run_verification(tmp_path)
    assert result["status"] == "success"
    assert "http" not in result["inputs"]


def test_missing_http_config_does_not_affect_verification(tmp_path: Path) -> None:
    copy_inputs(tmp_path)
    (tmp_path / "config/http.json").unlink(missing_ok=True)
    result = verify.run_verification(tmp_path)
    assert result["status"] == "success"
    assert "http" not in result["inputs"]


@pytest.mark.parametrize("entry", [[], None])
def test_nonobject_exclusion_completes_failed_evidence(
    tmp_path: Path, entry: object
) -> None:
    copy_inputs(tmp_path)
    (tmp_path / "config/deny.json").write_text(json.dumps([entry]))
    result = verify.run_verification(tmp_path)
    assert result["status"] == "failed"
    assert result["complete"] is True
    assert any(
        error["code"] == "invalid_composition_config"
        and "denylist[0] must be an object" in error["message"]
        for error in result["errors"]
    )
    assert json.loads((tmp_path / verify.VERIFY_PATH).read_text()) == result
