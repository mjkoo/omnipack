from __future__ import annotations

import hashlib
import json
import tempfile
import urllib.error
from collections.abc import Callable, Iterable
from datetime import UTC, datetime, timedelta
from email.message import Message
from pathlib import Path
from typing import Any, Self
from urllib.request import Request

import pytest

from omnipack.archive import Outcome
from omnipack.archive.run import (
    Archiver,
    ArchiveReport,
    TargetReport,
    render_summary,
    run_archive,
    version_slug,
    write_archive_report,
)
from omnipack.archive.source import CaptureOutcome, CaptureResult
from omnipack.archive.store import StoreError, StoreFailure
from omnipack.archive.targets import select_targets
from omnipack.http import HttpClient
from omnipack.report_model import Status
from tests.http_support import RoutedTransport
from tests.test_archive_github import RELEASES, gh_release

APP = "apps/github.com/owner/app/releases"
BUNDLE = "apps/github.com/owner/app/source/repo.bundle"
APK_URL = "https://github.com/owner/app/releases/download/v1/app.apk"
SOURCE_URL = "https://github.com/owner/app"


class FakeBucket:
    def __init__(self, fail: Exception | None = None) -> None:
        self.objects: dict[str, bytes] = {}
        self.writes: list[str] = []
        self.deletes: list[list[str]] = []
        self.stored_at: dict[str, datetime] = {}
        self.skew = timedelta()
        self.fail = fail

    def exists(self, key: str) -> bool:
        if self.fail:
            raise self.fail
        return key in self.objects

    def put_json(self, key: str, document: Any) -> None:
        self._store(key, json.dumps(document).encode())

    def upload_file(self, path: Path, key: str) -> None:
        self._store(key, path.read_bytes())

    def _store(self, key: str, data: bytes) -> None:
        self.writes.append(key)
        self.objects[key] = data
        # Every write is a minute later than the one before it.
        self.stored_at[key] = (
            datetime(2026, 1, 1, tzinfo=UTC)
            + timedelta(minutes=len(self.writes))
            + self.skew
        )

    def list_keys(self, prefix: str) -> list[tuple[str, datetime]]:
        return [
            (key, self.stored_at[key])
            for key in sorted(self.objects)
            if key.startswith(prefix)
        ]

    def delete(self, keys: Iterable[str]) -> None:
        batch = list(keys)
        self.deletes.append(batch)
        for key in batch:
            del self.objects[key]
            del self.stored_at[key]


class Body:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.url = "https://example.test/file"
        self.status = 200
        self.headers = Message()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def read1(self, size: int = -1) -> bytes:
        data, self.data = self.data, b""
        return data


class Downloads:
    """Serve file bodies by URL (an int is an HTTP error status)."""

    def __init__(self, files: dict[str, bytes | int]) -> None:
        self.files = files
        self.urls: list[str] = []
        self.requests: list[Request] = []

    def __call__(self, request: Request, timeout: float) -> Body:
        self.urls.append(request.full_url)
        self.requests.append(request)
        data = self.files[request.full_url]
        if isinstance(data, int):
            raise urllib.error.HTTPError(
                request.full_url, data, "fixture", Message(), None
            )
        return Body(data)


def entry(url: str = SOURCE_URL, **extra: object) -> dict[str, object]:
    return {
        "id": "x",
        "name": "App",
        "url": url,
        "overrideSource": "GitHub",
        "additionalSettings": "{}",
        **extra,
    }


def write_packs(root: Path, apps: list[dict[str, object]]) -> None:
    (root / "dist").mkdir(exist_ok=True)
    for name in ("single-screen.json", "dual-screen.json"):
        (root / "dist" / name).write_text(
            json.dumps({"settings": {}, "apps": apps if "single" in name else []})
        )


def capture_ok(url: str, destination: Path, work: Path, **_: Any) -> CaptureResult:
    destination.write_bytes(b"bundle")
    return CaptureResult(CaptureOutcome.CAPTURED)


