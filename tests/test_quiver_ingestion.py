from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from omnipack.catalog import generate_catalog, replace_catalog
from omnipack.composition_policy import parse_composition_policy
from omnipack.http import HttpResponse
from omnipack.merge import compose
from omnipack.model import App, Provenance, SourceType, Variant
from omnipack.render import render, render_pack
from omnipack.source_catalog import render_catalog
from omnipack.sources import IngestionReport, SourceError, ingest_all, quiver
from omnipack.verify import run_verification
from tests.current_config_support import (
    CurrentConfiguration,
    build_current_configuration,
    current_configuration_fixture,  # noqa: F401
)


def entry(package: str, repo: str, **extra: object) -> dict[str, object]:
    return {
        "id": package,
        "url": f"https://github.com/{repo}",
        "name": repo.rsplit("/", 1)[-1],
        "overrideSource": "GitHub",
        "categories": ["Decomps/Recomps"],
        "additionalSettings": {},
        **extra,
    }


def write_catalog(tmp_path: Path, apps: list[object]) -> None:
    (tmp_path / "quiver.json").write_text(json.dumps({"apps": apps}))


def other(package: str, repo: str, source: str, origin: str) -> App:
    return App(
        package,
        f"https://github.com/{repo}",
        repo,
        SourceType.GITHUB,
        (),
        Provenance(source, "fixture"),
        eligibility=frozenset({Variant.DUAL})
        if source == "codm2000"
        else frozenset(Variant),
        origin=origin,
    )


def policy(rules: list[dict[str, object]] | None = None):
    return parse_composition_policy(
        {"schemaVersion": 1, "candidates": rules or [], "pins": []}
    )


def test_committed_quiver_ingests_every_entry_without_network(tmp_path: Path) -> None:
    write_catalog(
        tmp_path,
        [entry("org.example.one", "owner/one"), entry("org.example.two", "owner/two")],
    )
    report = IngestionReport()
    apps = quiver.fetch(tmp_path, {"catalog": "quiver.json"}, report)
    assert [app.id for app in apps] == ["org.example.one", "org.example.two"]
    assert all(app.eligibility == frozenset(Variant) for app in apps)
    assert all(
        app.origin == "quiver-generated" and app.source_type == SourceType.GITHUB
        for app in apps
    )
    assert [item["source"] for item in report.admitted] == ["quiver", "quiver"]


@pytest.mark.parametrize(
    "content",
    ["bad JSON", "[]", '{"apps":{}}', '{"apps":[{}]}'],
)
def test_quiver_malformed_catalog_fails_named(tmp_path: Path, content: str) -> None:
    (tmp_path / "quiver.json").write_text(content)
    with pytest.raises(SourceError, match="quiver"):
        quiver.fetch(tmp_path, {"catalog": "quiver.json"})


def test_quiver_missing_catalog_fails_named(tmp_path: Path) -> None:
    with pytest.raises(SourceError, match="quiver"):
        quiver.fetch(tmp_path, {"catalog": "missing.json"})


def test_quiver_duplicate_package_id_fails_named(tmp_path: Path) -> None:
    write_catalog(
        tmp_path,
        [
            entry("org.example.shared", "owner/one"),
            entry("org.example.shared", "owner/two"),
        ],
    )
    with pytest.raises(SourceError, match="quiver.*org.example.shared"):
        quiver.fetch(tmp_path, {"catalog": "quiver.json"})


@pytest.mark.parametrize("field", ["family", "variant"])
def test_quiver_rejects_composition_fields(tmp_path: Path, field: str) -> None:
    write_catalog(tmp_path, [entry("org.example.one", "owner/one", **{field: "x"})])
    with pytest.raises(SourceError, match=field):
        quiver.fetch(tmp_path, {"catalog": "quiver.json"})


@pytest.mark.parametrize(
    "record",
    [
        entry("a1b2c3d4e5f6", "owner/one"),
        entry("org.example.one", "owner/one", additionalSettings={"trackOnly": True}),
        entry(
            "org.example.one",
            "owner/one",
            url="https://gitlab.com/group/one",
            overrideSource="GitLab",
        ),
    ],
    ids=["placeholder-id", "track-only", "gitlab"],
)
def test_quiver_keeps_any_valid_committed_record(
    tmp_path: Path, record: dict[str, object]
) -> None:
    write_catalog(tmp_path, [record])
    [app] = quiver.fetch(tmp_path, {"catalog": "quiver.json"})
    assert (app.id, app.url, app.source_type) == (
        record["id"],
        record["url"],
        record["overrideSource"],
    )


