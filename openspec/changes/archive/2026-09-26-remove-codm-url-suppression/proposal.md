## Why

Ingestion drops a committed codm2000 entry whenever a higher-precedence source
already lists the same normalized project URL with dual eligibility. No other
source has such a rule. It works around package-ID mismatches between sources,
not precedence: families form from a shared package ID or an explicit family, so
a codm2000 build that another source lists under a different ID never meets it
in a family. The pack model is to aggregate every source's candidates, resolve
conflicts by precedence within a family, and prune the owner's package denials.
A rule scoped to one source breaks that model, and extending it to later sources
would multiply the breakage.

## What Changes

- Remove project-URL suppression of codm2000 candidates. Every committed
  codm2000 entry becomes a dual-only, dual-preferred candidate. It reaches
  composition like any other source's candidate, where family formation,
  dual preference, precedence, pins and denials decide.
- Keep the current packs unchanged with owner configuration instead of a rule.
  The rule hides 9 entries today:
  - Six share a package ID, directly or through an existing composition
    correction, with a higher-precedence BBoi dual-asset build that is also
    dual-preferred. Precedence keeps BBoi's build:
    - `com.aure.banjorecomp`
    - `io.github.hm64recomp`
    - `org.openmw.ds`
    - `dev.twilitrealm.dusk`
    - `dev.picori.tmc`
    - `com.dishii.zelda3`
  - Two share a package ID with an ordinary RJNY build: `app.nanostack.pixelguide`
    and `com.emulnk`. Dual preference would let the codm2000 rendering replace
    RJNY's in dual, so two dual pins select the RJNY builds.
  - One, `com.raekwon.supermetroid`, is the Super Metroid build the owner already
    retired under BBoi's IDs. A package denial covers it.
- Retires: the codm2000 suppression paragraph and its two scenarios, and the
  source-record policy-field mention and scenario for suppressed codm2000
  records. Adds no requirement. Scenarios: about 1 added, 3 removed. Code: about
  -15 lines in the codm adapter and ingestion wiring. Configuration: about +20
  lines. Tests: about -40 lines of suppression tests, a few lines rewritten
  where tests assume suppression.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `source-ingestion`: codm2000 entries are no longer suppressed by
  another source's project URL. The policy-field requirement stops referring to
  suppressed codm2000 records.

## Impact

- `src/omnipack/sources/codm.py`, `src/omnipack/sources/__init__.py`: drop the
  covered-URL set and the higher-precedence input to the codm adapter.
- `config/deny.json`, `config/composition.json`: one denial, two dual pins.
- `tests/test_sources.py`, `tests/test_source_generation_fixtures.py`: remove or
  rewrite the suppression tests and the captured pipeline's covered-URL filter.
- `.build/report.json`: codm2000 admissions list all 30 committed entries.
  `dist/single-screen.json`, `dist/dual-screen.json` and the README catalog stay
  unchanged.
- The in-flight add-quiver-source change later drops its generated-candidate
  suppression on top of this.
