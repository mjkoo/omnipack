from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from omnipack import verify
from tests.verification_support import write_verification_inputs as copy_inputs


def test_offline_evidence_fingerprints_exact_inputs(tmp_path: Path) -> None:
    copy_inputs(tmp_path)
    result = verify.run_verification(tmp_path)
    assert result["status"] == "success"
    assert result["complete"] is True
    assert result["mode"] == "offline"
    assert result["schemaVersion"] == 3
    assert result["verifier"] == {"version": "2.0.0", "scope": "structural"}
    assert set(result["inputs"]) == {
        "single",
        "dual",
        "deny",
        "overlay",
        "composition",
        "readme",
    }
    for name, relative in verify.INPUT_PATHS.items():
        expected = hashlib.sha256((tmp_path / relative).read_bytes()).hexdigest()
        assert result["inputs"][name] == {"state": "present", "sha256": expected}
    assert json.loads((tmp_path / verify.VERIFY_PATH).read_text()) == result


def test_missing_inputs_complete_as_failed_evidence(tmp_path: Path) -> None:
    result = verify.run_verification(tmp_path)
    assert result["status"] == "failed"
    assert result["complete"] is True
    assert all(value["state"] == "missing" for value in result["inputs"].values())


@pytest.mark.parametrize("existing", [False, True], ids=["absent", "present"])
def test_interrupted_verification_does_not_replace_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, existing: bool
) -> None:
    copy_inputs(tmp_path)
    completed = verify.run_verification(tmp_path) if existing else None

    def interrupted(_inputs: object) -> object:
        raise KeyboardInterrupt

    monkeypatch.setattr(verify, "validate_offline", interrupted)
    with pytest.raises(KeyboardInterrupt):
        verify.run_verification(tmp_path)
    path = tmp_path / verify.VERIFY_PATH
    if existing:
        assert json.loads(path.read_text()) == completed
    else:
        assert not path.exists()


def test_report_fingerprints_the_bytes_captured_before_a_later_edit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    copy_inputs(tmp_path)
    real = verify.capture_inputs
    captured_overlay = (tmp_path / "config/overlay.json").read_bytes()

    def capture(root: Path):
        snapshots, fingerprints = real(root)
        (root / "config/overlay.json").write_bytes(b'[{"changed":true}]\n')
        return snapshots, fingerprints

    monkeypatch.setattr(verify, "capture_inputs", capture)
    result = verify.run_verification(tmp_path)
    assert result["status"] == "success"
    assert result["inputs"]["overlay"] == {
        "state": "present",
        "sha256": hashlib.sha256(captured_overlay).hexdigest(),
    }
    from omnipack.report import format_reports

    assert "Evidence: stale" in format_reports(tmp_path)


def test_composition_only_change_makes_recorded_evidence_stale(tmp_path: Path) -> None:
    from omnipack.report import format_reports

    copy_inputs(tmp_path)
    result = verify.run_verification(tmp_path)
    assert result["status"] == "success"
    path = tmp_path / "config/composition.json"
    path.write_bytes(path.read_bytes() + b"\n")
    assert "Evidence: stale" in format_reports(tmp_path)


def test_report_write_error_is_wrapped(tmp_path: Path) -> None:
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


def test_nonobject_exclusion_completes_failed_evidence(tmp_path: Path) -> None:
    copy_inputs(tmp_path)
    (tmp_path / "config/deny.json").write_text("[null]")
    result = verify.run_verification(tmp_path)
    assert result["status"] == "failed"
    assert result["complete"] is True
    assert any(
        error["code"] == "invalid_composition_config"
        and "denylist[0] must be an object" in error["message"]
        for error in result["errors"]
    )
    assert json.loads((tmp_path / verify.VERIFY_PATH).read_text()) == result
