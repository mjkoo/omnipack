from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from obtainium_pack import verify


def copy_inputs(root: Path) -> None:
    for relative in verify.INPUT_PATHS.values():
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(relative, target)


def test_offline_evidence_fingerprints_exact_seven_inputs(tmp_path: Path) -> None:
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
        verify.run_verification(tmp_path, live=True)
    stored = json.loads((tmp_path / verify.VERIFY_PATH).read_text())
    assert stored["complete"] is False


def test_secret_and_url_values_are_redacted_from_upstream_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    copy_inputs(tmp_path)
    token = "top-secret-token"
    monkeypatch.setenv("PACK_TEST_TOKEN", token)
    (tmp_path / "config/http.json").write_text(
        json.dumps({"credentials": {"example.test": "PACK_TEST_TOKEN"}})
    )

    class Failure(RuntimeError):
        code = "upstream"

    monkeypatch.setattr(
        "obtainium_pack.live.verify_live",
        lambda *_, **__: (_ for _ in ()).throw(
            Failure(f"https://user:{token}@example.test/file?token={token} {token}")
        ),
    )
    result = verify.run_verification(tmp_path, live=True)
    serialized = (tmp_path / verify.VERIFY_PATH).read_text()
    assert token not in serialized
    assert "user:" not in serialized
    assert "token=REDACTED" in serialized
    assert result["status"] == "failed"


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


def test_initial_report_write_error_is_wrapped(tmp_path: Path) -> None:
    (tmp_path / ".build").write_text("occupied")
    with pytest.raises(
        verify.VerificationReportError, match="cannot write verification report"
    ):
        verify.run_verification(tmp_path)


@pytest.mark.parametrize(
    "url",
    [
        "https://example.test/?token=nested-token",
        "https://[malformed/?token=nested-token",
    ],
)
def test_serialized_nested_live_evidence_redacts_secrets_and_malformed_urls(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, url: str
) -> None:
    from obtainium_pack.live import LiveEntryResult, LiveResult, ProbeEvidence
    from obtainium_pack.offline import Finding

    copy_inputs(tmp_path)
    monkeypatch.setenv("PACK_TEST_TOKEN", "nested-token")
    (tmp_path / "config/http.json").write_text(
        '{"credentials":{"example.test":"PACK_TEST_TOKEN"}}'
    )
    finding = Finding("probe", "candidate-probes-failed", f"failed {url}")
    entry = LiveEntryResult(
        "single",
        "app.example",
        0,
        "GitHub",
        None,
        (
            ProbeEvidence(
                "nested-token",
                "https://example.test/file?token=nested-token",
                False,
                failure_reason="nested-token",
            ),
        ),
        None,
        (finding,),
        (),
    )
    monkeypatch.setattr(
        "obtainium_pack.live.verify_live",
        lambda *_, **__: LiveResult((entry,), (finding,), ()),
    )
    result = verify.run_verification(tmp_path, live=True)
    serialized = (tmp_path / verify.VERIFY_PATH).read_text()
    assert "nested-token" not in serialized
    assert result["entries"][0]["probes"][0]["name"] == "REDACTED"
    if "[malformed" in url:
        assert "<invalid-url>" in serialized


def test_probe_assets_requires_live_mode(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="require live"):
        verify.run_verification(tmp_path, probe_assets=True)
