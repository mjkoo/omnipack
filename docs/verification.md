# Pack verification

`pack verify` checks existing pack files, local configuration and the generated
README catalog without network access. It validates structure and consistency.
Obtainium evaluates release selection, regular expressions and effective versions
on the device; the pack builder no longer maintains an independent implementation
of those behaviors.

## Commands and evidence

Run commands from the repository root:

| Command | Work performed |
| --- | --- |
| `uv run pack verify` or `just verify` | Validate the existing serialized pair, catalog and local configuration offline |
| `uv run pack report` | Display available build and verification evidence without fetching or writing files |
| `uv run pack build` | Ingest and compose sources, validate rendered bytes, then publish both packs and the catalog as a recoverable unit |

Unsupported arguments fail before verification starts and leave existing evidence
untouched. The separate `pack generate-source codm` operation resolves only the
explicitly configured codm source candidate; it does not extend structural
verification or change committed files.

Standalone verification writes schema 4 evidence to `.build/verify.json`, separately
from the build report. It reads every input once, checks and fingerprints exactly
those captured bytes, and writes the report a single time, when the run completes;
an interrupted run leaves no new report, so any report already on disk still
describes only the inputs an earlier completed run checked. Reports contain offline
mode, verifier identity, observation times, status, contextual errors and
SHA-256 fingerprints of both distribution files, the denylist, the overlay,
composition policy and README. Missing and unreadable inputs are explicit. HTTP
configuration and environment credentials are not consulted or fingerprinted.

Independent errors are collected across both variants. Verification exits zero
only for a complete run without errors; report persistence failure also causes a
nonzero exit and a stderr diagnostic.

Verification never rebuilds or changes the packs, README, configuration or
`.build/report.json`. Building performs source ingestion but does not discover
package IDs; codm discovery belongs to source generation.

`pack report` labels supported evidence stale when any input fingerprint or the
verifier identity differs. A verification report with any schema other than the
current one requires regeneration with `pack verify`. Build reports must use
schema 3; any other build report schema requires regeneration with `pack build`.
One available report is enough; missing both, corrupt reports and unsupported
schemas fail display.
Displaying a recorded failed operation exits successfully.

## Structural checks and limits

The validator checks JSON types, required app fields, absolute URLs, supported
source types and package uniqueness. Within decoded settings, it checks that a
setting named by the source type's defaults has its default's type, that HTML
`intermediateLink` steps and `requestHeader` records are well formed, and that
`preferredApkIndex`, when present, is an integer. These values come from upstream
records and overlay patches, and rendering copies them unchecked. Unknown settings
are acceptable when structurally valid. Regex strings are not compiled or
evaluated, so even a malformed pattern can pass structural checks.

Verification no longer checks that every default key is present, the rendered
pack settings or category colours, or GitLab project URL rules. Rendering fills
every default key and derives each category colour from its name, and ingestion
enforces the GitLab URL rules.

Composition checks cover rendered families, projected pins, denied packages,
package uniqueness, family coverage and overlay targets. They do not check
eligibility, which no candidate rule declares and rendered entries cannot reveal.
Rendered output omits losing candidates, so verification cannot reconstruct
provenance, candidate presence, preference or source ranking, or prove that a
patch produced the rendered values. Fixture-driven composition and rendering
tests protect maintained IDs, URLs, variant membership and override values
across refreshes.

Catalog verification compares the generated marker interior against the captured
packs and policy. Missing, unreadable, malformed or stale catalogs fail. Handwritten
content is excluded from catalog comparison but included in the README fingerprint.
A handwritten edit permits fresh verification while making old evidence stale.
Verification never repairs the catalog.

Success does not establish upstream health, release or download availability,
effective versions, APK identity, signatures, installation, architecture support,
re-import behavior or absence of spurious notifications. Investigate source
selection and version behavior in Obtainium. See [version detection](version-detection.md)
and [maintained curation](curation.md) for intended policies and their limitations.

## Publication and historical evidence

See [structural validation results](../openspec/changes/archive/2026-09-10-simplify-pack-verification/structural-verification-validation.md) for
the retained test suite, publication boundaries and byte-preservation checks.

Nightly publication runs `pack verify` once per run, in the read-only job, against
the exact candidate it committed locally beforehand; the write job trusts that job's
success and the pushed commit's SHA rather than re-running verification or reading a
report from a different run. Nightly does not run pre-build verification or repeat
development CI checks. Exact bytes, staging, publishable-path restrictions and the
README handwritten-content boundary remain enforced. A verification failure blocks
publication without selecting a different project. App release metadata becoming
unavailable after a successful build does not add a verification gate or cause
reselection.

The publisher separately checks the rolling release's existence, ownership marker,
title and published-prerelease state after a successful main push or a verified
no-op. A release-prerequisite failure blocks only release synchronization.
Verification itself never queries that release, including when the tracker is
present. See [publishing](publishing.md) for the two-job flow, bootstrap, release
synchronization and recovery.

Dated observations in [verification validation](../openspec/changes/archive/2026-09-08-add-pack-verification/verification-validation.md),
[curation validation](../openspec/changes/archive/2026-09-09-curate-app-version-policies/curation-validation.md), and retained fixture provenance
describe the checks performed at those times. Archived changes and git history
remain evidence of the retired implementation, without implying current
compatibility coverage or upstream health.

The RJNY verifier was evaluated as an implementation reference at revision
[`5bb57f833652c389c3b063d3b4af9b42ee11602a`](https://github.com/RJNY/Obtainium-Emulation-Pack/tree/5bb57f833652c389c3b063d3b4af9b42ee11602a),
particularly `scripts/test-apps.py`, under the Unlicense. No RJNY helper was copied
or adapted into the retired compatibility classifier. Its independent upstream
identity and historical attribution remain unchanged.
