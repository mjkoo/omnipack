from __future__ import annotations

import json
from html import unescape
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

import pytest

from omnipack.catalog import (
    CatalogError,
    generate_catalog,
    replace_catalog,
    split_catalog,
)
from omnipack.composition_policy import CompositionPolicy, rendered_key

FIXTURES = Path(__file__).parent / "fixtures"


def app(
    package_id: str,
    name: str,
    url: str,
    *,
    categories: list[str] | None = None,
    source: str = "GitHub",
    **extra: object,
) -> dict[str, object]:
    return {
        "id": package_id,
        "url": url,
        "author": "fixture",
        "name": name,
        "additionalSettings": "{}",
        "categories": categories or [],
        "overrideSource": source,
        **extra,
    }


def pack(*apps: dict[str, object], settings: object | None = None) -> bytes:
    return json.dumps(
        {"settings": settings or {}, "apps": apps},
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode()


def policy(*projections: tuple[str, str, str]) -> CompositionPolicy:
    return CompositionPolicy(
        (),
        (),
        {
            rendered_key(package_id, url): family
            for package_id, url, family in projections
        },
        {},
    )


def decoded_apps(catalog: bytes) -> list[dict[str, object]]:
    links = []
    for part in catalog.decode().split('href="')[1:]:
        url = part.split('"', 1)[0].replace("&amp;", "&")
        if url.startswith("https://apps.obtainium.imranr.dev/redirect?"):
            deep_link = parse_qs(urlsplit(url).query)["r"][0]
            links.append(
                json.loads(unquote(deep_link.removeprefix("obtainium://app/")))
            )
    return links


def test_catalog_groups_variants_by_current_family_and_preserves_exact_apps() -> None:
    single = app(
        "org.example.standard",
        "Shared App",
        "https://example.test/standard?x=1&y=%25#release",
        categories=["Utilities"],
        additionalSettings='{"trackOnly":"false","pattern":"a\\\\d+"}',
        future={"typed": True},
    )
    dual = app(
        "org.example.dual",
        "Different Name",
        "https://example.test/dual",
        categories=["Other upstream category"],
        additionalSettings='{"trackOnly":true}',
    )
    catalog = generate_catalog(
        pack(single, settings={"packWide": "excluded"}),
        pack(dual),
        policy(
            (
                "org.example.standard",
                "https://example.test/standard?x=1&y=%25#release",
                "shared",
            ),
            ("org.example.dual", "https://example.test/dual", "shared"),
        ),
    )

    text = catalog.decode()
    assert text.count("| Shared App |") == 1
    assert "<summary>Utilities</summary>" in text
    assert text.index("standard?x=1&amp;y=%25#release") < text.index("Add to Obtainium")
    assert decoded_apps(catalog) == [single, dual]


def test_gitlab_catalog_link_and_individual_import_preserve_native_identity() -> None:
    gitlab = app(
        "com.aurora.store",
        "Aurora Store",
        "https://gitlab.com/AuroraOSS/Parent/AuroraStore",
        source="GitLab",
        additionalSettings=json.dumps({"fallbackToOlderReleases": True}),
    )
    catalog = generate_catalog(pack(gitlab), pack(dict(gitlab)), policy())
    assert catalog.decode().count(">GitLab</a>") == 2
    assert decoded_apps(catalog) == [gitlab, gitlab]


def test_catalog_handles_dual_only_ordering_and_escapes_source_text() -> None:
    lower = app("z.id", "alpha", "https://example.test/z", categories=["beta"])
    exact = app("a.id", "Alpha", "https://example.test/a", categories=["Beta"])
    unsafe = app(
        "unsafe.id",
        "[unsafe] | <b>line\nbreak</b> *x* ~~deleted~~",
        "https://example.test/path?a=1&b=2",
    )
    catalog = generate_catalog(
        pack(lower, exact),
        pack(unsafe),
        policy(),
    ).decode()

    assert (
        catalog.index("<summary>Beta</summary>")
        < catalog.index("<summary>beta</summary>")
        < catalog.index("<summary>Other</summary>")
    )
    assert "| Alpha |" in catalog
    assert "| alpha |" in catalog
    assert "| - |" in catalog
    assert "\\[unsafe\\] \\| &lt;b&gt;line break&lt;/b&gt; \\*x\\*" in catalog
    assert r"\~\~deleted\~\~" in catalog
    assert "<b>" not in catalog
    assert '>GitHub</a> · <a href="' in catalog


def test_source_url_cannot_break_the_table_or_html() -> None:
    unsafe = app(
        "unsafe.url",
        "Safe name",
        'https://example.test/a|b\nnext?q="quoted"&x=1',
    )

    catalog = generate_catalog(pack(unsafe), pack(), policy()).decode()

    assert 'href="https://example.test/a%7Cb%0Anext?q=%22quoted%22&amp;x=1"' in catalog


def test_source_label_and_category_render_as_text_without_changing_payload() -> None:
    hostile = app(
        "hostile.source",
        "Safe name",
        "https://example.test/app",
        categories=["<script>bad</script> | *category*\nnext"],
        source="A|B *bold* ~~deleted~~ <img>\nnext",
        unknown={"preserved": True},
    )

    catalog = generate_catalog(pack(hostile), pack(), policy())
    text = catalog.decode()

    assert (
        "<summary>&lt;script&gt;bad&lt;/script&gt; &#124; &#42;category&#42; next</summary>"
        in text
    )
    assert (
        ">A&#124;B &#42;bold&#42; &#126;&#126;deleted&#126;&#126; &lt;img&gt; next</a>"
        in text
    )
    assert "<script>" not in text
    assert "<img>" not in text
    assert decoded_apps(catalog) == [hostile]


def test_duplicate_explicit_family_in_one_variant_is_rejected() -> None:
    first = app("one", "One", "https://example.test/one")
    second = app("two", "Two", "https://example.test/two")
    shared = policy(
        ("one", "https://example.test/one", "app:shared"),
        ("two", "https://example.test/two", "app:shared"),
    )

    with pytest.raises(
        CatalogError,
        match="^dual-screen contains duplicate explicit family 'app:shared'$",
    ):
        generate_catalog(pack(), pack(first, second), shared)


def test_duplicate_package_id_in_one_variant_is_rejected() -> None:
    first = app("one", "One", "https://example.test/one")
    second = app("one", "One", "https://example.test/two")

    with pytest.raises(
        CatalogError, match="^single-screen contains duplicate package id 'one'$"
    ):
        generate_catalog(pack(first, second), pack(first), policy())


def row_programs(catalog: bytes) -> list[tuple[str, int]]:
    """Each table row's program name and how many import links it holds."""
    return [
        (line.split(" | ", 1)[0].removeprefix("| "), line.count("Add to Obtainium"))
        for line in catalog.decode().splitlines()
        if line.startswith("| ")
        and not line.startswith("| Program")
        and not line.startswith("| ---")
    ]


def test_same_id_entries_of_different_explicit_families_are_separate_rows() -> None:
    single = app("same", "Single", "https://example.test/one")
    dual = app("same", "Dual", "https://example.test/two")
    projected = policy(
        ("same", "https://example.test/one", "app:one"),
        ("same", "https://example.test/two", "app:two"),
    )
    catalog = generate_catalog(pack(single), pack(dual), projected)
    assert row_programs(catalog) == [("Dual", 1), ("Single", 1)]
    assert decoded_apps(catalog) == [dual, single]


@pytest.mark.parametrize("reverse", [False, True])
def test_package_id_pair_and_a_dual_entry_share_a_label_in_separate_rows(
    reverse: bool,
) -> None:
    single = app("a", "Shared", "https://example.test/a")
    same_id = app("a", "Shared", "https://example.test/a-dual")
    projected_dual = app("c", "Shared", "https://example.test/c")
    projected = policy(
        ("a", "https://example.test/a", "app:x"),
        ("c", "https://example.test/c", "app:x"),
    )
    duals = [projected_dual, same_id]
    if reverse:
        duals.reverse()
    catalog = generate_catalog(pack(single), pack(*duals), projected)
    # The rows tie on category, name and label; their package ids order them.
    assert row_programs(catalog) == [("Shared", 1), ("Shared", 2)]
    assert decoded_apps(catalog) == [projected_dual, single, same_id]


@pytest.mark.parametrize(
    "serialized",
    [b"not json", b"[]", b"{}", b'{"apps":[null]}'],
)
def test_malformed_serialized_pack_is_rejected(serialized: bytes) -> None:
    with pytest.raises(CatalogError):
        generate_catalog(serialized, pack(), policy())


def test_redirect_fixture_matches_the_real_decoder_round_trip() -> None:
    fixture = json.loads((FIXTURES / "obtainium-redirect-decoding.json").read_text())
    catalog = generate_catalog(
        pack(fixture["app"], settings={"packWide": "excluded"}), pack(), policy()
    )
    redirects = [
        unescape(part.split('"', 1)[0])
        for part in catalog.decode().split('href="')[1:]
        if part.startswith("https://apps.obtainium.imranr.dev/redirect?")
    ]
    assert redirects == [fixture["url"]]

    outer_query = urlsplit(redirects[0]).query
    deep_link = parse_qs(outer_query)["r"][0]
    assert deep_link.startswith("obtainium://app/")
    encoded = deep_link.removeprefix("obtainium://app/")
    decoded = json.loads(unquote(encoded))

    assert decoded == fixture["app"]


def test_split_and_replace_preserve_every_byte_outside_marker_interior() -> None:
    readme = (
        b"\xffhandwritten\r\n<!-- omnipack:catalog:start -->\r\n"
        b"old\r\nbytes\r\n"
        b"<!-- omnipack:catalog:end -->\r\nfooter\x00"
    )
    prefix, interior, suffix = split_catalog(readme)

    assert prefix == b"\xffhandwritten\r\n<!-- omnipack:catalog:start -->\r\n"
    assert interior == b"old\r\nbytes\r\n"
    assert suffix == b"<!-- omnipack:catalog:end -->\r\nfooter\x00"
    assert replace_catalog(readme, b"new\n") == prefix + b"new\n" + suffix


@pytest.mark.parametrize(
    "readme",
    [
        b"",
        b"<!-- omnipack:catalog:start -->\n",
        b"<!-- omnipack:catalog:end -->\n",
        b"x <!-- omnipack:catalog:start -->\n<!-- omnipack:catalog:end -->\n",
        b"<!-- omnipack:catalog:start --> x\n<!-- omnipack:catalog:end -->\n",
        b"<!-- omnipack:catalog:end -->\n<!-- omnipack:catalog:start -->\n",
        (
            b"<!-- omnipack:catalog:start -->\n"
            b"<!-- omnipack:catalog:start -->\n"
            b"<!-- omnipack:catalog:end -->\n"
        ),
        (
            b"<!-- omnipack:catalog:start -->\n"
            b"<!-- omnipack:catalog:end -->\n"
            b"<!-- omnipack:catalog:end -->\n"
        ),
    ],
)
def test_invalid_marker_layout_is_rejected(readme: bytes) -> None:
    with pytest.raises(CatalogError, match="catalog marker"):
        split_catalog(readme)
