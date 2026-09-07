import json
import struct
import zipfile
from email.message import Message
from io import BytesIO
from pathlib import Path
from urllib.request import Request

import pytest

from obtainium_pack import cli
from obtainium_pack.cli import main
from obtainium_pack.http import HttpClient, HttpResponse
from obtainium_pack.merge import CompositionReport, CompositionResult
from obtainium_pack.model import App, Provenance, SourceType, Variant
from obtainium_pack.overlay import ComposedApp
from obtainium_pack.sources import IngestionReport, IngestionResult, SourceError


def fixture_apk(package_id: str) -> bytes:
    strings = ["manifest", "package", package_id]
    encoded = b""
    offsets = []
    for value in strings:
        offsets.append(len(encoded))
        raw = value.encode("utf-16-le")
        encoded += struct.pack("<H", len(value)) + raw + b"\0\0"
    header_size = 28
    pool_size = (header_size + 4 * len(strings) + len(encoded) + 3) & ~3
    pool = (
        struct.pack(
            "<HHI5I",
            1,
            header_size,
            pool_size,
            len(strings),
            0,
            0,
            header_size + 4 * len(strings),
            0,
        )
        + b"".join(struct.pack("<I", offset) for offset in offsets)
        + encoded
    )
    pool += b"\0" * (pool_size - len(pool))
    start = bytearray(56)
    struct.pack_into("<HHI", start, 0, 0x0102, 16, 56)
    struct.pack_into("<HHH", start, 24, 20, 20, 1)
    struct.pack_into("<III", start, 36, 0xFFFFFFFF, 1, 0xFFFFFFFF)
    struct.pack_into("<HBBI", start, 48, 8, 0, 3, 2)
    manifest = bytearray(8) + pool + start
    struct.pack_into("<HHI", manifest, 0, 3, 8, len(manifest))
    stream = BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("AndroidManifest.xml", manifest)
    return stream.getvalue()


def test_no_command_is_an_error(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main([])
    assert "required" in capsys.readouterr().err


def test_verify_missing_inputs_fails_and_report_displays_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["verify"]) == 1
    assert main(["report"]) == 0


def test_live_verification_stops_before_network_when_offline_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = tmp_path / "config"
    config.mkdir()
    for name, value in (
        ("deny.json", []),
        ("overlay.json", {}),
        ("overlay.dual.json", {}),
        ("settings.json", {}),
        ("http.json", {"credentials": {}}),
    ):
        (config / name).write_text(json.dumps(value))
    (tmp_path / "dist").mkdir()
    (tmp_path / "dist/single-screen.json").write_text("not json")
    (tmp_path / "dist/dual-screen.json").write_text("not json")
    monkeypatch.setattr(
        "obtainium_pack.live.verify_live",
        lambda *_: pytest.fail("live verification must not run"),
    )
    monkeypatch.chdir(tmp_path)
    assert main(["verify", "--live"]) == 1


def test_build_writes_both_variants_and_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "config").mkdir()
    (tmp_path / "config/settings.json").write_text("{}", encoding="utf-8")
    for name, value in (
        ("deny.json", []),
        ("overlay.json", {}),
        ("overlay.dual.json", {}),
    ):
        (tmp_path / "config" / name).write_text(json.dumps(value), encoding="utf-8")
    app = ComposedApp(
        Variant.SINGLE,
        Provenance("extras", "https://example.test/app"),
        {
            "id": "app.test",
            "url": "https://example.test/app",
            "name": "App",
            "overrideSource": "HTML",
            "categories": [],
        },
    )
    composed = CompositionResult(
        {
            Variant.SINGLE: [app],
            Variant.DUAL: [ComposedApp(Variant.DUAL, app.provenance, dict(app.data))],
        },
        CompositionReport(),
    )
    monkeypatch.setattr(
        cli,
        "_ingest_for_build",
        lambda root, report=None: IngestionResult([], report or IngestionReport()),
    )
    monkeypatch.setattr(cli, "compose", lambda *args, **kwargs: composed)
    monkeypatch.chdir(tmp_path)

    assert cli.main(["build"]) == 0
    assert (
        json.loads((tmp_path / "dist/single-screen.json").read_text())["apps"][0]["id"]
        == "app.test"
    )
    assert (
        json.loads((tmp_path / "dist/dual-screen.json").read_text())["apps"][0]["id"]
        == "app.test"
    )
    report = json.loads((tmp_path / ".build/report.json").read_text())
    assert report["status"] == "success"
    assert report["changes"]["single"]["added"] == ["app.test"]
    assert not (tmp_path / "dist/report.json").exists()


