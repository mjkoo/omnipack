# README catalog validation

The README catalog is generated from the two committed serialized exports and
current composition policy. Generation does not refresh upstream sources. Each
family has one row with the single-screen presentation taking precedence; each
variant link retains that variant's complete exported app object.

## Automated checks

Catalog tests cover different builds in one family, shared builds, dual-only
entries, category/name ordering, package-family fallback, current projection,
duplicate projected families, text escaping, and full app-payload fidelity.
Marker tests cover malformed layouts and byte preservation outside the generated
interior, including CRLF and non-UTF8 handwritten bytes.

Build integration tests inject staging and replacement failures with and without
prior exports, including failure to replace README after both packs. They verify
restoration to prior bytes or absence and cleanup of temporary files. Concurrent
README and policy edits, including edits during the final temporary-file write,
prevent publication and preserve the edits. Standalone verification tests reject
missing, unreadable, malformed and stale catalogs without input writes or live
requests, detect input mutation, and allow fresh verification after handwritten
edits. Historical seven- and eight-input reports remain readable but stale.

Nightly integration tests cover catalog-only publication, handwritten-content
rejection, candidate and staged byte checks, base mode preservation, no-op and
fresh-attempt behavior using disposable local repositories. These tests do not
publish to GitHub or dispatch the production workflow.

The full delivery `just check-all` run passed on 2026-09-09: 793 tests with 92%
coverage, formatting, lint, types, lock consistency, dependency audit, Python
packaging, offline pack verification, workflow lint and Nix checks for
`aarch64-darwin`. Strict validation passed for the active change and all eight
main OpenSpec capabilities. Other platform builds were not claimed.

## Redirect and rendered preview

Checked on 2026-09-09 against the official [deep-link documentation](https://wiki.obtainium.imranr.dev/deep_links/)
and [redirect source](https://github.com/ImranR98/apps.obtainium.imranr.dev/blob/main/src/pages/redirect.astro).
The redirect reads the decoded `r` query value, strips `obtainium://app/`, decodes
the percent-encoded JSON, parses it, and reserializes the object before handoff.
The test for `tests/fixtures/obtainium-redirect-decoding.json` generates a catalog
from its complete app record, matches the generated redirect to the fixture URL,
and follows those decoding and handoff steps. It checks exact payload and type
fidelity with Unicode, reserved characters, regex escaping and nested typed data.

An audit of the initial generated README matched all 195 decoded variant links
to the exported app-record multiset exactly. Its 107 family rows appear in nine
categories. A local Pandoc 3.7.0.2 GFM render was inspected using Chrome headless
screenshots at 1440 by 1200 and 1800 by 1400. The preview showed installation
instructions first, closed category sections, a readable expanded three-column
table, credits, and development instructions. An apostrophe-escaping defect
found in the first preview was corrected before the final render. This checks
a local GFM rendering, not GitHub's production renderer.

## Android acceptance

**Pending.** No Android device was available for this implementation. Automated
payload round trips and a rendered README preview do not establish browser-to-app
handoff, import confirmation, installation, signatures or device compatibility.

On a representative Android device with Obtainium installed, open the published
README in the browser and test an ordinary GitHub app, an HTML-source app, a
track-only resource and a family whose two variants differ. Check that each
redirect presents the expected app, hands off to Obtainium, and preserves its
configuration after import confirmation. Install an appropriate installable
entry separately; confirm a track-only entry remains a tracking resource. Also
import each full JSON pack from a downloaded file. Record the device, Android,
browser and Obtainium versions, selected entries, outcomes and observation date
before claiming device acceptance.
