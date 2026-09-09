from __future__ import annotations

import json
from email.message import Message
from pathlib import Path
from urllib.request import Request

import pytest

from omnipack import cli
from omnipack.http import HttpClient, HttpResponse
from omnipack.settings_defaults import SETTINGS_DEFAULTS


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


@pytest.mark.parametrize(
    ("command", "request_count", "mode"),
    [
        (["verify", "--live"], 1, "live"),
        (["verify", "--live", "--probe-assets"], 2, "live-probe"),
    ],
)
def test_live_cli_modes_are_explicit_and_report_display_is_read_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    command: list[str],
    request_count: int,
    mode: str,
) -> None:
    inputs(tmp_path)
    (tmp_path / "config/http.json").write_text(
        json.dumps({"credentials": {"api.github.com": "PACK_TEST_GITHUB_TOKEN"}})
    )
    monkeypatch.setenv("PACK_TEST_GITHUB_TOKEN", "fixture-token")
    before = snapshot(tmp_path)
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
    assert cli.main(command) == 0
    assert len(requests) == request_count
    report_path = tmp_path / ".build/verify.json"
    report_bytes = report_path.read_bytes()
    report = json.loads(report_bytes)
    assert report["status"] == "success"
    assert report["mode"] == mode
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
        and f"Mode: {mode}" in output
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


@pytest.mark.parametrize(
    ("enabled", "failure", "supplement"),
    [
        ((True, False), False, False),
        ((False, True), False, False),
        ((True, True), False, True),
        ((True, True), True, False),
    ],
)
def test_latest_metadata_reuse_and_independent_variant_evidence_round_trip(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    enabled: tuple[bool, bool],
    failure: bool,
    supplement: bool,
) -> None:
    from omnipack.live_http import LiveHttpClient

    inputs(tmp_path)
    (tmp_path / "config/http.json").write_text(
        json.dumps({"credentials": {"api.github.com": "PACK_TEST_GITHUB_TOKEN"}})
    )
    monkeypatch.setenv("PACK_TEST_GITHUB_TOKEN", "fixture-token")
    for index, variant in enumerate(("single", "dual")):
        path = tmp_path / "dist" / f"{variant}-screen.json"
        pack = json.loads(path.read_text())
        settings = {
            **SETTINGS_DEFAULTS["GitHub"],
            "verifyLatestTag": enabled[index],
            "sortMethodChoice": "none",
            "apkFilterRegEx": str(index),
        }
        pack["apps"][0]["additionalSettings"] = json.dumps(settings)
        path.write_text(json.dumps(pack))
    before = snapshot(tmp_path)
    latest = {
        "tag_name": "v1.0",
        "assets": [
            {
                "name": f"app-{index}.apk",
                "browser_download_url": f"https://downloads.example/{index}.apk",
            }
            for index in range(2)
        ],
    }
    newest = {**latest, "tag_name": "v2.0"}
    releases = (
        [newest, latest]
        if not supplement
        else [{**newest, "tag_name": f"v2.{index}"} for index in range(100)]
    )
    requests: list[str] = []

    def transport(
        _client: HttpClient,
        request: Request,
        _timeout: float,
        _max_bytes: int | None,
        *,
        prefix: bool = False,
    ) -> HttpResponse:
        requests.append(request.full_url)
        assert request.get_header("Authorization") == "Bearer fixture-token"
        if request.full_url.endswith("/releases/latest"):
            headers = Message()
            headers["ETag"] = '"latest-fixture"'
            return HttpResponse(
                request.full_url,
                404 if failure else 200,
                headers,
                json.dumps(latest).encode(),
            )
        assert request.full_url.endswith("/releases?per_page=100")
        return HttpResponse(
            request.full_url, 200, Message(), json.dumps(releases).encode()
        )

    monkeypatch.setattr(HttpClient, "_urllib_transport", transport)
    monkeypatch.setattr(LiveHttpClient, "_gate", lambda _self, _url: None)
    monkeypatch.chdir(tmp_path)
    assert cli.main(["verify", "--live"]) == (1 if failure else 0)
    report = json.loads((tmp_path / ".build/verify.json").read_text())
    assert len(report["entries"]) == 2
    assert (
        requests.count("https://api.github.com/repos/example/app/releases/latest") == 1
    )
    if failure:
        assert len(requests) == 1
        for entry in report["entries"]:
            assert entry["errors"][0]["code"] == "github-request-failed"
            assert "releases/latest" in entry["errors"][0]["message"]
    else:
        assert len(requests) == 2
        for index, entry in enumerate(report["entries"]):
            resolution = entry["resolution"]
            assert resolution["raw_version"] == ("v1.0" if enabled[index] else "v2.0")
            assert resolution["inspected_count"] == (101 if supplement else 2)
            assert resolution["window_limit"] == 100
            assert resolution["candidates"][0]["name"] == f"app-{index}.apk"
            assert entry["probes"] == []
    assert snapshot(tmp_path) == before
    assert not (tmp_path / ".build/live-http-cache").exists()
    monkeypatch.setattr(
        HttpClient,
        "_urllib_transport",
        lambda *_args, **_kwargs: pytest.fail("report request"),
    )
    assert cli.main(["report"]) == 0
    assert "Evidence: current" in capsys.readouterr().out
    assert snapshot(tmp_path) == before