def test_build_failure_returns_nonzero_and_writes_diagnostic_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    before = b'{"apps":[{"id":"existing.app"}]}\n'
    for name in ("single-screen.json", "dual-screen.json"):
        (dist / name).write_bytes(before)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        cli,
        "_ingest_for_build",
        lambda root, report=None: (_ for _ in ()).throw(
            SourceError("rjny", "HTTP 503")
        ),
    )
    assert cli.main(["build"]) == 1
    assert "rjny" in capsys.readouterr().err
    report = json.loads((tmp_path / ".build/report.json").read_text())
    assert report["status"] == "failed"
    assert report["stage"] == "ingestion"
    assert "HTTP 503" in report["error"]
    assert report["changes"] is None
    for name in ("single-screen.json", "dual-screen.json"):
        assert (dist / name).read_bytes() == before


def test_cached_resolution_survives_a_later_render_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = tmp_path / "config"
    config.mkdir()
    for name, value in (
        ("deny.json", []),
        ("overlay.json", {}),
        ("overlay.dual.json", {}),
        ("settings.json", {}),
    ):
        (config / name).write_text(json.dumps(value), encoding="utf-8")
    dist = tmp_path / "dist"
    dist.mkdir()
    before = {"settings": {}, "apps": [{"id": "old.id"}]}
    for name in ("single-screen.json", "dual-screen.json"):
        (dist / name).write_text(json.dumps(before), encoding="utf-8")

    composed = CompositionResult(
        {variant: [] for variant in Variant}, CompositionReport()
    )

    def resolved(_root: Path, report: IngestionReport | None = None) -> IngestionResult:
        (config / "package-ids.json").write_text(
            '{"github.com/new/project":{"packageId":"app.new","releaseId":1}}\n',
            encoding="utf-8",
        )
        return IngestionResult([], report or IngestionReport())

    monkeypatch.setattr(cli, "_ingest_for_build", resolved)
    monkeypatch.setattr(cli, "compose", lambda *args, **kwargs: composed)
    monkeypatch.setattr(
        "obtainium_pack.build.render",
        lambda *_args: (_ for _ in ()).throw(ValueError("render failed")),
    )
    monkeypatch.chdir(tmp_path)
    assert main(["build"]) == 1
    assert "app.new" in (config / "package-ids.json").read_text()
    for name in ("single-screen.json", "dual-screen.json"):
        assert json.loads((dist / name).read_text()) == before


