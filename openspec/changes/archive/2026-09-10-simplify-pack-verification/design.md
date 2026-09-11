## Context

See proposal.md for the accepted responsibility reduction. The current pure
validator already covers the serialized pair, configuration constraints, and
README catalog. Live behavior is layered over that validator, but its report
shape is also consumed by the publisher and many curation tests.

## Goals / Non-Goals

Keep the existing pure validator and publication byte boundaries. Remove the
live subsystem and its dependent test machinery completely. Preserve generated
app configurations, including filters and version policies used by Obtainium.

No dependency replacement, alternate live checker, or Flutter harness is part of
this change. Source ingestion still makes requests and can discover package IDs
from APKs. Broader publisher simplification remains independent.

## Decisions

### Use the existing pure validation path

`pack verify` retains structural validation and generated-catalog comparison.
Keep types, required default keys, source URL shapes, identity uniqueness,
composition constraints, and catalog checks. Do not compile patterns or interpret
source settings as a Python approximation of Obtainium. Unknown extra settings
remain structurally acceptable. A malformed regex string can therefore pass;
this is an explicit limitation rather than an unsupported-feature classifier.

Making the current verifier optional was rejected because it retains its
maintenance burden. Reusing the application through Flutter was rejected as an
additional toolchain/integration responsibility. Neither is a fallback path.

### Delete live-only code and adapt its consumers

Remove live.py, live_http.py and resolution/ once all imports are removed.
Delete verification-only probe/caching helpers in http.py after auditing callers;
retain shared transport, retry, redaction and credential protections needed by
source ingestion and package-ID discovery. Do not retain resolvers in tests.

Convert curation tests to fixture-driven composition/render checks of actual
exported settings. Keep evidence files and meaningful identity, family,
selection, overlay, catalog, and build-failure tests. Remove tests whose only
contract was the retired live implementation. Do not assert equivalent live
coverage after deletion.

### Emit a deliberately incompatible structural report schema

Advance verification schema to 2 and verifier identity. Retain offline mode,
started/completed timestamps, complete/status, exact structural input fingerprints,
and contextual errors. Remove compatibility baseline, resolution entries, probes,
version classifications, and live warnings. Keep build reporting independent.
HTTP config is not a verification input. No credential lookup is needed by verify.

Report parsing and publisher validation accept the new schema only. Older
verification reports produce a useful rerun diagnostic rather than invoking a
legacy reader. Supported reports with outdated identity or changed inputs are
stale. Retain atomic running/completed records and input-change detection for the
existing publisher contract. Further evidence-protocol simplification is separate.

### Replace only the publisher's verification gate

Run fresh `pack verify` after building the candidate. Adapt selected-revision
runtime validation to schema 2 and offline mode, retaining invocation freshness,
completion, current input hashes, and verified-byte comparisons through staging.
Do not weaken the allowed-path list or README handwritten-content boundary.

Align the composition contract with this structural gate: failed structural
verification blocks publication without selecting another project or family
alternative. After successful ingestion and building, unavailable app release
metadata does not add a publication gate or trigger reselection. Preserve standard
fallback when no eligible preferred dual candidate remains after successful
ingestion and deliberate exclusions unless a pin requires one, whole-source
fetch failures that abort building, and configured release fallback within a
selected project.

Keep release synchronization and its digest checks. Previously, resolving the
tracker also exposed a missing bootstrap seed before a main push. Preserve that
prerequisite through a narrow release existence/ownership preflight before main
publication, using the existing release discovery machinery. It is not app
verification and does not justify retaining a GitHub source resolver. Release
state is rediscovered during synchronization as today.

### State the reduced guarantee in current documentation

Update development, verification, publishing, version-detection and curation
instructions. Source-resolution examples describe intended behavior in Obtainium.
Past observations retain dates and provenance. Do not rewrite archives or
historical evidence as if they were recorded with the new validator. Update the
main verification purpose during spec synchronization to describe structural
validation. Retired flags fail explicitly; there is no successful compatibility
alias that silently performs fewer checks.

## Risks / Trade-offs

- Structurally valid settings can select an unavailable or unsuitable release.
  Document the limit and use Obtainium when investigating changed app behavior.
- Tests currently share resolver helpers. Audit imports before deletion and keep
  curation configuration assertions rather than dropping whole useful suites.
- Publisher consumers could accept obsolete evidence. Reject old schema and
  cover rejection, current-input mismatch and exact-byte publication checks.
- Release preflight can race remote changes. Existing synchronization discovery
  and ownership checks remain authoritative at mutation time.
- Build and release traffic remain. Do not advertise the entire nightly process
  as network-free; only pack verification becomes exclusively structural.

## Migration Plan

Land code, tests, current documentation, and spec deltas together after review.
Regenerate `.build/verify.json` locally; old reports are disposable and cannot
qualify a candidate. Remove obsolete live cache usage without deleting unrelated
scratch evidence. Existing commands with removed flags fail and must become
`pack verify`. Exported pack settings and bytes should not change under identical
fixture inputs. Run project checks and publication boundary tests without making
real publication writes. No operational release bootstrap is performed by this
change. Rollback, if needed, is a maintainer-controlled reversion, not automatic
publication or restoration of historical reports.
