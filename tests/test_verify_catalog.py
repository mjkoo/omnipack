from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from omnipack import verify
from omnipack.catalog import split_catalog
from omnipack.report import format_reports
from tests.test_verify import copy_inputs


@pytest.mark.parametrize("defect", ["missing", "unreadable", "malformed", "stale"])
def test_catalog_errors_fail_without_live_calls_or_input_writes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    defect: str,
) -> None:
    copy_inputs(tmp_path)
    readme = tmp_path / "README.md"
    if defect in ("missing", "unreadable"):
        readme.unlink(missing_ok=True)
        if defect == "unreadable":
            readme.mkdir()
    else:
        readme.write_bytes(
            b"bad"
            if defect == "malformed"
            else b"<!-- omnipack:catalog:start -->\nwrong\n<!-- omnipack:catalog:end -->\n"
        )
    before = {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    result = verify.run_verification(tmp_path)
    assert result["status"] == "failed"
    assert any(error["stage"] == "catalog" for error in result["errors"])
    assert all(path.read_bytes() == value for path, value in before.items())


def test_handwritten_edit_stales_evidence_but_allows_fresh_verification(
    tmp_path: Path,
) -> None:
    copy_inputs(tmp_path)
    result = verify.run_verification(tmp_path)
    assert result["status"] == "success"
    readme = tmp_path / "README.md"
    readme.write_bytes(b"New guide\n" + readme.read_bytes())
    assert "Evidence: stale" in format_reports(tmp_path)
    fresh = verify.run_verification(tmp_path)
    assert fresh["status"] == "success"
    assert fresh["inputs"]["readme"] != result["inputs"]["readme"]
    assert "Evidence: current" in format_reports(tmp_path)


def test_readme_mutation_during_verification_fingerprints_the_captured_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    copy_inputs(tmp_path)
    captured_readme = (tmp_path / "README.md").read_bytes()
    _, interior, _ = split_catalog(captured_readme)
    assert captured_readme.count(interior) == 1
    original = verify.validate_offline

    def mutate(inputs):
        # Rewrite the generated catalog interior on disk after the capture;
        # the catalog check must still read the captured bytes.
        readme = tmp_path / "README.md"
        readme.write_bytes(captured_readme.replace(interior, b"\nstale\n"))
        return original(inputs)

    monkeypatch.setattr(verify, "validate_offline", mutate)
    result = verify.run_verification(tmp_path)
    assert result["status"] == "success"
    assert result["inputs"]["readme"] == {
        "state": "present",
        "sha256": hashlib.sha256(captured_readme).hexdigest(),
    }
    assert "Evidence: stale" in format_reports(tmp_path)


def test_historical_reports_require_regeneration(tmp_path: Path) -> None:
    copy_inputs(tmp_path)
    result = verify.run_verification(tmp_path)
    assert result["status"] == "success"
    result["inputs"].pop("readme")
    result["verifier"]["version"] = "0.4.0"
    result["schemaVersion"] = 1
    result["mode"] = "live"
    (tmp_path / verify.VERIFY_PATH).write_text(json.dumps(result))
    with pytest.raises(ValueError, match="regenerate with `pack verify`"):
        format_reports(tmp_path)