@pytest.mark.parametrize("existing", [False, True])
def test_build_runs_the_real_pipeline_with_transport_only_fixtures(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, existing: bool
) -> None:
    config = tmp_path / "config"
    config.mkdir()
    source_config = {
        "rjny": {"repo": "fixture/rjny", "branch": "main", "path": "apps.json"},
        "bboi": {
            "codeberg_repo": "fixture/bboi",
            "single_asset_pattern": "single-*.json",
            "dual_asset_pattern": "dual-*.json",
        },
        "codm": {"readme_url": "https://fixture.test/readme"},
    }
    files: dict[str, object] = {
        "sources.json": source_config,
        "http.json": {"credentials": {}},
        "extras.json": [],
        "package-ids.json": {
            "github.com/fixture/retained": {"packageId": "app.retained", "releaseId": 1}
        },
        "deny.json": [],
        "overlay.json": {},
        "overlay.dual.json": {},
        "settings.json": {},
    }
    for name, value in files.items():
        (config / name).write_text(json.dumps(value), encoding="utf-8")
    record = {
        "id": "app.fixture",
        "url": "https://example.test/app",
        "name": "Fixture",
        "overrideSource": "HTML",
    }
    if existing:
        (tmp_path / "dist").mkdir()
        (tmp_path / "dist/dual-screen.json").write_text(
            json.dumps({"apps": [{"id": "app.generated"}]})
        )
    responses = {
        "https://raw.githubusercontent.com/fixture/rjny/main/apps.json": json.dumps(
            {"apps": [record]}
        ),
        "https://codeberg.org/api/v1/repos/fixture/bboi/releases/latest": json.dumps(
            {
                "assets": [
                    {
                        "name": "single-1.json",
                        "browser_download_url": "https://fixture.test/single",
                    },
                    {
                        "name": "dual-1.json",
                        "browser_download_url": "https://fixture.test/dual",
                    },
                ]
            }
        ),
        "https://fixture.test/single": '{"apps":[]}',
        "https://fixture.test/dual": '{"apps":[]}',
        "https://fixture.test/readme": (
            "| Project |\n| --- |\n"
            "[website](https://example.test/page) "
            "[generated](https://github.com/fixture/generated) "
            "[missing](https://github.com/fixture/missing) "
            "[retained](https://github.com/fixture/retained)"
        ),
        "https://api.github.com/repos/fixture/generated/releases/latest": json.dumps(
            {
                "id": 7,
                "assets": [
                    {
                        "name": "app.apk",
                        "browser_download_url": "https://fixture.test/app.apk",
                    }
                ],
            }
        ),
    }

    for project in ("missing", "retained"):
        responses[f"https://api.github.com/repos/fixture/{project}/releases/latest"] = (
            json.dumps({"id": 8, "assets": []})
        )

    def transport(
        _client: HttpClient, request: Request, _timeout: float, _max_bytes: int | None
    ) -> HttpResponse:
        if request.full_url == "https://fixture.test/app.apk":
            body = b"" if request.method == "HEAD" else fixture_apk("app.generated")
        else:
            body = responses[request.full_url].encode()
        return HttpResponse(request.full_url, 200, Message(), body)

    monkeypatch.setattr(HttpClient, "_urllib_transport", transport)
    monkeypatch.chdir(tmp_path)
    assert main(["build"]) == 0
    for name in ("single-screen.json", "dual-screen.json"):
        assert (
            json.loads((tmp_path / "dist" / name).read_text())["apps"][0]["id"]
            == "app.fixture"
        )
    assert (
        json.loads((tmp_path / ".build/report.json").read_text())["skipped"][0]["url"]
        == "https://example.test/page"
    )
    report = json.loads((tmp_path / ".build/report.json").read_text())
    assert report["status"] == "success"
    assert report["generated"] == [
        {
            "source": "codm2000",
            "url": "https://github.com/fixture/generated",
            "id": "app.generated",
            "status": "resolved",
        },
        {
            "source": "codm2000",
            "url": "https://github.com/fixture/retained",
            "id": "app.retained",
            "status": "reused",
        },
    ]
    failure = "APK resolution failed: latest release has no eligible APK assets"
    assert report["unresolved"] == [
        {
            "source": "codm2000",
            "url": "https://github.com/fixture/missing",
            "failure": failure,
        }
    ]
    assert report["retainedFailures"] == [
        {
            "source": "codm2000",
            "url": "https://github.com/fixture/retained",
            "id": "app.retained",
            "failure": failure,
        }
    ]
    assert report["changes"]["dual"] == {
        "added": ["app.fixture", "app.retained"]
        if existing
        else ["app.fixture", "app.generated", "app.retained"],
        "removed": [],
    }
    assert not (tmp_path / "dist/report.json").exists()
    cache = json.loads((config / "package-ids.json").read_text())
    assert cache["github.com/fixture/generated"] == {
        "packageId": "app.generated",
        "releaseId": 7,
    }


@pytest.mark.parametrize("stage", ["rendering", "report writing", "publication"])
@pytest.mark.parametrize("existing", [False, True])
def test_failed_build_reports_exact_stage_and_preserves_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stage: str, existing: bool
) -> None:
    config = tmp_path / "config"
    config.mkdir()
    for name, value in (
        ("deny.json", []),
        ("overlay.json", {}),
        ("overlay.dual.json", {}),
        ("settings.json", {}),
    ):
        (config / name).write_text(json.dumps(value))
    before = b'{"apps":[{"id":"before.id"}]}\n'
    paths = [
        tmp_path / "dist" / name for name in ("single-screen.json", "dual-screen.json")
    ]
    if existing:
        paths[0].parent.mkdir()
        for path in paths:
            path.write_bytes(before)
    monkeypatch.setattr(
        cli, "_ingest_for_build", lambda root, report: IngestionResult([], report)
    )
    if stage == "rendering":
        from obtainium_pack import build as build_module

        real_render = build_module.render
        renders = 0

        def render(*args):
            nonlocal renders
            renders += 1
            if renders == 2:
                raise ValueError("injected rendering failure")
            return real_render(*args)

        monkeypatch.setattr(build_module, "render", render)
    else:
        real_replace = Path.replace
        failed = False

        def replace(source: Path, target: Path) -> Path:
            nonlocal failed
            target_path = Path(target)
            selected = (
                target_path.name == "report.json"
                if stage == "report writing"
                else target_path.name == "dual-screen.json"
            )
            if selected and not failed:
                failed = True
                raise OSError(f"injected {stage} failure")
            return real_replace(source, target)

        monkeypatch.setattr(Path, "replace", replace)
    monkeypatch.chdir(tmp_path)
    assert main(["build"]) == 1
    for path in paths:
        if existing:
            assert path.read_bytes() == before
        else:
            assert not path.exists()
    report = json.loads((tmp_path / ".build/report.json").read_text())
    assert report["stage"] == stage
    assert report["error"] == f"injected {stage} failure"
    assert report["changes"] == {
        variant.value: {"added": [], "removed": ["before.id"] if existing else []}
        for variant in Variant
    }