def capture_fails(url: str, destination: Path, work: Path, **_: Any) -> CaptureResult:
    return CaptureResult(CaptureOutcome.FAILED, "git clone failed: gone")


def capture_forbidden(*args: Any, **kwargs: Any) -> CaptureResult:
    raise AssertionError("source capture must not run")


class World:
    def __init__(
        self,
        releases: list[dict[str, Any]],
        files: dict[str, bytes | int] | None = None,
        capture: Callable[..., CaptureResult] = capture_ok,
        bucket: FakeBucket | None = None,
    ) -> None:
        self.bucket = bucket or FakeBucket()
        self.api = RoutedTransport({RELEASES: releases})
        self.downloads = Downloads(files or {APK_URL: b"apk"})
        self.http = HttpClient(
            transport=self.api,
            stream_transport=self.downloads,
            sleep=lambda _s: None,
        )
        self.capture = capture

    def archiver(self, **kwargs: Any) -> Archiver:
        return Archiver(self.bucket, self.http, capture=self.capture, **kwargs)

    def process(self) -> dict[str, Any]:
        [target] = select_targets_for(entry())
        return dict(self.archiver().process(target))


def select_targets_for(*apps: dict[str, object]) -> list[Any]:
    with tempfile.TemporaryDirectory() as root:
        write_packs(Path(root), list(apps))
        return select_targets(Path(root))


def release_v1() -> dict[str, Any]:
    return gh_release("v1", "2024-01-01T00:00:00Z", "app.apk", body="notes")


def test_version_slug_is_sanitized_truncated_and_tagged_with_a_digest() -> None:
    assert version_slug("1.0") != version_slug("1_0")
    assert version_slug("a/b c").startswith("a_b_c-")
    assert len(version_slug("x" * 500)) == 80 + 9
    assert version_slug("").startswith("-")


def test_a_new_version_stores_every_object_and_the_manifest_last() -> None:
    world = World([release_v1()])

    report = world.process()

    assert report["outcome"] == Outcome.ARCHIVED
    prefix = f"{APP}/{version_slug('v1')}"
    assert world.bucket.writes[-1] == f"{prefix}/manifest.json"
    assert set(world.bucket.objects) == {
        f"{prefix}/assets/app.apk",
        f"{prefix}/release.json",
        f"{prefix}/release.md",
        f"{prefix}/manifest.json",
        BUNDLE,
    }
    manifest = json.loads(world.bucket.objects[f"{prefix}/manifest.json"])
    keys = {o["key"] for o in manifest["objects"]}
    assert keys == {"assets/app.apk", "release.json", "release.md"}
    apk = next(o for o in manifest["objects"] if o["key"] == "assets/app.apk")
    assert apk["size"] == 3 and len(apk["sha256"]) == 64
    assert manifest["version"] == "v1"
    assert manifest["sourceHistory"] == {
        "key": BUNDLE,
        "size": 6,
        "sha256": hashlib.sha256(b"bundle").hexdigest(),
    }


def test_a_new_version_is_stored_beside_the_old_one_and_a_return_touches_nothing() -> (
    None
):
    world = World([release_v1()])
    world.process()
    first = {key: data for key, data in world.bucket.objects.items() if key != BUNDLE}

    world.api.answers[RELEASES] = [gh_release("v2", "2024-02-01T00:00:00Z", "app.apk")]
    world.downloads.files[
        "https://github.com/owner/app/releases/download/v2/app.apk"
    ] = b"2"
    assert world.process()["outcome"] == Outcome.ARCHIVED
    assert first.items() <= world.bucket.objects.items()

    world.api.answers[RELEASES] = [release_v1()]
    world.bucket.writes.clear()
    world.downloads.urls.clear()
    world.capture = capture_forbidden
    assert world.process()["outcome"] == Outcome.UNCHANGED
    assert world.bucket.writes == [] and world.downloads.urls == []
    assert first.items() <= world.bucket.objects.items()


