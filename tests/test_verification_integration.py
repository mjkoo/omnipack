from __future__ import annotations

import json
from email.message import Message
from pathlib import Path
from urllib.request import Request

import pytest

from obtainium_pack import cli
from obtainium_pack.http import HttpClient, HttpResponse
from obtainium_pack.settings_defaults import SETTINGS_DEFAULTS


def inputs(root: Path) -> dict[Path, bytes]:
    (root / "config").mkdir()
    for name, value in [
        ("deny.json", []),
        ("overlay.json", {}),
        ("overlay.dual.json", {}),
        ("settings.json", {}),
        ("http.json", {"credentials": {}}),
        (
            "package-ids.json",
            {"github.com/example/app": {"packageId": "app.example", "releaseId": 42}},
        ),
    ]:
        (root / "config" / name).write_text(json.dumps(value))
    app = {
        "id": "app.example",
        "name": "Example",
        "author": "Example",
        "url": "https://github.com/example/app",
        "overrideSource": "GitHub",
        "categories": [],
        "additionalSettings": json.dumps(SETTINGS_DEFAULTS["GitHub"]),
    }
    (root / "dist").mkdir()
    for variant in ("single", "dual"):
        (root / "dist" / f"{variant}-screen.json").write_text(
            json.dumps({"apps": [app], "settings": {"categories": "{}"}})
        )
    (root / ".build").mkdir()
    (root / ".build/report.json").write_text('{"schemaVersion":1,"status":"success"}')
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


def test_live_warning_only_cli_succeeds_and_report_display_is_read_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    before = inputs(tmp_path)
    requests = []

    def transport(
        _client: HttpClient,
        request: Request,
        _timeout: float,
        _max_bytes: int | None,
        *,
        prefix: bool = False,
    ) -> HttpResponse:
        requests.append(request.full_url)
        if (
            request.full_url
            == "https://api.github.com/repos/example/app/releases?per_page=100"
        ):
            body = json.dumps(
                [
                    {
                        "tag_name": "rolling",
                        "name": "Rolling",
                        "draft": False,
                        "prerelease": False,
                        "published_at": "2026-09-01T00:00:00Z",
                        "assets": [
                            {
                                "name": "app.apk",
                                "browser_download_url": "https://downloads.example/app.apk",
                            }
                        ],
                    }
                ]
            ).encode()
        else:
            assert request.full_url == "https://downloads.example/app.apk"
            body = b"apk"
        return HttpResponse(request.full_url, 200, Message(), body)

    monkeypatch.setattr(HttpClient, "_urllib_transport", transport)
    monkeypatch.chdir(tmp_path)
    assert cli.main(["verify", "--live"]) == 0
    assert len(requests) == 3
    report_path = tmp_path / ".build/verify.json"
    report_bytes = report_path.read_bytes()
    report = json.loads(report_bytes)
    assert report["status"] == "success"
    assert len(report["warnings"]) == 2
    assert {item["code"] for item in report["warnings"]} == {"github-version-format"}
    assert snapshot(tmp_path) == before
    monkeypatch.setattr(
        HttpClient,
        "_urllib_transport",
        lambda *_args, **_kwargs: pytest.fail("report request"),
    )
    monkeypatch.setattr(
        Path, "write_text", lambda *_args, **_kwargs: pytest.fail("report write")
    )
    monkeypatch.setattr(
        Path, "write_bytes", lambda *_args, **_kwargs: pytest.fail("report write")
    )
    assert cli.main(["report"]) == 0
    output = capsys.readouterr().out
    assert (
        "Evidence: current" in output
        and "Warning:" in output
        and "Mode: live" in output
    )
    assert report_path.read_bytes() == report_bytes
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("failure_at", [1, 2])
def test_cli_initial_and_final_report_write_failures_are_concise(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    failure_at: int,
) -> None:
    inputs(tmp_path)
    path = tmp_path / ".build/verify.json"
    path.write_bytes(b'{"prior":"evidence"}')
    original = Path.replace
    calls = 0

    def replace(self: Path, target: Path) -> Path:
        nonlocal calls
        if target == path:
            calls += 1
            if calls == failure_at:
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
    stored = json.loads(path.read_bytes())
    if failure_at == 1:
        assert stored == {"prior": "evidence"}
    else:
        assert stored["status"] == "running" and stored["complete"] is False
