from __future__ import annotations

import hashlib
import json
from itertools import permutations
from pathlib import Path

import pytest

from omnipack.model import Provenance, Variant
from omnipack.overlay import ComposedApp
from omnipack.render import (
    RenderError,
    hydrate_settings,
    render,
)
from omnipack.settings_defaults import OBTAINIUM_VERSION, SETTINGS_DEFAULTS

FIXTURES = Path(__file__).parent / "fixtures"


def composed(
    package_id: str = "org.example.app",
    *,
    name: object = "Example",
    url: object = "https://github.com/example/app",
    source: str = "GitHub",
    categories: object = ("Emulator",),
    settings: object = None,
    author: object | None = "example",
) -> ComposedApp:
    data: dict[str, object] = {
        "id": package_id,
        "url": url,
        "name": name,
        "overrideSource": source,
        "categories": list(categories) if isinstance(categories, tuple) else categories,
        "additionalSettings": {} if settings is None else settings,
    }
    if author is not None:
        data["author"] = author
    return ComposedApp(
        Variant.SINGLE,
        Provenance("test", "fixture"),
        data,
    )


def document(apps: list[ComposedApp], settings: dict[str, object] | None = None):
    return json.loads(render(apps, settings or {}))


def test_defaults_match_every_source_key_set_in_upstream_exports() -> None:
    observed: dict[str, set[str]] = {}
    for fixture in (
        "rjny-single.json",
        "rjny-dual.json",
        "bboi-single.json",
        "bboi-dual.json",
    ):
        exported = json.loads((FIXTURES / fixture).read_text())
        for app in exported["apps"]:
            observed.setdefault(app["overrideSource"], set()).update(
                json.loads(app["additionalSettings"])
            )

    assert OBTAINIUM_VERSION == "GitHub/HTML 1.6.14; GitLab 1.6.15"
    assert {source: set(SETTINGS_DEFAULTS[source]) for source in observed} == observed
    assert len(SETTINGS_DEFAULTS["GitHub"]) == 29
    assert len(SETTINGS_DEFAULTS["HTML"]) == 29
    assert len(SETTINGS_DEFAULTS["GitLab"]) == 20


@pytest.mark.parametrize("source", ["GitHub", "HTML", "GitLab"])
def test_hydration_fills_sparse_settings_in_canonical_order(source: str) -> None:
    hydrated = hydrate_settings(source, {"trackOnly": True, "futureKey": 42})

    assert list(hydrated) == [*SETTINGS_DEFAULTS[source], "futureKey"]
    assert hydrated["trackOnly"] is True
    assert hydrated["futureKey"] == 42


def test_hydration_matches_shared_rjny_export() -> None:
    exported = json.loads((FIXTURES / "rjny-single.json").read_text())
    upstream = next(app for app in exported["apps"] if app["id"] == "aenu.aps3e")
    sparse = {"about": "PS3 emulator for Android"}

    assert hydrate_settings("GitHub", sparse) == json.loads(
        upstream["additionalSettings"]
    )


def test_render_encodes_settings_and_supplies_missing_optional_import_fields() -> None:
    app = composed(settings={"trackOnly": True}, categories=(), author=None)
    app.data.pop("categories")
    rendered = document([app])["apps"][0]

    assert isinstance(rendered["additionalSettings"], str)
    assert json.loads(rendered["additionalSettings"])["trackOnly"] is True
    assert rendered["author"] == ""
    assert rendered["categories"] == []


def test_render_hydrates_when_app_settings_are_missing() -> None:
    app = composed()
    app.data.pop("additionalSettings")

    rendered = document([app])["apps"][0]

    assert json.loads(rendered["additionalSettings"]) == SETTINGS_DEFAULTS["GitHub"]


@pytest.mark.parametrize("field,value", [("name", None), ("url", 7)])
def test_render_rejects_missing_or_wrong_required_strings(
    field: str, value: object
) -> None:
    app = composed()
    if value is None:
        app.data.pop(field)
    else:
        app.data[field] = value

    with pytest.raises(RenderError, match=rf"org\.example\.app.*{field}"):
        render([app], {})


def test_render_is_byte_stable_and_pins_object_key_order() -> None:
    app = composed(settings={"future": 1})
    app.data["zFuture"] = True
    app.data["aFuture"] = False

    first = render([app], {"zSetting": 1, "aSetting": 2})
    second = render([app], {"aSetting": 2, "zSetting": 1})

    assert first == second
    assert first.endswith("\n")
    rendered_app = json.loads(first, object_pairs_hook=dict)["apps"][0]
    assert list(rendered_app) == [
        "id",
        "url",
        "author",
        "name",
        "additionalSettings",
        "categories",
        "overrideSource",
        "aFuture",
        "zFuture",
    ]

    reversed_data = dict(reversed(list(app.data.items())))
    reordered = ComposedApp(app.variant, app.provenance, reversed_data)
    assert render([reordered], {"aSetting": 2, "zSetting": 1}) == second


def test_render_rejects_non_finite_numbers() -> None:
    with pytest.raises(RenderError, match="invalid in JSON"):
        render([composed(settings={"future": float("nan")})], {})


def test_render_orders_by_first_category_then_name_then_id_for_all_permutations() -> (
    None
):
    apps = [
        composed("z-id", name="A", categories=("Zulu", "Alpha")),
        composed("a-id", name="Z", categories=("Alpha",)),
        composed("b-id", name="Same", categories=("Beta",)),
        composed("a-tie", name="Same", categories=("Beta",)),
        composed("uncategorized", name="ZZ", categories=()),
    ]
    expected = ["uncategorized", "a-id", "a-tie", "b-id", "z-id"]

    for ordering in permutations(apps):
        assert [app["id"] for app in document(list(ordering))["apps"]] == expected


def test_settings_categories_use_configured_and_derived_colors_for_observed_union() -> (
    None
):
    derived = int.from_bytes(b"\xff" + hashlib.sha256(b"Beta").digest()[:3])
    apps = [
        composed("one", categories=("Alpha", "Beta")),
        composed("two", categories=()),
    ]
    rendered = document(
        apps,
        {
            "categories": {"Alpha": 0xFF010203, "Unused": 0xFF040506},
            "groupByCategory": True,
        },
    )["settings"]

    assert rendered["categories"] == json.dumps(
        {"Alpha": 0xFF010203, "Beta": derived}, separators=(",", ":")
    )
    assert rendered["groupByCategory"] is True
    assert "Unused" not in rendered["categories"]
    assert (
        document(apps, {"categories": rendered["categories"]})["settings"]["categories"]
        == rendered["categories"]
    )


def test_render_rejects_duplicate_package_ids() -> None:
    with pytest.raises(RenderError, match="duplicate package id.*same"):
        render([composed("same"), composed("same", name="Other")], {})


def test_render_canonicalizes_nested_objects_and_preserves_array_order() -> None:
    left = {"z": [{"second": 2, "first": 1}], "a": [3, 1, 2]}
    right = {"a": [3, 1, 2], "z": [{"first": 1, "second": 2}]}
    first_app = composed(settings={"intermediateLink": [left]})
    second_app = composed(settings={"intermediateLink": [right]})
    first_app.data["future"] = left
    second_app.data["future"] = right
    first = render([first_app], {"future": left})
    second = render([second_app], {"future": right})
    assert first == second
    decoded = json.loads(first)
    assert decoded["settings"]["future"] == left
    assert decoded["apps"][0]["future"] == left
    assert json.loads(decoded["apps"][0]["additionalSettings"])["intermediateLink"] == [
        left
    ]