def test_an_asset_404_leaves_no_manifest_and_fails_the_target() -> None:
    world = World([release_v1()], {APK_URL: 404})

    report = world.process()

    assert report["outcome"] == Outcome.FAILED
    assert report["error"]
    assert not any(key.endswith("manifest.json") for key in world.bucket.objects)


def test_a_version_that_failed_partway_is_archived_in_full_by_the_next_run() -> None:
    notes = "https://github.com/owner/app/releases/download/v1/notes.txt"
    world = World(
        [gh_release("v1", "2024-01-01T00:00:00Z", "app.apk", "notes.txt")],
        {APK_URL: b"apk", notes: 404},
    )
    assert world.process()["outcome"] == Outcome.FAILED
    prefix = f"{APP}/{version_slug('v1')}"
    assert f"{prefix}/assets/app.apk" in world.bucket.objects

    world.downloads.files[notes] = b"notes"
    world.bucket.writes.clear()
    assert world.process()["outcome"] == Outcome.ARCHIVED

    assert world.bucket.writes[-1] == f"{prefix}/manifest.json"
    assert {f"{prefix}/assets/app.apk", f"{prefix}/assets/notes.txt"} <= set(
        world.bucket.writes
    )
    manifest = json.loads(world.bucket.objects[f"{prefix}/manifest.json"])
    assert {o["key"] for o in manifest["objects"]} == {
        "assets/app.apk",
        "assets/notes.txt",
        "release.json",
    }


def test_a_clone_failure_archives_without_a_bundle_and_records_why() -> None:
    world = World([release_v1()], capture=capture_fails)

    assert world.process()["outcome"] == Outcome.ARCHIVED

    manifest = json.loads(
        world.bucket.objects[f"{APP}/{version_slug('v1')}/manifest.json"]
    )
    assert manifest["sourceHistory"] == {"reason": "git clone failed: gone"}
    assert BUNDLE not in world.bucket.objects


def test_a_failed_capture_leaves_the_previous_bundle_and_records_why() -> None:
    world = World([release_v1()])
    world.process()
    previous = world.bucket.objects[BUNDLE]

    world.api.answers[RELEASES] = [gh_release("v2", "2024-02-01T00:00:00Z", "app.apk")]
    world.downloads.files[
        "https://github.com/owner/app/releases/download/v2/app.apk"
    ] = b"2"
    world.capture = capture_fails
    assert world.process()["outcome"] == Outcome.ARCHIVED

    assert world.bucket.objects[BUNDLE] == previous
    manifest = json.loads(
        world.bucket.objects[f"{APP}/{version_slug('v2')}/manifest.json"]
    )
    assert manifest["sourceHistory"] == {"reason": "git clone failed: gone"}


def test_a_new_version_replaces_the_targets_bundle() -> None:
    world = World([release_v1()])
    world.process()

    def capture_new(url: str, destination: Path, work: Path, **_: Any) -> CaptureResult:
        destination.write_bytes(b"newer")
        return CaptureResult(CaptureOutcome.CAPTURED)

    world.capture = capture_new
    world.api.answers[RELEASES] = [gh_release("v2", "2024-02-01T00:00:00Z", "app.apk")]
    world.downloads.files[
        "https://github.com/owner/app/releases/download/v2/app.apk"
    ] = b"2"
    world.process()

    assert world.bucket.objects[BUNDLE] == b"newer"
    assert [k for k in world.bucket.objects if k.endswith("repo.bundle")] == [BUNDLE]


def archive_versions(world: World, *versions: str) -> None:
    for version in versions:
        world.api.answers[RELEASES] = [
            gh_release(version, "2024-01-01T00:00:00Z", "app.apk")
        ]
        world.downloads.files[
            f"https://github.com/owner/app/releases/download/{version}/app.apk"
        ] = b"x"
        assert world.process()["outcome"] == Outcome.ARCHIVED


