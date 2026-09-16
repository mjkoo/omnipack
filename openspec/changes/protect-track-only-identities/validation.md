# Implementation validation

Branch: `protect-track-only-identities`.

## Behavior and regression evidence

The pre-change full suite passed: 646 tests. Before implementation, the focused
policy suite failed seven cases: prohibited family, changed and restated identity,
corrected and ingested reserved-id collisions, descriptive-rule collision, and
selector precedence over rendered projections. Composition/CLI regressions failed
four cases before implementation. After implementation, all 117 focused policy,
composition, CLI and tracker tests passed.

The guard gathers every ingested track-only id before inspecting candidates,
uses exact boolean true, checks every collapsed candidate before transforms and
projections, and retains original selectors in errors. Controls cover descriptive
tracker rules, two trackers sharing an id, non-boolean settings, ordinary APK
rules and correction away from a reserved id.

## Captured-source compatibility

The shared current-configuration fixture ingested 130 candidates from captured
RJNY and BBoi inputs, committed extras and the generated catalog. All ordinary
effective ids were audited against all six ingested track-only ids:
`1845280017`, `476086958`, `767644078`, `809443320`, `904332840`, `994078275`.
No collisions occurred, including among candidates later excluded.

Rendering the same captured inputs before and after the guard produced identical
UTF-8 bytes for both variants:

| Variant | Bytes | SHA-256 |
| --- | ---: | --- |
| single | 102039 | f55841cc37706d93256f67b679c9b61eaf52f9fe05f61bf285cb3d0c8626f56f |
| dual | 129129 | d4b0ffe433274c4c6fbb63c753daaeb9836b2593e0933aecdf90e763a22a55bd |

No configuration migration is needed for these inputs. This audit does not claim
future upstream inputs cannot collide. Later overlay changes remain outside the
ingested-settings guard, as designed.

## Checks

Locked dependency check, formatting, lint, type checking, offline pack verification
and strict change validation passed. Independent reviews and final suite results
are recorded below as they complete.