def test_composition_failure_preserves_collected_diagnostics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = tmp_path / "config"
    config.mkdir()
    for name, value in (
        (
            "deny.json",
            [
                {"id": "removed.app", "reason": "excluded"},
                {"id": "stale.app", "reason": "obsolete"},
            ],
        ),
        ("overlay.json", {"missing.app": {"name": "Missing"}}),
        ("overlay.dual.json", {}),
    ):
        (config / name).write_text(json.dumps(value), encoding="utf-8")
    apps = [
        App(
            package_id,
            "https://example.test/app",
            source,
            SourceType.HTML,
            (),
            variant,
            Provenance(source, "https://example.test/catalog"),
        )
        for variant in Variant
        for package_id, source in (
            ("collision.app", "rjny"),
            ("collision.app", "extras"),
            ("removed.app", "extras"),
        )
    ]
    monkeypatch.setattr(
        cli, "_ingest_for_build", lambda root, report: IngestionResult(apps, report)
    )
    monkeypatch.chdir(tmp_path)

    assert main(["build"]) == 1
    report = json.loads((tmp_path / ".build/report.json").read_text())
    assert report["stage"] == "composition"
    assert "missing.app" in report["error"]
    assert report["displacements"] == [
        {
            "id": "collision.app",
            "variant": variant.value,
            "winner_source": "extras",
            "loser_source": "rjny",
            "differing_fields": ["name"],
        }
        for variant in Variant
    ]
    assert report["denylistRemovals"] == [
        {"id": "removed.app", "variant": variant.value, "reason": "excluded"}
        for variant in Variant
    ]
    assert report["staleExclusions"] == [
        {"id": "stale.app", "variant": None, "reason": "obsolete"}
    ]
    assert report["changes"] is None
    assert not (tmp_path / "dist").exists()


def test_offline_gate_preserves_pair_and_standalone_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = tmp_path / "config"
    config.mkdir()
    for name, value in (
        ("deny.json", []),
        ("overlay.json", {}),
        ("overlay.dual.json", {}),
        ("settings.json", {}),
    ):
        (config / name).write_text(json.dumps(value))
    dist = tmp_path / "dist"
    dist.mkdir()
    before = b'{"settings":{"categories":"{}"},"apps":[]}\n'
    for name in ("single-screen.json", "dual-screen.json"):
        (dist / name).write_bytes(before)
    verify_path = tmp_path / ".build/verify.json"
    verify_path.parent.mkdir()
    verify_path.write_bytes(b'{"keep":true}\n')
    composed = CompositionResult(
        {variant: [] for variant in Variant}, CompositionReport()
    )
    monkeypatch.setattr(
        cli, "_ingest_for_build", lambda root, report: IngestionResult([], report)
    )
    monkeypatch.setattr(cli, "compose", lambda *_args, **_kwargs: composed)
    calls = 0

    def render(*_args: object) -> str:
        nonlocal calls
        calls += 1
        return (
            '{"settings":{"categories":"{}"},"apps":[]}\n' if calls == 1 else "not json"
        )

    monkeypatch.setattr("obtainium_pack.build.render", render)
    monkeypatch.chdir(tmp_path)
    assert main(["build"]) == 1
    assert all(
        (dist / name).read_bytes() == before
        for name in ("single-screen.json", "dual-screen.json")
    )
    assert verify_path.read_bytes() == b'{"keep":true}\n'
    report = json.loads((tmp_path / ".build/report.json").read_text())
    assert report["stage"] == "offline verification"
    assert report["offlineVerification"]["status"] == "failed"
    assert report["changes"] == {
        variant.value: {"added": [], "removed": []} for variant in Variant
    }