def test_a_fourth_version_prunes_the_oldest_manifest_first() -> None:
    world = World([release_v1()])
    archive_versions(world, "v1", "v2", "v3")
    assert world.bucket.deletes == []

    archive_versions(world, "v4")

    oldest = f"{APP}/{version_slug('v1')}/"
    assert world.bucket.deletes[0] == [f"{oldest}manifest.json"]
    assert [sorted(batch) for batch in world.bucket.deletes[1:]] == [
        [
            f"{oldest}assets/app.apk",
            f"{oldest}release.json",
        ]
    ]
    assert not [k for k in world.bucket.objects if k.startswith(oldest)]
    for kept in ("v2", "v3", "v4"):
        assert f"{APP}/{version_slug(kept)}/manifest.json" in world.bucket.objects
    assert BUNDLE in world.bucket.objects


def test_an_incomplete_prefix_is_not_pruned(tmp_path: Path) -> None:
    world = World([release_v1()])
    orphan = f"{APP}/{version_slug('half')}/assets/app.apk"
    (tmp_path / "half").write_bytes(b"half")
    world.bucket.upload_file(tmp_path / "half", orphan)

    archive_versions(world, "v1", "v2", "v3", "v4")

    assert orphan in world.bucket.objects
    assert world.bucket.deletes
    assert all(orphan not in batch for batch in world.bucket.deletes)


def test_the_version_just_archived_is_never_pruned() -> None:
    world = World([release_v1()])
    archive_versions(world, "v1", "v2", "v3")
    # The bucket's clock jumps back, so the new manifest ranks as the oldest.
    world.bucket.skew = timedelta(days=-1)

    archive_versions(world, "v4")

    assert f"{APP}/{version_slug('v4')}/manifest.json" in world.bucket.objects
    assert world.bucket.deletes == []


def test_a_pruned_version_selected_again_is_archived_again() -> None:
    world = World([release_v1()])
    archive_versions(world, "v1", "v2", "v3", "v4")
    assert f"{APP}/{version_slug('v1')}/manifest.json" not in world.bucket.objects

    archive_versions(world, "v1")

    assert f"{APP}/{version_slug('v1')}/manifest.json" in world.bucket.objects


def test_a_capture_cut_short_by_the_deadline_abandons_the_target() -> None:
    world = World([release_v1()])
    world.http.clock = lambda: 0.0

    def late(url: str, destination: Path, work: Path, **_: Any) -> CaptureResult:
        return CaptureResult(CaptureOutcome.EXPIRED, "timed out at the run deadline")

    world.capture = late
    [target] = select_targets_for(entry())
    report = world.archiver(deadline=50.0).process(target)

    assert report["outcome"] == Outcome.FAILED
    assert not any(key.endswith("manifest.json") for key in world.bucket.objects)


def test_an_html_target_through_an_intermediate_page_stores_only_its_file() -> None:
    page = "https://example.test/dl"
    mirror = "https://example.test/mirror/"
    apk = "https://example.test/mirror/app-1.2.apk"
    html_entry = entry(
        page,
        overrideSource="HTML",
        additionalSettings=json.dumps(
            {
                "intermediateLink": [{"customLinkFilterRegex": "/mirror/$"}],
                "versionExtractionRegEx": r"[0-9.]+(?=\.apk)",
            }
        ),
    )
    transport = RoutedTransport(
        {page: f'<a href="{mirror}">mirror</a>', mirror: f'<a href="{apk}">get</a>'}
    )
    downloads = Downloads({apk: b"apk"})
    bucket = FakeBucket()
    http = HttpClient(transport=transport, stream_transport=downloads)
    [target] = select_targets_for(html_entry)

    report = Archiver(bucket, http, capture=capture_forbidden).process(target)

    assert report["outcome"] == Outcome.ARCHIVED
    (manifest_key,) = [k for k in bucket.objects if k.endswith("manifest.json")]
    manifest = json.loads(bucket.objects[manifest_key])
    assert manifest["fetchedUrls"] == [page, mirror]
    assert "sourceHistory" not in manifest
    assert [o["key"] for o in manifest["objects"]] == ["assets/app-1.2.apk"]
    assert not any(key.endswith("repo.bundle") for key in bucket.objects)