def test_quiver_candidates_reach_composition_with_url_and_package_overlaps(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from omnipack.sources import bboi, extras, rjny

    write_catalog(
        tmp_path,
        [
            entry("org.example.shared", "owner/same"),
            entry("org.example.new", "owner/new"),
        ],
    )
    (tmp_path / "codm.json").write_text('{"apps":[]}')
    higher = other("org.example.shared", "owner/different", "rjny", "rjny-catalog")
    monkeypatch.setattr(rjny, "fetch", lambda *_: [higher])
    monkeypatch.setattr(bboi, "fetch", lambda *_: [])
    monkeypatch.setattr(extras, "fetch", lambda *_: [])

    class Offline:
        def get(self, *_args: object, **_kwargs: object) -> HttpResponse:
            raise AssertionError("routine build fetched Quiver or APK data")

    candidates = ingest_all(
        tmp_path,
        Offline(),
        {
            "rjny": {},
            "bboi": {},
            "codm": {"catalog": "codm.json"},
            "quiver": {"catalog": "quiver.json"},
        },
        [],
        IngestionReport(),
    )
    assert [app.id for app in candidates] == [
        "org.example.shared",
        "org.example.shared",
        "org.example.new",
    ]
    result = compose(candidates, [], [], policy=policy())
    # Every project URL is its own family, so a shared package id joins nothing.
    assert {
        (app.data["id"], app.data["url"]) for app in result.apps[Variant.SINGLE]
    } == {
        ("org.example.shared", "https://github.com/owner/different"),
        ("org.example.shared", "https://github.com/owner/same"),
        ("org.example.new", "https://github.com/owner/new"),
    }
    assert {
        item.family for item in result.report.selections if item.source == "quiver"
    } == {"github.com/owner/same", "github.com/owner/new"}
    assert [(item.variant, item.id) for item in result.report.repeated_ids] == [
        (Variant.SINGLE, "org.example.shared"),
        (Variant.DUAL, "org.example.shared"),
    ]


def test_quiver_ranks_between_rjny_and_bboi() -> None:
    quiver_app = other("org.example.game", "owner/quiver", "quiver", "quiver-generated")
    for source, origin, winner in (
        ("bboi", "bboi-standard-asset", "quiver"),
        ("rjny", "rjny-catalog", "rjny"),
        ("extras", "extras", "extras"),
    ):
        rival = other("org.example.game", "owner/quiver", source, origin)
        result = compose([rival, quiver_app], [], [], policy=policy())
        [single] = [
            item for item in result.report.selections if item.variant is Variant.SINGLE
        ]
        assert single.source == winner


def test_same_project_codm_dual_preference() -> None:
    quiver_app = other("org.example.game", "owner/same", "quiver", "quiver-generated")
    codm = other("org.example.game", "owner/same", "codm2000", "codm-generated")
    result = compose([quiver_app, codm], [], [], policy=policy())
    assert [app.data["url"] for app in result.apps[Variant.SINGLE]] == [quiver_app.url]
    assert [app.data["url"] for app in result.apps[Variant.DUAL]] == [codm.url]
    assert (
        next(
            selection.source
            for selection in result.report.selections
            if selection.variant is Variant.DUAL
        )
        == "codm2000"
    )


def test_different_package_fork_family_pairs_across_variants() -> None:
    quiver_app = other("org.example.base", "owner/base", "quiver", "quiver-generated")
    codm = other("org.example.fork", "owner/fork", "codm2000", "codm-generated")
    rules: list[dict[str, object]] = [
        {
            "match": {
                "source": app.provenance.source,
                "origin": app.origin,
                "id": app.id,
                "url": app.url,
            },
            "family": "app:game",
            "rationale": "Reviewed platform fork.",
        }
        for app in (quiver_app, codm)
    ]
    parsed = policy(rules)
    result = compose([quiver_app, codm], [], [], policy=parsed)
    assert [app.data["id"] for app in result.apps[Variant.SINGLE]] == [quiver_app.id]
    assert [app.data["id"] for app in result.apps[Variant.DUAL]] == [codm.id]
    single = render(result.apps[Variant.SINGLE]).encode()
    dual = render(result.apps[Variant.DUAL]).encode()
    assert b"app:game" not in single
    assert b"app:game" not in dual
    assert b"base" in generate_catalog(single, dual, parsed)


def test_quiver_future_membership_is_configuration_driven(tmp_path: Path) -> None:
    write_catalog(tmp_path, [entry("org.example.future", "newpublisher/future")])
    [candidate] = quiver.fetch(tmp_path, {"catalog": "quiver.json"})
    result = compose([candidate], [], [], policy=policy())
    assert all(
        [app.data["id"] for app in result.apps[variant]] == ["org.example.future"]
        for variant in Variant
    )
    denial = [{"url": candidate.url, "reason": "Rejected after review."}]
    denied = compose([candidate], denial, [], policy=policy())
    assert all(not denied.apps[variant] for variant in Variant)
    (tmp_path / "quiver.json").write_text('{"apps":[]}')
    empty = compose(
        quiver.fetch(tmp_path, {"catalog": "quiver.json"}), denial, [], policy=policy()
    )
    assert [item.url for item in empty.report.stale_exclusions] == [
        "github.com/newpublisher/future"
    ]


def assert_canonical_quiver_catalog(catalog: Path) -> None:
    entries = json.loads(catalog.read_bytes())["apps"]
    assert catalog.read_bytes() == render_catalog(entries), (
        f"{catalog} differs from the canonical rendering of its entries"
    )


def test_committed_quiver_catalog_is_canonical_without_a_fixed_roster() -> None:
    root = Path(__file__).resolve().parents[1]
    assert_canonical_quiver_catalog(root / "config/catalogs/quiver.json")


def test_a_valid_but_noncanonical_quiver_catalog_fails_the_check(
    tmp_path: Path,
) -> None:
    entries = [entry("org.example.one", "owner/one")]
    catalog = tmp_path / "quiver.json"
    catalog.write_bytes(render_catalog(entries))
    assert_canonical_quiver_catalog(catalog)

    catalog.write_text(json.dumps(json.loads(catalog.read_text()), indent=2))
    with pytest.raises(
        AssertionError, match=r"quiver\.json differs from the canonical"
    ):
        assert_canonical_quiver_catalog(catalog)


def test_current_configuration_fixture_composes_quiver(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests import current_config_support

    injected = other(
        "org.example.future", "newpublisher/future", "quiver", "quiver-generated"
    )
    original_fetch = current_config_support.quiver.fetch
    monkeypatch.setattr(
        current_config_support.quiver,
        "fetch",
        lambda *args: [*original_fetch(*args), injected],
    )
    current = build_current_configuration()
    assert any(app == injected for app in current.candidates)
    assert all(
        any(app.data["id"] == injected.id for app in current.result.apps[variant])
        for variant in Variant
    )


def test_current_composition_renders_and_verifies_with_quiver(
    current_configuration: CurrentConfiguration, tmp_path: Path
) -> None:
    root = Path(__file__).resolve().parents[1]
    injected = other(
        "org.example.future", "newpublisher/future", "quiver", "quiver-generated"
    )
    composed = compose(
        [*current_configuration.candidates, injected],
        json.loads((root / "config/deny.json").read_text()),
        json.loads((root / "config/overlay.json").read_text()),
        policy=parse_composition_policy(current_configuration.policy),
    )
    for name in ("deny", "overlay", "composition"):
        destination = tmp_path / f"config/{name}.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / f"config/{name}.json", destination)
    packs = {}
    for variant, stem in ((Variant.SINGLE, "single"), (Variant.DUAL, "dual")):
        data = render_pack(composed.apps[variant]).encode()
        packs[variant] = data
        destination = tmp_path / f"dist/{stem}-screen.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
    catalog = generate_catalog(
        packs[Variant.SINGLE],
        packs[Variant.DUAL],
        parse_composition_policy(current_configuration.policy),
    )
    (tmp_path / "README.md").write_bytes(
        replace_catalog((root / "README.md").read_bytes(), catalog)
    )
    assert run_verification(tmp_path)["status"] == "success"