def test_an_html_targets_request_headers_reach_its_pages_and_its_download() -> None:
    page = "https://example.test/dl"
    apk = "https://example.test/app-1.2.apk"
    html_entry = entry(
        page,
        overrideSource="HTML",
        additionalSettings=json.dumps(
            {
                "versionExtractionRegEx": r"[0-9.]+(?=\.apk)",
                "requestHeader": [{"requestHeader": "X-Mirror: m.example"}],
            }
        ),
    )
    transport = RoutedTransport({page: f'<a href="{apk}">get</a>'})
    downloads = Downloads({apk: b"apk"})
    http = HttpClient(transport=transport, stream_transport=downloads)
    [target] = select_targets_for(html_entry)

    report = Archiver(FakeBucket(), http, capture=capture_fails).process(target)

    assert report["outcome"] == Outcome.ARCHIVED
    sent = [*transport.requests, *downloads.requests]
    assert [request.full_url for request in sent] == [page, apk]
    assert all(request.get_header("X-mirror") == "m.example" for request in sent)


def test_an_unchanged_html_target_downloads_nothing() -> None:
    page = "https://example.test/dl"
    apk = "https://example.test/app-1.2.apk"
    html_entry = entry(
        page,
        overrideSource="HTML",
        additionalSettings=json.dumps({"versionExtractionRegEx": r"[0-9.]+(?=\.apk)"}),
    )
    downloads = Downloads({apk: b"apk"})
    http = HttpClient(
        transport=RoutedTransport({page: f'<a href="{apk}">get</a>'}),
        stream_transport=downloads,
    )
    bucket = FakeBucket()
    [target] = select_targets_for(html_entry)
    archiver = Archiver(bucket, http, capture=capture_fails)
    archiver.process(target)
    bucket.writes.clear()
    downloads.urls.clear()

    assert archiver.process(target)["outcome"] == Outcome.UNCHANGED
    assert downloads.urls == [] and bucket.writes == []


def test_repeated_asset_names_never_collide_with_a_prefixed_name() -> None:
    names = ["2-x.apk", "x.apk", "x.apk"]
    base = "https://github.com/owner/app/releases/download/v1"
    world = World(
        [gh_release("v1", "2024-01-01T00:00:00Z", *names)],
        files={f"{base}/{name}": b"data" for name in names},
    )

    assert world.process()["outcome"] == Outcome.ARCHIVED

    [manifest_key] = [k for k in world.bucket.objects if k.endswith("manifest.json")]
    manifest = json.loads(world.bucket.objects[manifest_key])
    keys = [o["key"] for o in manifest["objects"] if o["key"].startswith("assets/")]
    assert len(keys) == len(set(keys)) == 3


def test_a_dry_run_resolves_with_no_download_clone_or_write() -> None:
    world = World([release_v1()])
    calls: list[str] = []
    [target] = select_targets_for(entry())

    report = Archiver(
        None,
        world.http,
        capture=lambda *a, **k: calls.append("clone"),  # ty: ignore[invalid-argument-type]
    ).process(target)

    assert report == {"name": "App", "url": SOURCE_URL, "version": "v1"}
    assert world.downloads.urls == [] and calls == []


def test_a_track_only_target_is_skipped_without_a_request() -> None:
    world = World([release_v1()], capture=capture_forbidden)
    [target] = select_targets_for(
        entry(additionalSettings=json.dumps({"trackOnly": True}))
    )

    report = world.archiver().process(target)

    assert report["outcome"] == Outcome.SKIPPED
    assert world.api.requests == [] and world.downloads.urls == []
    assert world.bucket.writes == []


def test_outcomes_map_for_no_release_and_skipped(tmp_path: Path) -> None:
    world = World([])
    write_packs(
        tmp_path,
        [entry(), entry("https://example.test/x", overrideSource="Other")],
    )

    report = run_archive(tmp_path, world.bucket, http=world.http)

    assert [t["outcome"] for t in report["targets"]] == [
        Outcome.NO_RELEASE,
        Outcome.SKIPPED,
    ]
    assert report["status"] == Status.SUCCESS


def test_a_deleted_repository_does_not_stop_healthy_targets(tmp_path: Path) -> None:
    gone = "https://api.github.com/repos/owner/gone/releases?per_page=100"
    world = World([release_v1()])
    old_apk = "https://github.com/owner/gone/releases/download/v0/gone.apk"
    old = gh_release("v0", "2023-01-01T00:00:00Z", "gone.apk")
    old["assets"][0]["browser_download_url"] = old_apk
    world.api.answers[gone] = [old]
    world.downloads.files[old_apk] = b"old"
    [gone_target] = select_targets_for(entry("https://github.com/owner/gone"))
    assert world.archiver().process(gone_target)["outcome"] == Outcome.ARCHIVED
    earlier = dict(world.bucket.objects)
    world.api.answers[gone] = 404
    write_packs(tmp_path, [entry("https://github.com/owner/gone"), entry()])

    report = run_archive(tmp_path, world.bucket, http=world.http, capture=capture_ok)

    assert [t["outcome"] for t in report["targets"]] == [
        Outcome.UNREACHABLE,
        Outcome.ARCHIVED,
    ]
    assert earlier.items() <= world.bucket.objects.items()


def test_an_exhausted_budget_leaves_the_rest_not_checked(tmp_path: Path) -> None:
    now = [0.0]
    world = World([release_v1()])
    world.http.clock = lambda: now[0]
    inner = world.bucket.upload_file

    def spend(path: Path, key: str) -> None:
        now[0] = 10.0
        inner(path, key)

    world.bucket.upload_file = spend  # ty: ignore[invalid-assignment]
    write_packs(tmp_path, [entry(), entry("https://github.com/owner/other")])

    report = run_archive(
        tmp_path, world.bucket, http=world.http, budget=5.0, capture=capture_ok
    )

    assert [t.get("outcome") for t in report["targets"]] == [
        Outcome.FAILED,
        Outcome.NOT_CHECKED,
    ]
    assert report["status"] == Status.SUCCESS


def test_a_bucket_error_ends_the_run_failed_and_publishes_only_a_fixed_message(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    detail = "Could not connect to https://s3.secret.example/private-bucket"
    error = StoreError(StoreFailure.UNREACHABLE, detail)
    world = World([release_v1()], bucket=FakeBucket(error))
    write_packs(tmp_path, [entry(), entry("https://github.com/owner/other")])

    report = run_archive(tmp_path, world.bucket, http=world.http)
    write_archive_report(tmp_path, report)

    assert report["status"] == Status.FAILED
    assert report["error"] == "cannot reach the archive bucket"
    assert [t["outcome"] for t in report["targets"]] == [Outcome.NOT_CHECKED] * 2
    published = (tmp_path / ".build/archive/report.json").read_text() + (
        tmp_path / ".build/archive/summary.md"
    ).read_text()
    assert "secret" not in published
    assert detail in capsys.readouterr().err


def test_the_report_so_far_is_handed_over_after_each_target(tmp_path: Path) -> None:
    world = World([release_v1()])
    write_packs(
        tmp_path, [entry(), entry("https://example.test/x", overrideSource="Other")]
    )
    checkpoints: list[list[Any]] = []

    run_archive(
        tmp_path,
        world.bucket,
        http=world.http,
        capture=capture_ok,
        checkpoint=lambda partial: checkpoints.append(
            [(t.get("outcome"), t.get("reason")) for t in partial["targets"]]
        ),
    )

    assert checkpoints == [
        [
            (Outcome.ARCHIVED, None),
            (Outcome.NOT_CHECKED, "the run ended before reaching it"),
        ],
        [(Outcome.ARCHIVED, None), (Outcome.SKIPPED, "unsupported source")],
    ]


def test_a_spent_deadline_stops_the_release_request() -> None:
    world = World([release_v1()])
    world.http.clock = lambda: 100.0
    [target] = select_targets_for(entry())

    report = world.archiver(deadline=50.0).process(target)

    assert report["outcome"] == Outcome.FAILED
    assert world.api.requests == []


def test_a_spent_deadline_stops_the_asset_download() -> None:
    now = [0.0]
    world = World([release_v1()])
    world.http.clock = lambda: now[0]
    resolve = world.api.__call__

    def resolve_then_spend(request: Request, timeout: float) -> Any:
        response = resolve(request, timeout)
        now[0] = 100.0
        return response

    world.http.transport = resolve_then_spend
    [target] = select_targets_for(entry())

    report = world.archiver(deadline=50.0).process(target)

    assert report["outcome"] == Outcome.FAILED
    assert len(world.api.requests) == 1
    assert world.downloads.urls == []
    assert world.bucket.objects == {}


def test_a_last_upload_that_ends_past_the_deadline_still_writes_the_manifest() -> None:
    now = [0.0]
    world = World([release_v1()])
    world.http.clock = lambda: now[0]
    inner = world.bucket.upload_file

    def slow_bundle(path: Path, key: str) -> None:
        inner(path, key)
        if key.endswith("repo.bundle"):
            now[0] = 100.0

    world.bucket.upload_file = slow_bundle  # ty: ignore[invalid-assignment]
    [target] = select_targets_for(entry())

    report = world.archiver(deadline=50.0).process(target)

    assert report["outcome"] == Outcome.ARCHIVED
    assert world.bucket.writes[-1].endswith("manifest.json")


def test_unreadable_packs_give_a_failed_report(tmp_path: Path) -> None:
    report = run_archive(tmp_path, FakeBucket())

    assert report["status"] == Status.FAILED
    assert "unreadable" in report["error"]


def test_the_report_and_summary_are_written(tmp_path: Path) -> None:
    write_packs(tmp_path, [entry("https://example.test/x", overrideSource="Other")])
    report = run_archive(tmp_path, None)

    write_archive_report(tmp_path, report)

    written = json.loads((tmp_path / ".build/archive/report.json").read_text())
    assert written["status"] == "success" and written["dryRun"] is True
    assert "skipped" in (tmp_path / ".build/archive/summary.md").read_text()


def test_a_failed_target_with_a_version_shows_its_error_in_the_summary() -> None:
    report = ArchiveReport(
        status=Status.SUCCESS,
        dryRun=False,
        targets=[
            TargetReport(
                name="App",
                url=SOURCE_URL,
                outcome=Outcome.FAILED,
                version="v1",
                error="HTTP 404 for app.apk",
            )
        ],
    )

    assert f"failed: {SOURCE_URL} (App): HTTP 404 for app.apk" in render_summary(report)


def test_the_summary_escapes_markup_in_a_targets_text() -> None:
    report = ArchiveReport(
        status=Status.SUCCESS,
        dryRun=False,
        targets=[
            TargetReport(
                name="<b>App</b>",
                url="https://example.test/<x>",
                outcome=Outcome.FAILED,
                error="bad <script>",
            )
        ],
    )

    summary = render_summary(report)

    assert "<b>" not in summary and "<script>" not in summary
    assert "&lt;b&gt;App&lt;/b&gt;" in summary and "bad &lt;script&gt;" in summary
